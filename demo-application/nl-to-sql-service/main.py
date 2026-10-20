import os
import sys
import platform
import re

# Prevent Python 3.12 Windows WMI query hang in platform module called by OpenAI SDK
if sys.platform == "win32":
    platform.win32_ver = lambda *args, **kwargs: ('10', '10.0.19045', 'SP0', 'Multiprocessor Free')
    platform.platform = lambda *args, **kwargs: 'Windows-10-10.0.19045-SP0'
    platform.system = lambda *args, **kwargs: 'Windows'
    platform.uname = lambda *args, **kwargs: platform.uname_result('Windows', 'PC', '10', '10.0.19045', 'AMD64')

from dotenv import load_dotenv

import database
import prompts
import llm
import schema_extractor
import refinement_loop
from entity_resolver import entity_resolver
from relationship_mapper import relationship_mapper
from exemplar_selector import exemplar_selector
from profiler import CycleProfiler, time_block, log_step, trace

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
    dialect: str = None,
    use_entity_resolution: bool = True,
    use_relationship_mapping: bool = True,
    use_exemplars: bool = True,
    num_exemplars: int = 2
) -> tuple[str, dict]:
    """
    Standard contract function for Member 1 translator engine with self-correction,
    contextual entity value grounding (Task 4A), multi-hop relationship mapping (Task 4B),
    and DAIL-style dynamic few-shot exemplar selection (Task 2.5).
    """
    full_schema_context = full_schema_meta or schema_meta
    trace("ENGINE INPUT", {"user_query": nl_query, "injected_rules": injected_rules,
        "use_pruning": use_pruning, "enable_refinement": enable_refinement,
        "use_entity_resolution": use_entity_resolution, "use_relationship_mapping": use_relationship_mapping,
        "use_exemplars": use_exemplars, "max_refinement_attempts": max_refinement_attempts})
    trace("FULL SCHEMA", full_schema_context)

    # Resolve target dialect
    active_dialect = dialect or refinement_loop.connection_dialect(db_conn)
    trace("SQL DIALECT", active_dialect)

    # 0A. Contextual Entity & Value Grounding (Task 4A)
    value_groundings_str = ""
    grounded_tables = set()
    if use_entity_resolution:
        with time_block("Contextual Entity & Value Grounding (Task 4A)", parent_summary=profiler.categories if profiler else None, category="Entity Resolution"):
            grounding_matches, grounded_tables = entity_resolver.resolve_grounded_entities(
                nl_query=nl_query,
                db_conn=db_conn,
                schema_meta=full_schema_context
            )
            value_groundings_str = entity_resolver.format_grounding_hints(grounding_matches)
    trace("ENTITY GROUNDING OUTPUT", {"enabled": use_entity_resolution,
        "grounded_tables": sorted(grounded_tables), "hints": value_groundings_str})

    # 0B. Relational Graph & Multi-Hop Steiner Bridge Resolution (Task 4B)
    join_paths_str = ""
    bridge_tables = set()
    if use_relationship_mapping:
        with time_block("Relational Graph & Bridge Discovery (Task 4B)", parent_summary=profiler.categories if profiler else None, category="Relationship Mapping"):
            candidate_terminals = set(grounded_tables)
            # Add table names mentioned in query (with word boundaries to avoid substring false positives)
            for t_match in re.findall(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[\w\.\-\]]+)', full_schema_context, re.IGNORECASE):
                t_clean = t_match.strip('`"[]').split('.')[-1]
                if re.search(rf'\b{re.escape(t_clean)}\b', nl_query, re.IGNORECASE):
                    candidate_terminals.add(t_clean)

            if len(candidate_terminals) >= 2:
                bridge_tables, join_paths = relationship_mapper.resolve_multi_hop_bridges(
                    terminal_tables=candidate_terminals,
                    schema_meta=full_schema_context,
                    db_conn=db_conn,
                    nl_query=nl_query
                )
                join_paths_str = relationship_mapper.format_canonical_join_skeleton(join_paths, nl_query=nl_query)

    trace("RELATIONSHIP MAPPING OUTPUT", {"enabled": use_relationship_mapping,
        "bridge_tables": sorted(bridge_tables), "join_hints": join_paths_str})
    # Combine protected tables to prevent accidental over-pruning in Task 1
    protected_tables = grounded_tables.union(bridge_tables)

    # 0C. Apply Task 1 Minimal-Context Schema Extraction
    if use_pruning:
        pruned_schema, pruning_stats = schema_extractor.extract_minimal_schema(
            nl_query, 
            schema_meta, 
            profiler=profiler,
            protected_tables=protected_tables if protected_tables else None
        )
        schema_meta = pruned_schema
        trace("SCHEMA PRUNING STATS", pruning_stats)
    trace("SCHEMA USED FOR GENERATION", schema_meta)

    # 0C.2 Subgraph Relational Join Paths (Task 4B / Stage 8A Precision Guidance)
    if use_relationship_mapping:
        with time_block("Relational Subgraph Path Resolution (Task 4B)", parent_summary=profiler.categories if profiler else None, category="Relationship Mapping"):
            selected_tables = set()
            for t_match in re.findall(r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[\w\.\-\]]+)', schema_meta, re.IGNORECASE):
                t_clean = t_match.strip('`"[]').split('.')[-1]
                selected_tables.add(t_clean)
            
            subgraph_hints = relationship_mapper.get_subgraph_join_paths(
                selected_tables=selected_tables,
                schema_meta=full_schema_context,
                nl_query=nl_query,
                db_conn=db_conn
            )
            if subgraph_hints:
                join_paths_str = subgraph_hints

    trace("FINAL JOIN HINTS", join_paths_str)
    # 0D. Dynamic Exemplar Selection (Task 2.5 - DAIL-SQL In-Context Learning)
    exemplars_str = ""
    if use_exemplars:
        with time_block("Dynamic Exemplar Selection (Task 2.5)", parent_summary=profiler.categories if profiler else None, category="Exemplar Retrieval"):
            retrieved_ex = exemplar_selector.retrieve(nl_query, k=num_exemplars)
            exemplars_str = exemplar_selector.format_exemplars(retrieved_ex)
    trace("EXEMPLAR OUTPUT", {"enabled": use_exemplars, "examples": exemplars_str})

    # 1. Build Prompt with CRP v2 (including Value Groundings, Join Paths & Strict Projection Rules)
    with time_block("Build Code Representation Prompt (CRP v2)", parent_summary=profiler.categories if profiler else None, category="Prompt Construction"):
        prompt_string = prompts.generate_crp_prompt(
            schema_meta, 
            nl_query, 
            injected_rules=injected_rules, 
            dialect=active_dialect,
            value_groundings=value_groundings_str,
            join_paths=join_paths_str,
            exemplars=exemplars_str
        )
        
    trace("FINAL ENGINE PROMPT", prompt_string)
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

    trace("INITIAL CLEANED SQL", final_sql)
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
        trace("REFINEMENT OUTPUT", ref_stats)
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

    trace("FINAL FULL SQL QUERY", final_sql)
    trace("ENGINE OUTPUT METADATA", token_stats)
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


