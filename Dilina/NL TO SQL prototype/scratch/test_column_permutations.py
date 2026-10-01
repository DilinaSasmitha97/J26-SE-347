import json
import sqlite3
import os
import itertools

with open("mismatches_stage4_1.json", 'r', encoding='utf-8') as f:
    mismatches = json.load(f)

DB_DIR = r"D:\spider_data\database"

swapped_matches = []
for m in mismatches:
    db_id = m["db_id"]
    pred_sql = m["predicted_sql"]
    gold_sql = m["gold_sql"]
    db_path = os.path.join(DB_DIR, db_id, f"{db_id}.sqlite")
    
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(pred_sql)
            p_rows = cursor.fetchall()
            
            cursor.execute(gold_sql)
            g_rows = cursor.fetchall()
            
            conn.close()
            
            if len(p_rows) == len(g_rows) and len(p_rows) > 0:
                # Check if rows have same length (same number of columns)
                if len(p_rows[0]) == len(g_rows[0]) and len(p_rows[0]) > 1:
                    # Check permutations of columns
                    num_cols = len(p_rows[0])
                    # Try all permutations of column indices
                    for perm in itertools.permutations(range(num_cols)):
                        if perm == tuple(range(num_cols)):
                            continue # original order already failed
                        perm_p_rows = [tuple(r[i] for i in perm) for r in p_rows]
                        if set(str(r) for r in perm_p_rows) == set(str(r) for r in g_rows):
                            swapped_matches.append({
                                "sample_idx": m["sample_idx"],
                                "db_id": db_id,
                                "complexity": m["complexity"],
                                "question": m["question"],
                                "permutation": perm,
                                "pred_sql": pred_sql,
                                "gold_sql": gold_sql
                            })
                            break
        except Exception as e:
            pass

print(f"Total Column Permutation Swaps Found: {len(swapped_matches)} out of {len(mismatches)} mismatches!")
for s in swapped_matches[:5]:
    print(f"Sample {s['sample_idx']} ({s['complexity']}): Q: {s['question']}")
    print(f"  PRED: {s['pred_sql']}")
    print(f"  GOLD: {s['gold_sql']}")
    print(f"  Permutation: {s['permutation']}")
    print("-" * 50)
