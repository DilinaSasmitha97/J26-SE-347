import os
from dotenv import load_dotenv

import database
import prompts
import llm
import schema_extractor
import refinement_loop
from profiler import CycleProfiler, time_block, log_step

# Load environment variables
load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower().strip()
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-3.5-flash"


def translate(
    nl_query: str, 
    schema_meta: str, 
    injected_rules: str = None, 
    profiler=None, 
    use_pruning: bool = True,
    enable_refinement: bool = True,
    max_refinement_attempts: int = 2,
    db_conn = None,
    full_schema_meta: str = None,
    dialect: str = None
) -> tuple[str, dict]:
    """
    Standard contract function for Member 1 translator engine with self-correction.
    Accepts:
        - nl_query: Natural language question
        - schema_meta: Database schema string (DDL / CREATE statements)
        - injected_rules: Security rules from Member 3
        - use_pruning: If True, uses Task 1 Minimal-Context Schema Extractor
        - enable_refinement: If True, uses Task 3 Automated Query Refinement Loop
        - max_refinement_attempts: Maximum self-correction iterations (default: 2)
        - db_conn: Active database connection for dry-run compiler validation
        - full_schema_meta: Full unpruned schema string for zero-delay cached expansion
        - dialect: Target SQL dialect ('sqlite', 'mssql', etc.)
    
    Returns:
        tuple[str, dict]: (clean_sql_query, token_stats_dict)
    """
    full_schema_context = full_schema_meta or schema_meta

    # Resolve target dialect
    import sqlite3
    if not dialect:
        if isinstance(db_conn, sqlite3.Connection):
            active_dialect = "sqlite"
        elif db_conn is not None:
            active_dialect = "mssql"
        else:
            active_dialect = "sqlite"
    else:
        active_dialect = dialect

    # 0. Apply Task 1 Minimal-Context Schema Extraction
    if use_pruning:
        pruned_schema, pruning_stats = schema_extractor.extract_minimal_schema(nl_query, schema_meta, profiler=profiler)
        schema_meta = pruned_schema

    # 1. Build Prompt
    with time_block("Build Code Representation Prompt (CRP)", parent_summary=profiler.categories if profiler else None, category="Prompt Construction"):
        prompt_string = prompts.generate_crp_prompt(schema_meta, nl_query, injected_rules=injected_rules, dialect=active_dialect)
        
    # 2. Call LLM via wrapper with retries & token tracking
    raw_output, token_stats = llm.call_llm(prompt_string, retries=3, profiler=profiler)
    
    # 3. Post-process raw output
    with time_block("Post-process raw output to extract clean SQL", parent_summary=profiler.categories if profiler else None, category="SQL Cleanup"):
        clean_output = raw_output.strip()
        if clean_output.startswith("```sql"):
            clean_output = clean_output[6:].strip()
        elif clean_output.startswith("```"):
            clean_output = clean_output[3:].strip()
        if clean_output.endswith("```"):
            clean_output = clean_output[:-3].strip()
            
        if not (clean_output.upper().startswith("SELECT") or clean_output.upper().startswith("WITH")):
            final_sql = "SELECT " + clean_output
        else:
            final_sql = clean_output

    # 4. Apply Task 3 Automated Query Refinement Loop (Self-Correction)
    if enable_refinement:
        final_sql, is_valid, attempts_count, ref_stats = refinement_loop.execute_refinement_loop(
            nl_query=nl_query,
            initial_sql=final_sql,
            schema_meta=schema_meta,
            db_conn=db_conn,
            full_schema_meta=full_schema_context,
            max_attempts=max_refinement_attempts,
            injected_rules=injected_rules,
            profiler=profiler,
            dialect=active_dialect
        )
        if isinstance(token_stats, dict):
            token_stats["refinement_attempts"] = attempts_count
            token_stats["healed"] = ref_stats.get("healed", False)
            token_stats["is_valid"] = is_valid
            token_stats["refinement_tokens"] = ref_stats.get("total_refinement_tokens", 0)
            token_stats["total_tokens"] = token_stats.get("total_tokens", 0) + ref_stats.get("total_refinement_tokens", 0)
    else:
        if isinstance(token_stats, dict):
            token_stats["refinement_attempts"] = 0
            token_stats["healed"] = False
            token_stats["is_valid"] = True

    return final_sql, token_stats


def generate_sql(schema_context: str, user_question: str, profiler=None, db_conn=None) -> str:
    """
    Generates SQL based on the provided schema context and user question.
    Backward-compatible wrapper returning only the SQL query string.
    """
    final_sql, _ = translate(nl_query=user_question, schema_meta=schema_context, profiler=profiler, db_conn=db_conn)
    return final_sql


def main():
    print(f"=== Phase 1-3: NL-to-SQL Engine with Self-Correction ({PROVIDER.capitalize()}) ===")
    
    # 1. Ask user for natural language query
    user_question = input("\nEnter your natural language question: ")
    if not user_question.strip():
        print("No question provided. Exiting.")
        return

    profiler = CycleProfiler("NL-to-SQL Single Cycle Execution")
    profiler.start()

    print("\n[1/3] Extracting Database Schema...")
    conn = None
    try:
        # Connect to DB and extract schema using CR(P) formatting
        conn = database.get_db_connection(profiler=profiler)
        schema_context = database.extract_schema_as_create_statements(conn, profiler=profiler)
        log_step("Database schema extracted successfully.")
    except Exception as e:
        log_step(f"Error accessing database: {e}", level="WARN")
        log_step("Note: To run fully, ensure SQL Server is running and DB_NAME is set in .env.", level="WARN")
        log_step("Falling back to a mock schema representation for prototype demonstration purposes...\n", level="WARN")
        schema_context = "CREATE TABLE [Employees] (\n    [Id] int NOT NULL,\n    [Name] nvarchar(50) NOT NULL,\n    [DepartmentId] int NOT NULL,\n    PRIMARY KEY ([Id])\n);"

    print("[2/3] Formatting Code Representation Prompt (CRP) & Pruning Schema...")
    active_model = GEMINI_MODEL if PROVIDER == "gemini" else GROQ_MODEL
    print(f"[3/3] Sending to {PROVIDER.capitalize()} LLM with Self-Correction ({active_model}, Temperature=0)...")
    
    try:
        final_sql, token_stats = translate(
            nl_query=user_question, 
            schema_meta=schema_context, 
            profiler=profiler,
            db_conn=conn,
            full_schema_meta=schema_context,
            enable_refinement=True,
            max_refinement_attempts=2
        )
        print("\n" + "="*40)
        print("        GENERATED SQL QUERY")
        print("="*40)
        print(final_sql)
        print("="*40)
        print(f"Tokens Used: {token_stats.get('total_tokens', 0)} ({token_stats.get('prompt_tokens', 0)} prompt / {token_stats.get('completion_tokens', 0)} completion)")
        print(f"Refinement Attempts: {token_stats.get('refinement_attempts', 0)} | Healed: {token_stats.get('healed', False)}\n")
    except Exception as e:
        log_step(f"API Request failed: {e}", level="ERROR")
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        profiler.finish()

if __name__ == "__main__":
    main()


