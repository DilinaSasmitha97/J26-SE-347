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

def generate_crp_prompt(schema_context: str, user_request: str, injected_rules: str = None, dialect: str = "sqlite") -> str:
    """
    Constructs the exact string representation for the LLM based on Phase 1 rules.
    Combines strict formatting, SQL schema context in comment blocks, optional authorization/security 
    rules placeholder (reserved for Member 3 integration), dialect hint, and the natural language request.
    """
    dialect_name = get_dialect_display_name(dialect)
    rules_block = ""
    if injected_rules and str(injected_rules).strip():
        rules_block = f"\n/* Injected Authorization & Security Rules:\n{injected_rules}\n*/\n"

    prompt = f"""Complete {dialect_name} query only and with no explanation

/* Given the following database schema:
{schema_context}
*/{rules_block}

/* Answer the following: {user_request} */
SELECT"""
    
    return prompt

