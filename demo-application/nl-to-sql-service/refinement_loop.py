import re
import sqlite3
from typing import Optional, Tuple, List, Dict, Any

from profiler import time_block, log_step, trace
import llm
import prompts

def categorize_compiler_error(error_msg: str) -> Tuple[str, List[str]]:
    """
    Parses compiler diagnostic error message to classify the error type 
    and extract referenced missing table/column identifiers.
    
    Returns:
        (error_type: str, missing_entities: list[str])
    """
    err_str = str(error_msg)
    err_lower = err_str.lower()
    missing_entities = []

    # 1. SQLite Schema Linking Errors
    # e.g. "no such column: T1.salary", "no such table: Employees"
    col_match = re.search(r'no such column:\s*([`"\[\w\.\-\]]+)', err_str, re.IGNORECASE)
    if col_match:
        raw_col = col_match.group(1).strip('`"[]')
        col_name = raw_col.split('.')[-1]
        missing_entities.append(col_name)
        return "SCHEMA_LINKING_ERROR", missing_entities

    tbl_match = re.search(r'no such table:\s*([`"\[\w\.\-\]]+)', err_str, re.IGNORECASE)
    if tbl_match:
        raw_tbl = tbl_match.group(1).strip('`"[]')
        tbl_name = raw_tbl.split('.')[-1]
        missing_entities.append(tbl_name)
        return "SCHEMA_LINKING_ERROR", missing_entities

    # 2. Microsoft SQL Server Schema Linking Errors
    # e.g. "Invalid column name 'salary'.", "Invalid object name 'dbo.Employees'."
    mssql_col = re.search(r"Invalid column name '([^']+)'", err_str, re.IGNORECASE)
    if mssql_col:
        missing_entities.append(mssql_col.group(1))
        return "SCHEMA_LINKING_ERROR", missing_entities

    mssql_tbl = re.search(r"Invalid object name '([^']+)'", err_str, re.IGNORECASE)
    if mssql_tbl:
        tbl_name = mssql_tbl.group(1).split('.')[-1]
        missing_entities.append(tbl_name)
        return "SCHEMA_LINKING_ERROR", missing_entities

    # 3. SQLite / MSSQL Syntax Errors
    # e.g. "near 'WHRE': syntax error", "Incorrect syntax near 'FROM'"
    if "syntax error" in err_lower or "incorrect syntax" in err_lower or "unrecognized token" in err_lower or "incomplete input" in err_lower:
        return "SYNTAX_ERROR", []

    # 4. Aggregation / Grouping / Ambiguity Errors
    if "misuse of aggregate" in err_lower or "must appear in the group by" in err_lower or "ambiguous column" in err_lower:
        return "AGGREGATION_ERROR", []

    # Fallback to general execution error
    return "SYNTAX_ERROR", []


def find_missing_schema_entities(
    missing_entities: List[str], 
    full_schema_meta: Optional[str], 
    current_schema_meta: str
) -> List[str]:
    """
    Rapidly scans the locally cached full database schema (<1ms) to locate any missing
    tables or columns that were omitted during Task 1 pruning, returning their DDL statements.
    """
    if not missing_entities or not full_schema_meta:
        return []

    # Split full schema into CREATE TABLE blocks
    blocks = re.split(r'(?=CREATE\s+TABLE)', full_schema_meta, flags=re.IGNORECASE)
    supplemental_ddls = []

    for entity in missing_entities:
        entity_lower = entity.lower()
        
        # Check if already present in current pruned schema
        if re.search(rf'\b{re.escape(entity)}\b', current_schema_meta, re.IGNORECASE):
            continue

        for block in blocks:
            block = block.strip()
            if not block.upper().startswith("CREATE TABLE"):
                continue

            # Extract table name
            match = re.search(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[\w\.\-\]]+)', block, re.IGNORECASE)
            if not match:
                continue

            raw_tbl = match.group(1).strip('`"[]')
            tbl_name = raw_tbl.split('.')[-1].lower()

            # Check if block matches missing table or contains missing column definition
            is_tbl_match = (tbl_name == entity_lower)
            is_col_match = bool(re.search(rf'^\s*[`"\[]?{re.escape(entity)}[`"\]]?\s+', block, re.IGNORECASE | re.MULTILINE))

            if is_tbl_match or is_col_match:
                ddl_stmt = block if block.endswith(';') else block + ';'
                if ddl_stmt not in supplemental_ddls:
                    supplemental_ddls.append(ddl_stmt)
                    log_step(f"Refinement Schema Expansion: Discovered missing entity '{entity}' in table [{raw_tbl}] (<1ms cached lookup).")

    return supplemental_ddls


