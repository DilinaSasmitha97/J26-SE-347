import os
import sys
import platform

# Prevent Python 3.12 Windows WMI query hang in platform module called by OpenAI SDK
if sys.platform == "win32":
    platform.win32_ver = lambda *args, **kwargs: ('10', '10.0.19045', 'SP0', 'Multiprocessor Free')
    platform.platform = lambda *args, **kwargs: 'Windows-10-10.0.19045-SP0'
    platform.system = lambda *args, **kwargs: 'Windows'
    platform.uname = lambda *args, **kwargs: platform.uname_result('Windows', 'PC', '10', '10.0.19045', 'AMD64')

import json
import sqlite3
import argparse
import time
import itertools
import random
from collections import defaultdict
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


def permute_tuple(element: tuple, perm: tuple) -> tuple:
    assert len(element) == len(perm)
    return tuple([element[i] for i in perm])


def unorder_row(row: tuple) -> tuple:
    return tuple(sorted(row, key=lambda x: str(x) + str(type(x))))


def quick_rej(result1: list, result2: list, order_matters: bool) -> bool:
    s1 = [unorder_row(row) for row in result1]
    s2 = [unorder_row(row) for row in result2]
    if order_matters:
        return s1 == s2
    else:
        return set(s1) == set(s2)


def multiset_eq(l1: list, l2: list) -> bool:
    if len(l1) != len(l2):
        return False
    d = defaultdict(int)
    for e in l1:
        d[e] += 1
    for e in l2:
        d[e] -= 1
        if d[e] < 0:
            return False
    return True


def get_constraint_permutation(tab1_sets_by_columns: list, result2: list):
    num_cols = len(result2[0])
    perm_constraints = [{i for i in range(num_cols)} for _ in range(num_cols)]
    if num_cols <= 3:
        return itertools.product(*perm_constraints)

    # Sample up to 20 rows and constrain the space of permutations
    sample_size = min(20, len(result2))
    for row in (random.sample(result2, sample_size) if len(result2) > 0 else []):
        for tab1_col in range(num_cols):
            for tab2_col in set(perm_constraints[tab1_col]):
                if row[tab2_col] not in tab1_sets_by_columns[tab1_col]:
                    perm_constraints[tab1_col].remove(tab2_col)
    return itertools.product(*perm_constraints)


def yale_result_eq(result1: list, result2: list, order_matters: bool) -> bool:
    """
    Evaluates execution equivalence according to the official Yale test-suite-sql-eval standard
    (Zhong et al., EMNLP 2020 / taoyds/test-suite-sql-eval).
    
    result1: gold query execution results (list of tuples)
    result2: predicted query execution results (list of tuples)
    order_matters: True if gold query specified ORDER BY, False otherwise
    """
    if len(result1) == 0 and len(result2) == 0:
        return True
    if len(result1) != len(result2):
        return False
    num_cols = len(result1[0])
    if len(result2[0]) != num_cols:
        return False
    if not quick_rej(result1, result2, order_matters):
        return False

    tab1_sets_by_columns = [{row[i] for row in result1} for i in range(num_cols)]
    for perm in get_constraint_permutation(tab1_sets_by_columns, result2):
        if len(perm) != len(set(perm)):
            continue
        if num_cols == 1:
            result2_perm = result2
        else:
            result2_perm = [permute_tuple(element, perm) for element in result2]
        if order_matters:
            if result1 == result2_perm:
                return True
        else:
            if set(result1) == set(result2_perm) and multiset_eq(result1, result2_perm):
                return True
    return False


