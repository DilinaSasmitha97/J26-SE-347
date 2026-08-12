import os
import json
import sqlite3
import argparse
from database import get_sqlite_connection, extract_sqlite_schema_as_create_statements
from main import translate
from profiler import CycleProfiler, time_block, log_step

def get_sql_difficulty(sql: dict) -> str:
    """
    Evaluates SQL query complexity level (easy, medium, hard, extra) based on Spider benchmark rules.
    """
    if not isinstance(sql, dict):
        return "easy"
        
    from_tables = sql.get('from', {}).get('table_units', []) if isinstance(sql.get('from'), dict) else []
    joins = max(0, len(from_tables) - 1)
    
    select_units = sql.get('select', [False, []])[1] if isinstance(sql.get('select'), list) and len(sql.get('select')) > 1 else []
    aggs = sum(1 for unit in select_units if isinstance(unit, list) and len(unit) > 0 and unit[0] > 0)
    
    has_where = len(sql.get('where', [])) > 0
    has_group = len(sql.get('groupBy', [])) > 0
    has_having = len(sql.get('having', [])) > 0
    has_order = len(sql.get('orderBy', [])) > 0
    has_limit = sql.get('limit') is not None
    has_set_op = any(sql.get(op) is not None for op in ['intersect', 'union', 'except'])
    
    total_clauses = (1 if has_where else 0) + (1 if has_group else 0) + (1 if has_having else 0) + (1 if has_order else 0) + (1 if has_limit else 0) + (1 if has_set_op else 0)
    
    if joins == 0 and total_clauses <= 1 and aggs <= 1 and not has_set_op:
        return 'easy'
    elif joins <= 1 and total_clauses <= 2 and not has_set_op:
        return 'medium'
    elif joins <= 2 and total_clauses <= 4:
        return 'hard'
    else:
        return 'extra'