def dry_run_validate(sql: str, db_conn=None) -> Tuple[bool, str, str]:
    """
    Performs compiler-level dry-run validation of a SQL query without executing or modifying data.
    
    Uses:
      - SQLite: `EXPLAIN <sql>` bytecode compilation
      - MSSQL: `SET NOEXEC ON; <sql>; SET NOEXEC OFF;` compilation
      
    Returns:
        (is_valid: bool, error_message: str, error_type: str)
    """
    if not sql or not sql.strip():
        return False, "Query is empty.", "SYNTAX_ERROR"

    clean_sql = sql.strip().rstrip(';')

    # Case 1: No DB connection provided (Standalone API call with DDL only)
    if db_conn is None:
        # Perform structural sanity check
        upper_sql = clean_sql.upper()
        if not (upper_sql.startswith("SELECT") or upper_sql.startswith("WITH")):
            return False, "Query must begin with SELECT or WITH clause.", "SYNTAX_ERROR"
        # Check basic parenthesis balance
        if clean_sql.count('(') != clean_sql.count(')'):
            return False, "Unbalanced parentheses in SQL query.", "SYNTAX_ERROR"
        return True, "", ""

    # Case 2: SQLite Connection (Used in Spider Benchmark & Test Suite)
    if isinstance(db_conn, sqlite3.Connection):
        try:
            cursor = db_conn.cursor()
            cursor.execute(f"EXPLAIN {clean_sql}")
            return True, "", ""
        except sqlite3.OperationalError as e:
            err_msg = str(e)
            err_type, _ = categorize_compiler_error(err_msg)
            return False, err_msg, err_type
        except Exception as e:
            err_msg = str(e)
            err_type, _ = categorize_compiler_error(err_msg)
            return False, err_msg, err_type

    # Case 3: Microsoft SQL Server Connection (Live ERP via pyodbc)
    try:
        cursor = db_conn.cursor()
        # Compile and check schema bindings without executing rows or locks
        validation_stmt = f"SET NOEXEC ON;\n{clean_sql};\nSET NOEXEC OFF;"
        cursor.execute(validation_stmt)
        return True, "", ""
    except Exception as e:
        # Ensure NOEXEC is reset on failure
        try:
            db_conn.cursor().execute("SET NOEXEC OFF;")
        except Exception:
            pass
        err_msg = str(e)
        err_type, _ = categorize_compiler_error(err_msg)
        return False, err_msg, err_type


def sanitize_sql_keyword_spacing(sql: str) -> str:
    """
    Safely separates concatenated table aliases and SQL keywords outside of string literals.
    Examples:
      - 'P2ON' -> 'P2 ON'
      - 'AS T1JOIN' -> 'AS T1 JOIN'
      - ')JOIN' -> ') JOIN'
      - 'T2WHERE' -> 'T2 WHERE'
      - 'T3ON' -> 'T3 ON'
      - '101AND' -> '101 AND', '2.5OR' -> '2.5 OR', ')AND' -> ') AND'
    Preserves real identifiers like 'LOCATION', 'PERSON', 'ACTION', etc., and quoted strings.
    """
    if not sql or not isinstance(sql, str):
        return sql

    # Split SQL into tokens outside of single-quoted and double-quoted strings
    parts = re.split(r"('(?:''|[^'])*'|\"(?:\"\"|[^\"])*\")", sql)

    keywords = r"(ON|JOIN|LEFT\s+JOIN|INNER\s+JOIN|RIGHT\s+JOIN|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|UNION|INTERSECT|EXCEPT)"
    # AND/OR are added only where a glued keyword is unambiguous (after digits or ')').
    # They are deliberately left out of rule 2: its lazy alias match would split
    # real aliases such as 'AS brand' into 'AS br AND'.
    logic_keywords = r"(AND|OR|ON|JOIN|LEFT\s+JOIN|INNER\s+JOIN|RIGHT\s+JOIN|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|UNION|INTERSECT|EXCEPT)"

    sanitized_parts = []
    for part in parts:
        # If this part is a string literal, leave it completely untouched
        if part.startswith("'") or part.startswith('"'):
            sanitized_parts.append(part)
            continue
        
        # 1. Glued alias ending with digits + keyword (e.g. 'P2ON' -> 'P2 ON', 'T1JOIN' -> 'T1 JOIN', 'HP2ON' -> 'HP2 ON')
        # English words do not contain digits immediately preceding a SQL keyword
        s = re.sub(rf"\b([a-zA-Z]+[0-9]+){logic_keywords}\b", r"\1 \2", part, flags=re.IGNORECASE)

        # 2. Glued keyword after 'AS' alias (e.g. 'AS T1JOIN' -> 'AS T1 JOIN', 'AS empJOIN' -> 'AS emp JOIN')
        s = re.sub(rf"\b(AS\s+[a-zA-Z0-9_]+?){keywords}\b", r"\1 \2", s, flags=re.IGNORECASE)

        # 3. Glued keyword after closing parenthesis (e.g. ')JOIN' -> ') JOIN', ')AND' -> ') AND')
        s = re.sub(rf"\){logic_keywords}\b", r") \1", s, flags=re.IGNORECASE)

        # 4. Glued keyword after a numeric literal (e.g. 'tenant_id = 101AND' -> '101 AND', '2.5OR' -> '2.5 OR')
        # The leading \b stops it from splitting identifiers such as 'col_2or'.
        s = re.sub(rf"\b([0-9]+(?:\.[0-9]+)?){logic_keywords}\b", r"\1 \2", s, flags=re.IGNORECASE)

        sanitized_parts.append(s)

    return "".join(sanitized_parts)


