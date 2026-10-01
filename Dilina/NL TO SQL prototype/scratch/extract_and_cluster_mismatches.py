import re
import json
import os
import sqlite3

LOG_PATH = r"C:\Users\USER\.gemini\antigravity-ide\brain\41ea6217-4925-49a6-aa04-40a1e22a4743\.system_generated\tasks\task-1469.log"
DEV_JSON_PATH = r"D:\spider_data\dev.json"
DB_DIR = r"D:\spider_data\database"
OUTPUT_JSON = r"D:\Secure Multi-Tenant Natural Language Interface for Database Querying\Dilina\NL TO SQL prototype\mismatches_stage4_1.json"

def parse_log():
    print(f"Reading log from {LOG_PATH}...")
    with open(LOG_PATH, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Split by sample markers: [1/1034], [2/1034], etc.
    sample_blocks = re.split(r'\[(\d+)/1034\]\s+DB:\s+([\w\.\-]+)\s+\|\s+Complexity:\s+(\w+)\s+\|\s+Q:\s+(.*?)\n', content)
    
    print(f"Found {len(sample_blocks)} raw tokens from split")
    
    # Each sample will have 5 parts in the split list:
    # 0: header before first sample
    # Then for each sample: (idx_str, db_id, complexity, question, body)
    
    samples = []
    i = 1
    while i < len(sample_blocks):
        sample_idx = int(sample_blocks[i])
        db_id = sample_blocks[i+1].strip()
        complexity = sample_blocks[i+2].strip()
        question = sample_blocks[i+3].strip()
        body = sample_blocks[i+4]
        i += 5

        # Check if this sample had a RESULT_MISMATCH
        if "[MISMATCH] Results differ | Category: RESULT_MISMATCH" in body:
            # Extract Predicted SQL
            pred_match = re.search(r'Predicted SQL:\s*(.*?)(?=\n\s*Gold SQL:|\n\s*Tokens:)', body, re.DOTALL)
            predicted_sql = pred_match.group(1).strip() if pred_match else ""
            
            # Extract Gold SQL
            gold_match = re.search(r'Gold SQL:\s*(.*?)(?=\n\s*Tokens:)', body, re.DOTALL)
            gold_sql = gold_match.group(1).strip() if gold_match else ""

            samples.append({
                "sample_idx": sample_idx,
                "dev_json_idx": sample_idx - 1,
                "db_id": db_id,
                "complexity": complexity,
                "question": question,
                "predicted_sql": predicted_sql,
                "gold_sql": gold_sql
            })

    print(f"Extracted {len(samples)} RESULT_MISMATCH samples.")
    return samples

def analyze_mismatch(sample):
    db_id = sample["db_id"]
    pred_sql = sample["predicted_sql"]
    gold_sql = sample["gold_sql"]
    q = sample["question"]
    
    db_path = os.path.join(DB_DIR, db_id, f"{db_id}.sqlite")
    
    analysis = {
        "cluster": "UNKNOWN",
        "details": "",
        "pred_row_count": None,
        "gold_row_count": None,
        "pred_results_sample": None,
        "gold_results_sample": None,
        "is_distinct_difference": False,
        "is_set_operation_difference": False,
        "is_limit_order_difference": False,
        "is_case_or_value_difference": False
    }
    
    # 1. Execute both on sqlite if db exists
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(pred_sql)
            pred_rows = cursor.fetchall()
            analysis["pred_row_count"] = len(pred_rows)
            analysis["pred_results_sample"] = [str(r) for r in pred_rows[:3]]
            
            cursor.execute(gold_sql)
            gold_rows = cursor.fetchall()
            analysis["gold_row_count"] = len(gold_rows)
            analysis["gold_results_sample"] = [str(r) for r in gold_rows[:3]]
            
            conn.close()
            
            # Check if one is a duplicate-free version of the other
            pred_set = set([str(r) for r in pred_rows])
            gold_set = set([str(r) for r in gold_rows])
            
            if pred_set == gold_set and len(pred_rows) != len(gold_rows):
                analysis["is_distinct_difference"] = True
                analysis["cluster"] = "DISTINCT_PROJECTION_MISMATCH"
                analysis["details"] = f"Same unique rows ({len(pred_set)}), but duplicate row counts differ: Pred had {len(pred_rows)}, Gold had {len(gold_rows)}"
                return analysis
        except Exception as e:
            analysis["details"] = f"Execution error during analysis: {e}"
    
    # 2. Syntax/Pattern heuristics
    pred_up = pred_sql.upper()
    gold_up = gold_sql.upper()
    
    # Check for Set Operations (UNION, INTERSECT, EXCEPT vs subqueries)
    set_keywords = ["INTERSECT", "EXCEPT", "UNION"]
    has_set_gold = any(kw in gold_up for kw in set_keywords)
    has_set_pred = any(kw in pred_up for kw in set_keywords)
    if has_set_gold != has_set_pred:
        analysis["is_set_operation_difference"] = True
        analysis["cluster"] = "SET_OPERATION_SYNTHESIS"
        analysis["details"] = f"Gold uses set op ({[kw for kw in set_keywords if kw in gold_up]}), Pred uses ({[kw for kw in set_keywords if kw in pred_up]} or subquery/JOIN)"
        return analysis

    # Check for ORDER BY / LIMIT
    if ("LIMIT" in pred_up and "LIMIT" not in gold_up) or ("LIMIT" in gold_up and "LIMIT" not in pred_up):
        analysis["is_limit_order_difference"] = True
        analysis["cluster"] = "LIMIT_AND_RANKING_MISMATCH"
        analysis["details"] = "One query uses LIMIT/TOP while the other aggregates or filters without LIMIT."
        return analysis
        
    # Check for DISTINCT in text
    if ("DISTINCT" in pred_up and "DISTINCT" not in gold_up) or ("DISTINCT" in gold_up and "DISTINCT" not in pred_up):
        analysis["is_distinct_difference"] = True
        analysis["cluster"] = "DISTINCT_KEYWORD_MISMATCH"
        analysis["details"] = f"DISTINCT mismatch: Pred has DISTINCT={'DISTINCT' in pred_up}, Gold has DISTINCT={'DISTINCT' in gold_up}"
        return analysis

    # Check for Column projection count mismatch
    # (e.g. Gold selected 1 column, Pred selected 2 columns)
    if analysis["pred_results_sample"] and analysis["gold_results_sample"]:
        p_cols = len(eval(analysis["pred_results_sample"][0])) if analysis["pred_row_count"] > 0 else 0
        g_cols = len(eval(analysis["gold_results_sample"][0])) if analysis["gold_row_count"] > 0 else 0
        if p_cols != g_cols and p_cols > 0 and g_cols > 0:
            analysis["cluster"] = "PROJECTION_ATTRIBUTE_COUNT_MISMATCH"
            analysis["details"] = f"Column count mismatch: Pred projected {p_cols} columns, Gold projected {g_cols} columns"
            return analysis

    # Check for string literal filtering difference
    pred_literals = set(re.findall(r"'([^']*)'", pred_sql))
    gold_literals = set(re.findall(r"'([^']*)'", gold_sql))
    if pred_literals != gold_literals:
        # Check casing
        pred_lower_lits = {l.lower() for l in pred_literals}
        gold_lower_lits = {l.lower() for l in gold_literals}
        if pred_lower_lits == gold_lower_lits:
            analysis["is_case_or_value_difference"] = True
            analysis["cluster"] = "LITERAL_CASING_MISMATCH"
            analysis["details"] = f"String literal casing difference: Pred={pred_literals} vs Gold={gold_literals}"
            return analysis
        else:
            analysis["is_case_or_value_difference"] = True
            analysis["cluster"] = "LITERAL_VALUE_CHOICE_MISMATCH"
            analysis["details"] = f"Different literal values filtered: Pred={pred_literals} vs Gold={gold_literals}"
            return analysis

    # Check for Aggregate function difference
    aggs = ["COUNT(", "AVG(", "SUM(", "MAX(", "MIN("]
    pred_aggs = [a for a in aggs if a in pred_up]
    gold_aggs = [a for a in aggs if a in gold_up]
    if pred_aggs != gold_aggs:
        analysis["cluster"] = "AGGREGATE_FUNCTION_MISMATCH"
        analysis["details"] = f"Different aggregate functions: Pred={pred_aggs} vs Gold={gold_aggs}"
        return analysis

    # Default to general semantic predicate mismatch
    analysis["cluster"] = "PREDICATE_LOGIC_MISMATCH"
    analysis["details"] = "Different WHERE/HAVING boolean conditions or join filters"
    return analysis

def main():
    mismatches = parse_log()
    
    clusters = {}
    complexity_counts = {"EASY": 0, "MEDIUM": 0, "HARD": 0, "EXTRA": 0}
    
    enriched_mismatches = []
    for s in mismatches:
        c = s["complexity"].upper()
        complexity_counts[c] = complexity_counts.get(c, 0) + 1
        
        analysis = analyze_mismatch(s)
        s["analysis"] = analysis
        enriched_mismatches.append(s)
        
        cluster_name = analysis["cluster"]
        clusters[cluster_name] = clusters.get(cluster_name, 0) + 1

    # Save to JSON
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(enriched_mismatches, f, indent=2)
    print(f"\nSaved {len(enriched_mismatches)} enriched mismatches to {OUTPUT_JSON}")

    print("\n" + "="*60)
    print("        RESULT_MISMATCH FAILURE CLUSTER BREAKDOWN")
    print("="*60)
    print(f"Total Mismatches Analyzed: {len(enriched_mismatches)}\n")
    print("Distribution by Complexity Tier:")
    for comp, cnt in complexity_counts.items():
        pct = (cnt / len(enriched_mismatches)) * 100 if enriched_mismatches else 0
        print(f"  * {comp:<8}: {cnt:>3} ({pct:>5.1f}%)")
    
    print("\nDistribution by Failure Cluster:")
    sorted_clusters = sorted(clusters.items(), key=lambda x: x[1], reverse=True)
    for cl, cnt in sorted_clusters:
        pct = (cnt / len(enriched_mismatches)) * 100 if enriched_mismatches else 0
        print(f"  * {cl:<35}: {cnt:>3} ({pct:>5.1f}%)")
    print("="*60)

if __name__ == "__main__":
    main()
