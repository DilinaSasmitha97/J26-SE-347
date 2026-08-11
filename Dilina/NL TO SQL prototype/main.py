import os
from dotenv import load_dotenv

import database
import prompts
import llm
import schema_extractor
from profiler import CycleProfiler, time_block, log_step

# Load environment variables
load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower().strip()
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-3.5-flash"


def translate(nl_query: str, schema_meta: str, injected_rules: str = None, profiler=None, use_pruning: bool = True) -> tuple[str, dict]:
    """
    Standard contract function for Member 1 naive translator baseline.
    Accepts:
        - nl_query: Natural language question
        - schema_meta: Database schema string (DDL / CREATE statements)
        - injected_rules: Placeholder parameter reserved for Member 3 authorization & security rules
        - use_pruning: If True, uses Task 1 Minimal-Context Schema Extractor
    
    Returns:
        tuple[str, dict]: (clean_sql_query, token_stats_dict)
    """
    # 0. Apply Task 1 Minimal-Context Schema Extraction
    if use_pruning:
        pruned_schema, pruning_stats = schema_extractor.extract_minimal_schema(nl_query, schema_meta, profiler=profiler)
        schema_meta = pruned_schema

    # 1. Build Prompt
    with time_block("Build Code Representation Prompt (CRP)", parent_summary=profiler.categories if profiler else None, category="Prompt Construction"):
        prompt_string = prompts.generate_crp_prompt(schema_meta, nl_query, injected_rules=injected_rules)
        
    # 2. Call LLM via wrapper with retries & token tracking
    raw_output, token_stats = llm.call_llm(prompt_string, retries=3, profiler=profiler)
    
    # 3. Post-process raw output
    with time_block("Post-process raw output to extract clean SQL", parent_summary=profiler.categories if profiler else None, category="SQL Cleanup"):
        clean_output = raw_output.strip()
        if clean_output.startswith("```sql"):
            clean_output = clean_output[6:].strip()
        if clean_output.endswith("```"):
            clean_output = clean_output[:-3].strip()
            
        if not clean_output.upper().startswith("SELECT"):
            final_sql = "SELECT " + clean_output
        else:
            final_sql = clean_output
            
    return final_sql, token_stats


def generate_sql(schema_context: str, user_question: str, profiler=None) -> str:
    """
    Generates SQL based on the provided schema context and user question.
    Backward-compatible wrapper returning only the SQL query string.
    """
    final_sql, _ = translate(nl_query=user_question, schema_meta=schema_context, profiler=profiler)
    return final_sql


def main():
    print(f"=== Phase 1: NL-to-SQL Engine ({PROVIDER.capitalize()}) ===")
    
    # 1. Ask user for natural language query
    user_question = input("\nEnter your natural language question: ")
    if not user_question.strip():
        print("No question provided. Exiting.")
        return

    profiler = CycleProfiler("NL-to-SQL Single Cycle Execution")
    profiler.start()

    print("\n[1/3] Extracting Database Schema...")
    try:
        # Connect to DB and extract schema using CR(P) formatting
        conn = database.get_db_connection(profiler=profiler)
        schema_context = database.extract_schema_as_create_statements(conn, profiler=profiler)
        with profiler.step("Closing Database Connection", category="Database Cleanup"):
            conn.close()
        log_step("Database schema extracted successfully.")
    except Exception as e:
        log_step(f"Error accessing database: {e}", level="WARN")
        log_step("Note: To run fully, ensure SQL Server is running and DB_NAME is set in .env.", level="WARN")
        log_step("Falling back to a mock schema representation for prototype demonstration purposes...\n", level="WARN")
        # Mock schema just in case the user runs it without setting up their local DB first
        schema_context = "CREATE TABLE [Employees] (\n    [Id] int NOT NULL,\n    [Name] nvarchar(50) NOT NULL,\n    [DepartmentId] int NOT NULL,\n    PRIMARY KEY ([Id])\n);"

    print("[2/3] Formatting Code Representation Prompt (CRP)...")
    active_model = GEMINI_MODEL if PROVIDER == "gemini" else GROQ_MODEL
    print(f"[3/3] Sending to {PROVIDER.capitalize()} LLM ({active_model}, Temperature=0)...")
    
    try:
        final_sql, token_stats = translate(user_question, schema_context, profiler=profiler)
        print("\n" + "="*40)
        print("        GENERATED SQL QUERY")
        print("="*40)
        print(final_sql)
        print("="*40)
        print(f"Tokens Used: {token_stats.get('total_tokens', 0)} ({token_stats.get('prompt_tokens', 0)} prompt / {token_stats.get('completion_tokens', 0)} completion)\n")
    except Exception as e:
        log_step(f"API Request failed: {e}", level="ERROR")
    finally:
        profiler.finish()

if __name__ == "__main__":
    main()