def build_refinement_prompt(
    nl_query: str,
    failed_sql: str,
    error_msg: str,
    current_schema: str,
    supplemental_schema: Optional[str] = None,
    injected_rules: Optional[str] = None,
    dialect: str = "sqlite"
) -> str:
    """
    Constructs a targeted self-correction prompt showing the user question, 
    the failed SQL query, the exact compiler error, dialect name, and relevant schema tables.
    """
    dialect_name = prompts.get_dialect_display_name(dialect)
    rules_block = ""
    if injected_rules and str(injected_rules).strip():
        rules_block = f"\n/* Injected Authorization & Security Rules:\n{injected_rules}\n*/\n"

    extra_schema_block = ""
    if supplemental_schema and supplemental_schema.strip():
        extra_schema_block = f"\n/* Supplemental Database Tables:\n{supplemental_schema.strip()}\n*/"

    prompt = f"""Complete {dialect_name} query only with no explanation or markdown fences.

/* Given the following database schema:
{current_schema}
*/{extra_schema_block}{rules_block}

/* User Request: {nl_query} */

/* Previous Failed SQL Query:
{failed_sql}
*/

/* Database Compiler Error:
{error_msg}
*/

/* Corrective Instruction:
Analyze the database compiler error and the schema carefully. Fix the syntax, join, or column reference error.
Ensure the returned SQL query is syntactically valid for {dialect_name} and references only columns defined in the schema.
*/
SELECT"""

    return prompt


def clean_sql_output(raw_output: str) -> str:
    """
    Post-processes raw LLM completion into a clean, executable SQL string.
    """
    clean = raw_output.strip()
    if clean.startswith("```sql"):
        clean = clean[6:].strip()
    elif clean.startswith("```"):
        clean = clean[3:].strip()
    if clean.endswith("```"):
        clean = clean[:-3].strip()

    clean_upper = clean.upper()
    if not (clean_upper.startswith("SELECT") or clean_upper.startswith("WITH")):
        clean = "SELECT " + clean

    return clean