def evaluate_spider(dataset_path: str, max_samples: int = None, difficulty: str = "all", delay: float = 0.0, enable_refinement: bool = True) -> dict:
    diff_filter = difficulty.lower().strip() if difficulty else "all"
    log_step(f"Loading Spider dataset from {dataset_path} (Filter: difficulty='{diff_filter}', Refinement={'ENABLED' if enable_refinement else 'DISABLED'})...")
    
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
    strict_correct = 0
    yale_correct = 0
    errors = 0
    healed_total = 0
    refinement_attempts_total = 0
    refinement_tokens_total = 0
    predictions_log = []
    
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
    
    diff_stats = {
        "easy": {"total": 0, "strict_correct": 0, "yale_correct": 0},
        "medium": {"total": 0, "strict_correct": 0, "yale_correct": 0},
        "hard": {"total": 0, "strict_correct": 0, "yale_correct": 0},
        "extra": {"total": 0, "strict_correct": 0, "yale_correct": 0},
    }
    
    base_dir = os.path.dirname(dataset_path)
    db_dir = os.path.join(base_dir, "database")
    
    eval_profiler = CycleProfiler(f"Spider Evaluation ({total} samples, difficulty='{diff_filter}', refinement={enable_refinement})")
    eval_profiler.start()
    
    log_step(f"Starting evaluation of {total} queries (Available matching: {total_available_matching})...\n")
    
    for idx, item in enumerate(data):
        question = item['question']
        gold_sql = item['query']
        db_id = item['db_id']
        sample_diff = get_sql_difficulty(item.get('sql', {}))
        if sample_diff in diff_stats:
            diff_stats[sample_diff]["total"] += 1
        
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
            schema = extract_sqlite_schema_as_create_statements(conn, profiler=sample_profiler)
            
            # 2. Generate SQL with translate contract stub & optional refinement
            predicted_sql, token_stats = translate(
                nl_query=question, 
                schema_meta=schema, 
                profiler=sample_profiler,
                enable_refinement=enable_refinement,
                max_refinement_attempts=2,
                db_conn=conn,
                full_schema_meta=schema
            )
            
            p_tok = token_stats.get('prompt_tokens', 0)
            c_tok = token_stats.get('completion_tokens', 0)
            t_tok = token_stats.get('total_tokens', 0)
            
            if token_stats.get("healed", False):
                healed_total += 1
            refinement_attempts_total += token_stats.get("refinement_attempts", 0)
            refinement_tokens_total += token_stats.get("refinement_tokens", 0)
            
            total_prompt_tokens_all += p_tok
            total_completion_tokens_all += c_tok
            total_tokens_all += t_tok
            
            print(f"    Predicted SQL: {predicted_sql.strip()}")
            print(f"    Gold SQL:      {gold_sql.strip()}")
            print(f"    Tokens:        {t_tok} total ({p_tok} prompt / {c_tok} completion) | Refinement: {token_stats.get('refinement_attempts', 0)} attempts (Healed: {token_stats.get('healed', False)})")
            
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
                order_matters = 'order by' in gold_sql.lower()
                is_strict = False
                is_yale = False

                if pred_results is not None and gold_results is not None:
                    # Legacy strict set match (for historical cross-stage comparability)
                    pred_set = set([str(r) for r in pred_results])
                    gold_set = set([str(r) for r in gold_results])
                    is_strict = (pred_set == gold_set)

                    # Official Yale test-suite-sql-eval match (multiset + order_matters + column permutation)
                    is_yale = yale_result_eq(gold_results, pred_results, order_matters=order_matters)

                    if is_strict:
                        strict_correct += 1
                        if sample_diff in diff_stats:
                            diff_stats[sample_diff]["strict_correct"] += 1

                    if is_yale:
                        yale_correct += 1
                        if sample_diff in diff_stats:
                            diff_stats[sample_diff]["yale_correct"] += 1
                        if is_strict:
                            log_step("    [YALE & STRICT MATCH] Results strictly identical", level="SUCCESS")
                        else:
                            log_step("    [YALE EQUIVALENT] Permutation / semantic match (Yale EX Passed)", level="SUCCESS")
                    else:
                        cat = categorize_failure(predicted_sql, gold_sql, pred_exec_error)
                        taxonomy_counts[cat] = taxonomy_counts.get(cat, 0) + 1
                        log_step(f"    [MISMATCH] Results differ | Category: {cat}", level="INFO")
                else:
                    cat = categorize_failure(predicted_sql, gold_sql, pred_exec_error)
                    taxonomy_counts[cat] = taxonomy_counts.get(cat, 0) + 1
                    log_step(f"    [MISMATCH] Execution Error | Category: {cat}", level="WARN")

                predictions_log.append({
                    "index": idx + 1,
                    "db_id": db_id,
                    "difficulty": sample_diff,
                    "question": question,
                    "gold_sql": gold_sql,
                    "predicted_sql": predicted_sql,
                    "strict_match": is_strict,
                    "yale_match": is_yale,
                    "tokens": t_tok,
                    "healed": token_stats.get("healed", False)
                })
                
            conn.close()
            
        except Exception as e:
            log_step(f"    [!] Evaluation error: {e}", level="ERROR")
            errors += 1
        finally:
            sample_profiler.finish()
            for cat, dur in sample_profiler.categories.items():
                eval_profiler.categories[cat] = eval_profiler.categories.get(cat, 0.0) + dur
            
        print("-" * 50)
        if delay > 0 and idx < total - 1:
            time.sleep(delay)
        
    strict_accuracy = (strict_correct / total) * 100 if total > 0 else 0
    yale_accuracy = (yale_correct / total) * 100 if total > 0 else 0
    avg_tokens = (total_tokens_all / total) if total > 0 else 0
    avg_prompt_tokens = (total_prompt_tokens_all / total) if total > 0 else 0
    avg_completion_tokens = (total_completion_tokens_all / total) if total > 0 else 0
    
    summary_report = {
        "model_name": os.getenv("OPENROUTER_MODEL") if os.getenv("LLM_PROVIDER") == "openrouter" else os.getenv("GROQ_MODEL", "qwen/qwen-2.5-coder-32b-instruct"),
        "difficulty_filter": diff_filter,
        "refinement_enabled": enable_refinement,
        "requested_max_samples": max_samples,
        "available_matching_count": total_available_matching,
        "total_evaluated": total,
        "boundary_notice": boundary_notice,
        "yale_execution_accuracy_pct": round(yale_accuracy, 2),
        "yale_correct": yale_correct,
        "strict_execution_accuracy_pct": round(strict_accuracy, 2),
        "strict_correct": strict_correct,
        "errors": errors,
        "healed_queries": healed_total,
        "refinement_attempts_total": refinement_attempts_total,
        "refinement_tokens_total": refinement_tokens_total,
        "total_tokens": total_tokens_all,
        "avg_tokens_per_query": round(avg_tokens, 1),
        "avg_prompt_tokens": round(avg_prompt_tokens, 1),
        "avg_completion_tokens": round(avg_completion_tokens, 1),
        "difficulty_breakdown": {
            d: {
                "total": s["total"],
                "yale_correct": s["yale_correct"],
                "yale_accuracy_pct": round((s["yale_correct"] / s["total"] * 100) if s["total"] > 0 else 0, 2),
                "strict_correct": s["strict_correct"],
                "strict_accuracy_pct": round((s["strict_correct"] / s["total"] * 100) if s["total"] > 0 else 0, 2)
            } for d, s in diff_stats.items() if s["total"] > 0
        },
        "failure_taxonomy": taxonomy_counts
    }
    
    # Save taxonomy report to file
    report_file = os.path.join(os.path.dirname(__file__), "failure_taxonomy.json")
    with open(report_file, "w", encoding="utf-8") as rf:
        json.dump(summary_report, rf, indent=2)
    log_step(f"Exported failure taxonomy report to {report_file}")

    # Export Yale-format predictions file (for official taoyds/test-suite-sql-eval verification)
    pred_sql_file = os.path.join(os.path.dirname(__file__), "predictions_eval.sql")
    with open(pred_sql_file, "w", encoding="utf-8") as pf:
        for p in predictions_log:
            single_line_sql = " ".join(p["predicted_sql"].split()) if p["predicted_sql"] else "SELECT 1"
            pf.write(f"{single_line_sql}\t{p['db_id']}\n")
    log_step(f"Exported Yale-format predictions to {pred_sql_file}")

    # Export detailed predictions JSON
    pred_log_file = os.path.join(os.path.dirname(__file__), "predictions_detailed.json")
    with open(pred_log_file, "w", encoding="utf-8") as plf:
        json.dump(predictions_log, plf, indent=2)
    log_step(f"Exported detailed predictions log to {pred_log_file}")

    print(f"\n=== Evaluation Complete (100% Yale test-suite-sql-eval Standard) ===")
    print(f"Model                                      : {summary_report['model_name']}")
    print(f"Difficulty Filter                          : {diff_filter.upper()}")
    print(f"Refinement Loop                            : {'ENABLED' if enable_refinement else 'DISABLED'}")
    print(f"Total Available Matching                   : {total_available_matching}")
    print(f"Total Evaluated                            : {total}")
    if boundary_notice:
        print(f" Notice                                    : {boundary_notice}")
    print(f"Yale Execution Accuracy (Official Primary) : {yale_accuracy:.2f}% ({yale_correct}/{total})")
    print(f"Strict Set Accuracy (Legacy Baseline)      : {strict_accuracy:.2f}% ({strict_correct}/{total})")
    print(f"Evaluation Errors                          : {errors}")
    print(f"Healed by Refinement                       : {healed_total}")
    print(f"Avg Tokens per Query                       : {avg_tokens:.1f} ({avg_prompt_tokens:.1f} in / {avg_completion_tokens:.1f} out)")
    if enable_refinement and healed_total > 0:
        print(f"Refinement Tokens Total                    : {refinement_tokens_total} ({refinement_attempts_total} total attempts)")
    print("-" * 50)
    print("Difficulty Tier Breakdown (Yale EX / Strict EX):")
    for d_name, d_data in summary_report.get("difficulty_breakdown", {}).items():
        print(f"  • {d_name.capitalize():<8}: Yale={d_data['yale_correct']}/{d_data['total']} ({d_data['yale_accuracy_pct']}%) | Strict={d_data['strict_correct']}/{d_data['total']} ({d_data['strict_accuracy_pct']}%)")
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
    parser.add_argument("-m", "--model", type=str, default=None, help="Model name to evaluate (e.g. llama-3.3-70b-versatile, llama-3.1-8b-instant)")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds between sample evaluation cycles")
    parser.add_argument("--dataset", type=str, default=r"D:\spider_data\dev.json", help="Path to Spider dev.json dataset")
    parser.add_argument("--refine", dest="refine", action="store_true", default=True, help="Enable Task 3 automated query refinement loop (default: True)")
    parser.add_argument("--no-refine", dest="refine", action="store_false", help="Disable Task 3 query refinement loop for baseline A/B comparison")
    
    args = parser.parse_args()
    if args.model:
        import main
        main.GROQ_MODEL = args.model
    evaluate_spider(
        dataset_path=args.dataset, 
        max_samples=args.samples, 
        difficulty=args.difficulty, 
        delay=args.delay,
        enable_refinement=args.refine
    )