def categorize_failure(predicted_sql: str, gold_sql: str, pred_exec_error: str = None) -> str:
    """
    Categorizes NL-to-SQL failure modes into specific taxonomy categories.
    """
    if pred_exec_error:
        err_lower = pred_exec_error.lower()
        if "no such column" in err_lower or "no such table" in err_lower:
            return "SCHEMA_LINKING_ERROR"
        return "SYNTAX_ERROR"
        
    gold_upper = gold_sql.upper()
    pred_upper = predicted_sql.upper() if predicted_sql else ""
    
    # Check for JOIN mismatch
    if "JOIN" in gold_upper and "JOIN" not in pred_upper:
        return "JOIN_ERROR"
        
    # Check for Aggregation / Grouping mismatch
    agg_keywords = ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN(", "GROUP BY"]
    if any(k in gold_upper for k in agg_keywords) and not any(k in pred_upper for k in agg_keywords):
        return "AGGREGATION_ERROR"
        
    return "RESULT_MISMATCH"


def evaluate_spider(dataset_path: str, max_samples: int = None, difficulty: str = "all", model_name: str = None, delay: float = 0.0) -> dict:
    diff_filter = difficulty.lower().strip() if difficulty else "all"
    log_step(f"Loading Spider dataset from {dataset_path} (Filter: difficulty='{diff_filter}', model='{model_name or 'default'}', delay={delay}s)...")
    
    if not os.path.exists(dataset_path):
        log_step(f"Dataset file not found: {dataset_path}", level="ERROR")
        return {}
        
    with open(dataset_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
        
    # Apply Complexity / Difficulty Filtering
    if diff_filter != "all":
        filtered_data = [item for item in raw_data if get_sql_difficulty(item.get('sql', {})) == diff_filter]
    else:
        filtered_data = raw_data
        
    total_available_matching = len(filtered_data)
    boundary_notice = None
    
    if max_samples is not None:
        if total_available_matching < max_samples:
            boundary_notice = f"Requested {max_samples} questions for difficulty '{diff_filter}', but only {total_available_matching} matching questions exist in the dataset. Evaluating all {total_available_matching} available questions."
            log_step(f"[NOTICE] {boundary_notice}", level="WARN")
            data = filtered_data
        else:
            data = filtered_data[:max_samples]
    else:
        data = filtered_data
        
    total = len(data)
    correct = 0
    errors = 0
    
    total_tokens_all = 0
    total_prompt_tokens_all = 0
    total_completion_tokens_all = 0
    
    taxonomy_counts = {
        "SCHEMA_LINKING_ERROR": 0,
        "SYNTAX_ERROR": 0,
        "JOIN_ERROR": 0,
        "AGGREGATION_ERROR": 0,
        "RESULT_MISMATCH": 0
    }
    
    base_dir = os.path.dirname(dataset_path)
    db_dir = os.path.join(base_dir, "database")
    
    eval_profiler = CycleProfiler(f"Spider Evaluation ({total} samples, difficulty='{diff_filter}')")
    eval_profiler.start()
    
    log_step(f"Starting evaluation of {total} queries (Available matching: {total_available_matching})...\n")
    
    for idx, item in enumerate(data):
        question = item['question']
        gold_sql = item['query']
        db_id = item['db_id']
        sample_diff = get_sql_difficulty(item.get('sql', {}))
        
        db_path = os.path.join(db_dir, db_id, f"{db_id}.sqlite")
        
        print(f"\n[{idx+1}/{total}] DB: {db_id} | Complexity: {sample_diff.upper()} | Q: {question}")
        
        sample_profiler = CycleProfiler(f"Sample {idx+1}/{total} [{db_id}]")
        sample_profiler.start()
        
        pred_exec_error = None
        predicted_sql = ""
        token_stats = {}
        
        try:
            # 1. Connect and extract schema
            conn = get_sqlite_connection(db_path, profiler=sample_profiler)
            conn.text_factory = lambda b: b.decode('utf-8', errors='ignore')
            schema = extract_sqlite_schema_as_create_statements(conn, profiler=sample_profiler)
            
            # 2. Generate SQL with translate contract stub
            predicted_sql, token_stats = translate(question, schema, model_name=model_name, profiler=sample_profiler)
            
            p_tok = token_stats.get('prompt_tokens', 0)
            c_tok = token_stats.get('completion_tokens', 0)
            t_tok = token_stats.get('total_tokens', 0)
            
            total_prompt_tokens_all += p_tok
            total_completion_tokens_all += c_tok
            total_tokens_all += t_tok
            
            print(f"    Predicted SQL: {predicted_sql.strip()}")
            print(f"    Gold SQL:      {gold_sql.strip()}")
            print(f"    Tokens:        {t_tok} total ({p_tok} prompt / {c_tok} completion)")
            
            # 3. Execute both queries
            cursor = conn.cursor()
            
            # Execute predicted
            with time_block("SQLite Execution (Predicted Query)", parent_summary=sample_profiler.categories, category="Predicted Query Execution"):
                try:
                    cursor.execute(predicted_sql)
                    pred_results = cursor.fetchall()
                except Exception as e:
                    pred_exec_error = str(e)
                    log_step(f"    [!] Predicted execution failed: {e}", level="WARN")
                    pred_results = None
                    
            # Execute gold
            with time_block("SQLite Execution (Gold Query)", parent_summary=sample_profiler.categories, category="Gold Query Execution"):
                try:
                    cursor.execute(gold_sql)
                    gold_results = cursor.fetchall()
                except Exception as e:
                    log_step(f"    [!] Gold execution failed: {e}", level="WARN")
                    gold_results = None
                    
            # 4. Compare datasets (Execution Accuracy) & failure categorization
            with time_block("Results Comparison & Failure Taxonomy", parent_summary=sample_profiler.categories, category="Result Set Comparison"):
                if pred_results is not None and gold_results is not None:
                    pred_set = set([str(r) for r in pred_results])
                    gold_set = set([str(r) for r in gold_results])
                    
                    if pred_set == gold_set:
                        log_step("    [MATCH] Results are identical", level="SUCCESS")
                        correct += 1
                    else:
                        cat = categorize_failure(predicted_sql, gold_sql, pred_exec_error)
                        taxonomy_counts[cat] = taxonomy_counts.get(cat, 0) + 1
                        log_step(f"    [MISMATCH] Results differ | Category: {cat}", level="INFO")
                else:
                    cat = categorize_failure(predicted_sql, gold_sql, pred_exec_error)
                    taxonomy_counts[cat] = taxonomy_counts.get(cat, 0) + 1
                    log_step(f"    [MISMATCH] Execution Error | Category: {cat}", level="WARN")
                
            conn.close()
            
        except Exception as e:
            log_step(f"    [!] Evaluation error: {e}", level="ERROR")
            errors += 1
        finally:
            sample_profiler.finish()
            for cat, dur in sample_profiler.categories.items():
                eval_profiler.categories[cat] = eval_profiler.categories.get(cat, 0.0) + dur
            
        print("-" * 50)
        if delay > 0:
            import time
            time.sleep(delay)
        
    accuracy = (correct / total) * 100 if total > 0 else 0
    avg_tokens = (total_tokens_all / total) if total > 0 else 0
    avg_prompt_tokens = (total_prompt_tokens_all / total) if total > 0 else 0
    avg_completion_tokens = (total_completion_tokens_all / total) if total > 0 else 0
    
    summary_report = {
        "model_name": model_name or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "difficulty_filter": diff_filter,
        "requested_max_samples": max_samples,
        "available_matching_count": total_available_matching,
        "total_evaluated": total,
        "boundary_notice": boundary_notice,
        "correct": correct,
        "errors": errors,
        "execution_accuracy_pct": round(accuracy, 2),
        "total_tokens": total_tokens_all,
        "avg_tokens_per_query": round(avg_tokens, 1),
        "avg_prompt_tokens": round(avg_prompt_tokens, 1),
        "avg_completion_tokens": round(avg_completion_tokens, 1),
        "failure_taxonomy": taxonomy_counts
    }
    
    # Save taxonomy report to file
    report_file = os.path.join(os.path.dirname(__file__), "failure_taxonomy.json")
    with open(report_file, "w", encoding="utf-8") as rf:
        json.dump(summary_report, rf, indent=2)
    log_step(f"Exported failure taxonomy report to {report_file}")

    print(f"\n=== Evaluation Complete ===")
    print(f"Model                  : {summary_report['model_name']}")
    print(f"Difficulty Filter      : {diff_filter.upper()}")
    print(f"Total Available Matching: {total_available_matching}")
    print(f"Total Evaluated        : {total}")
    if boundary_notice:
        print(f" Notice                : {boundary_notice}")
    print(f"Correct (Match)        : {correct}")
    print(f"Evaluation Errors      : {errors}")
    print(f"Execution Accuracy     : {accuracy:.2f}%")
    print(f"Avg Tokens per Query   : {avg_tokens:.1f} ({avg_prompt_tokens:.1f} in / {avg_completion_tokens:.1f} out)")
    print("-" * 50)
    print("Failure Taxonomy Breakdown:")
    for f_cat, f_count in taxonomy_counts.items():
        print(f"  • {f_cat:<25}: {f_count}")
    print("=" * 50)
    
    eval_profiler.finish()
    return summary_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spider Benchmark Evaluation Harness with Complexity Filtering")
    parser.add_argument("-n", "--samples", type=int, default=10, help="Maximum number of samples to evaluate (default: 10)")
    parser.add_argument("-d", "--difficulty", type=str, default="all", choices=["all", "easy", "medium", "hard", "extra"], help="Query complexity level filter (easy, medium, hard, extra, all)")
    parser.add_argument("-m", "--model", type=str, default=None, help="Groq model override (e.g. mixtral-8x7b-32768, llama-3.1-8b-instant, llama-3.3-70b-versatile)")
    parser.add_argument("--delay", type=float, default=0.0, help="Pause delay in seconds between queries to prevent API rate limits")
    parser.add_argument("--dataset", type=str, default=r"D:\spider_data\dev.json", help="Path to Spider dev.json dataset")
    
    args = parser.parse_args()
    
    # Auto-apply 3.0s rate limit delay for OpenRouter free models if delay not explicitly passed
    run_delay = args.delay
    if run_delay == 0.0 and args.model and (":" in args.model or "/" in args.model):
        run_delay = 3.0
        
    evaluate_spider(dataset_path=args.dataset, max_samples=args.samples, difficulty=args.difficulty, model_name=args.model, delay=run_delay)