def execute_refinement_loop(
    nl_query: str,
    initial_sql: str,
    schema_meta: str,
    db_conn=None,
    full_schema_meta: Optional[str] = None,
    max_attempts: int = 2,
    injected_rules: Optional[str] = None,
    profiler=None,
    dialect: Optional[str] = None
) -> Tuple[str, bool, int, Dict[str, Any]]:
    """
    Autonomous Query Refinement Loop (Task 3).
    
    Workflow:
      1. Dry-run validates initial SQL with database compiler.
      2. If valid, returns immediately (0 refinement overhead).
      3. If invalid, enters iterative feedback loop up to max_attempts:
         - Inspects compiler error.
         - Scans cached full schema (<1ms) if missing entities detected.
         - Builds targeted refinement prompt.
         - Re-queries LLM and re-validates.
      4. Terminates early on first successful compilation or when max_attempts is reached.
      
    Returns:
        tuple: (final_sql, is_valid, attempts_count, refinement_metadata)
    """
    with time_block("Automated Query Refinement Loop (Task 3)", parent_summary=profiler.categories if profiler else None, category="Self-Correction Refinement Loop"):
        # Step 1: Validate initial SQL
        is_valid, error_msg, err_type = dry_run_validate(initial_sql, db_conn)
        trace("INITIAL SQL VALIDATION", {"sql": initial_sql, "valid": is_valid,
            "error": error_msg, "error_type": err_type,
            "validation_mode": "compiler dry-run" if db_conn is not None else "structural check"})
        
        refinement_stats = {
            "initial_valid": is_valid,
            "refinement_attempts": 0,
            "healed": False,
            "error_taxonomy": err_type if not is_valid else None,
            "initial_error": error_msg if not is_valid else None,
            "attempts_history": [],
            "total_refinement_tokens": 0
        }

        if is_valid:
            return initial_sql, True, 0, refinement_stats

        # Fast Deterministic Syntax Spacing Sanitizer (Compiler-Gated, 0 tokens)
        if err_type == "SYNTAX_ERROR":
            sanitized_sql = sanitize_sql_keyword_spacing(initial_sql)
            if sanitized_sql != initial_sql:
                is_sanitized_valid, s_err, s_type = dry_run_validate(sanitized_sql, db_conn)
                trace("SPACING SANITIZER OUTPUT", {"sql": sanitized_sql, "valid": is_sanitized_valid, "error": s_err})
                if is_sanitized_valid:
                    refinement_stats["healed"] = True
                    refinement_stats["healed_by_sanitizer"] = True
                    log_step("Initial SQL syntax healed by compiler-gated spacing sanitizer (0 tokens).", level="SUCCESS")
                    return sanitized_sql, True, 0, refinement_stats

        # Determine target SQL dialect
        if not dialect:
            if isinstance(db_conn, sqlite3.Connection):
                active_dialect = "sqlite"
            elif db_conn is not None:
                active_dialect = "mssql"
            else:
                active_dialect = "sqlite"
        else:
            active_dialect = dialect

        log_step(f"Dry-run validation failed on initial SQL ({err_type}): {error_msg}. Starting refinement loop ({active_dialect.upper()}, max {max_attempts} attempts)...", level="WARN")

        current_sql = initial_sql
        accumulated_schema = schema_meta
        supplemental_schema_str = ""

        # Step 2: Iterative Self-Correction
        for attempt in range(1, max_attempts + 1):
            with time_block(f"Refinement Attempt {attempt}/{max_attempts}", parent_summary=profiler.categories if profiler else None, category="Refinement - LLM Iteration"):
                refinement_stats["refinement_attempts"] = attempt
                
                # Check for missing entities in cached full schema (<1ms)
                _, missing_entities = categorize_compiler_error(error_msg)
                new_ddls = find_missing_schema_entities(missing_entities, full_schema_meta, accumulated_schema)
                if new_ddls:
                    supplemental_schema_str += "\n\n" + "\n\n".join(new_ddls)
                    accumulated_schema += "\n\n" + "\n\n".join(new_ddls)
                trace("REFINEMENT SCHEMA EXPANSION", {"attempt": attempt, "missing_entities": missing_entities, "added_schema": new_ddls})

                # Build targeted error-correction prompt
                refine_prompt = build_refinement_prompt(
                    nl_query=nl_query,
                    failed_sql=current_sql,
                    error_msg=error_msg,
                    current_schema=accumulated_schema,
                    supplemental_schema=supplemental_schema_str,
                    injected_rules=injected_rules,
                    dialect=active_dialect
                )

                # Query LLM
                try:
                    raw_correction, token_stats = llm.call_llm(refine_prompt, retries=2, profiler=profiler)
                    refinement_stats["total_refinement_tokens"] += token_stats.get("total_tokens", 0)
                    refined_sql = clean_sql_output(raw_correction)
                except Exception as call_err:
                    log_step(f"Refinement LLM call failed on attempt {attempt}: {call_err}", level="ERROR")
                    break

                # Re-validate with database compiler
                is_valid, error_msg, err_type = dry_run_validate(refined_sql, db_conn)
                if not is_valid and err_type == "SYNTAX_ERROR":
                    sanitized_refined = sanitize_sql_keyword_spacing(refined_sql)
                    if sanitized_refined != refined_sql:
                        s_valid, s_err, s_type = dry_run_validate(sanitized_refined, db_conn)
                        if s_valid:
                            is_valid = True
                            refined_sql = sanitized_refined
                            error_msg = ""
                            err_type = ""
                
                attempt_log = {
                    "attempt": attempt,
                    "generated_sql": refined_sql,
                    "is_valid": is_valid,
                    "error_msg": error_msg if not is_valid else None,
                    "tokens": token_stats.get("total_tokens", 0)
                }
                refinement_stats["attempts_history"].append(attempt_log)
                trace("REFINEMENT ATTEMPT OUTPUT", attempt_log)

                current_sql = refined_sql

                if is_valid:
                    refinement_stats["healed"] = True
                    log_step(f"[SUCCESS] Refinement Attempt {attempt} healed query successfully!", level="SUCCESS")
                    return current_sql, True, attempt, refinement_stats
                else:
                    log_step(f"Refinement Attempt {attempt} failed ({err_type}): {error_msg}", level="WARN")

        # Reached max attempts without healing
        log_step(f"Refinement loop exhausted {max_attempts} attempts without healing.", level="WARN")
        return current_sql, False, max_attempts, refinement_stats
