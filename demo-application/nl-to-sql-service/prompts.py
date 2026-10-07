"""
This file stores the prompt templates for the NL-to-SQL Engine 
using the Code Representation Prompt (CRP) strategy.
"""

def get_dialect_display_name(dialect: str = "sqlite") -> str:
    d = (dialect or "sqlite").lower().strip()
    if d in ["mssql", "sqlserver", "sql_server", "tsql"]:
        return "Microsoft SQL Server"
    elif d in ["sqlite", "sqlite3"]:
        return "SQLite"
    elif d in ["postgres", "postgresql"]:
        return "PostgreSQL"
    elif d in ["mysql"]:
        return "MySQL"
    return "SQL"

def generate_crp_prompt(
    schema_context: str, 
    user_request: str, 
    injected_rules: str = None, 
    dialect: str = "sqlite",
    value_groundings: str = None,
    join_paths: str = None,
    exemplars: str = None
) -> str:
    """
    Constructs the exact string representation for the LLM based on Phase 1-4 rules.
    Combines strict formatting, SQL schema context in comment blocks, optional authorization/security 
    rules placeholder (reserved for Member 3 integration), dialect hint, entity value groundings,
    multi-hop join paths, dynamic few-shot exemplars, and the natural language request.
    """
    dialect_name = get_dialect_display_name(dialect)
    rules_block = ""
    if injected_rules and str(injected_rules).strip():
        rules_block = f"\n/* Injected Authorization & Security Rules:\n{injected_rules}\n*/\n"

    grounding_block = ""
    if value_groundings and str(value_groundings).strip():
        grounding_block = f"\n{value_groundings.strip()}\n"

    join_block = ""
    if join_paths and str(join_paths).strip():
        join_block = f"\n{join_paths.strip()}\n"

    exemplars_block = ""
    if exemplars and str(exemplars).strip():
        exemplars_block = f"\n{exemplars.strip()}\n"

    prompt = f"""Complete {dialect_name} query only and with no explanation.
-- Rule 1: Project ONLY the exact columns requested in the question. Do not include unrequested auxiliary counts or metrics in SELECT.

/* Given the following database schema:
{schema_context}
*/{rules_block}{grounding_block}{join_block}{exemplars_block}

/* Answer the following: {user_request} */
SELECT"""
    
    return prompt
