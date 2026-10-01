import os
import sys
import platform
import json
import sqlite3
import argparse
import itertools
from typing import List, Tuple, Set

# Prevent Python 3.12 Windows WMI query hang in platform module called by OpenAI SDK
if sys.platform == "win32":
    platform.win32_ver = lambda *args, **kwargs: ('10', '10.0.19045', 'SP0', 'Multiprocessor Free')
    platform.platform = lambda *args, **kwargs: 'Windows-10-10.0.19045-SP0'
    platform.system = lambda *args, **kwargs: 'Windows'
    platform.uname = lambda *args, **kwargs: platform.uname_result('Windows', 'PC', '10', '10.0.19045', 'AMD64')

from database import get_sqlite_connection, extract_sqlite_schema_as_create_statements
from main import translate
from profiler import CycleProfiler, time_block, log_step
from evaluate import yale_result_eq

MISMATCHES_FILE = r"D:\Secure Multi-Tenant Natural Language Interface for Database Querying\Dilina\NL TO SQL prototype\mismatches_stage4_1.json"
DB_BASE_DIR = r"D:\spider_data\database"

def check_permutation_match(pred_rows: List[Tuple], gold_rows: List[Tuple]) -> bool:
    """Checks if rows match under any permutation of columns."""
    if not pred_rows or not gold_rows:
        return False
    if len(pred_rows) != len(gold_rows):
        return False
    if len(pred_rows[0]) != len(gold_rows[0]):
        return False
    num_cols = len(pred_rows[0])
    if num_cols <= 1:
        return False
        
    gold_set = set(str(r) for r in gold_rows)
    for perm in itertools.permutations(range(num_cols)):
        if perm == tuple(range(num_cols)):
            continue
        perm_pred = set(str(tuple(r[i] for i in perm)) for r in pred_rows)
        if perm_pred == gold_set:
            return True
    return False

def run_mismatches_testbed(max_samples: int = None, enable_refinement: bool = True):
    if not os.path.exists(MISMATCHES_FILE):
        print(f"Error: {MISMATCHES_FILE} not found. Run extract_and_cluster_mismatches.py first.")
        return

    with open(MISMATCHES_FILE, 'r', encoding='utf-8') as f:
        mismatches = json.load(f)

    if max_samples is not None and max_samples > 0:
        mismatches = mismatches[:max_samples]

    total = len(mismatches)
    print("=" * 65)
    print(f"  RUNNING STAGE 4.1 MISMATCH TESTBED (N = {total} failed queries)")
    print(f"  Refinement Loop: {'ENABLED' if enable_refinement else 'DISABLED'}")
    print("=" * 65)

    strict_correct = 0
    perm_correct = 0
    errors = 0
    healed = 0

    for idx, sample in enumerate(mismatches):
        s_idx = sample["sample_idx"]
        db_id = sample["db_id"]
        q = sample["question"]
        gold_sql = sample["gold_sql"]
        comp = sample["complexity"]
        orig_cluster = sample.get("analysis", {}).get("cluster", "UNKNOWN")

        print(f"\n[{idx+1}/{total}] Sample #{s_idx} | DB: {db_id} ({comp}) | Cluster: {orig_cluster}")
        print(f"    Q: {q}")

        db_path = os.path.join(DB_BASE_DIR, db_id, f"{db_id}.sqlite")
        if not os.path.exists(db_path):
            print(f"    [!] DB not found: {db_path}")
            errors += 1
            continue

        try:
            conn = get_sqlite_connection(db_path)
            full_schema = extract_sqlite_schema_as_create_statements(conn)

            pred_sql, token_stats = translate(
                nl_query=q,
                schema_meta=full_schema,
                injected_rules=None,
                profiler=None,
                use_pruning=True,
                enable_refinement=enable_refinement,
                db_conn=conn,
                full_schema_meta=full_schema,
                dialect="sqlite",
                use_entity_resolution=True,
                use_relationship_mapping=True
            )

            print(f"    Pred: {pred_sql.strip().replace(chr(10), ' ')}")
            print(f"    Gold: {gold_sql.strip().replace(chr(10), ' ')}")

            cursor = conn.cursor()
            try:
                cursor.execute(pred_sql)
                p_rows = cursor.fetchall()
            except Exception as e:
                p_rows = None
                print(f"    [!] Pred execution error: {e}")

            try:
                cursor.execute(gold_sql)
                g_rows = cursor.fetchall()
            except Exception as e:
                g_rows = None
                print(f"    [!] Gold execution error: {e}")

            if p_rows is not None and g_rows is not None:
                p_set = set(str(r) for r in p_rows)
                g_set = set(str(r) for r in g_rows)
                is_strict = (p_set == g_set)
                order_matters = 'order by' in gold_sql.lower()
                is_yale = yale_result_eq(g_rows, p_rows, order_matters=order_matters)

                if is_strict:
                    strict_correct += 1
                if is_yale:
                    perm_correct += 1
                    if is_strict:
                        print(f"    --> [YALE & STRICT MATCH] Correct! (Was {orig_cluster})")
                    else:
                        print(f"    --> [YALE PERMUTATION MATCH] Attributes swapped, semantically identical!")
                    if token_stats.get("healed", False):
                        healed += 1
                else:
                    print(f"    --> [STILL MISMATCH]")
            else:
                print(f"    --> [EXECUTION FAILURE]")

            conn.close()

        except Exception as e:
            print(f"    [!] Pipeline Exception: {e}")
            errors += 1

    print("\n" + "=" * 65)
    print("                 TESTBED SUMMARY REPORT")
    print("=" * 65)
    print(f"Total Evaluated From Failure Corpus: {total}")
    print(f"Strict Execution Matches (Identical): {strict_correct} ({strict_correct/total*100:.1f}%)")
    print(f"Permutation-Invariant Matches       : {perm_correct} ({perm_correct/total*100:.1f}%)")
    print(f"Pipeline / DB Errors                : {errors}")
    print(f"Queries Saved by Refinement         : {healed}")
    print("=" * 65)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 4.1 Mismatch Testbed Runner")
    parser.add_argument("-n", "--samples", type=int, default=None, help="Max mismatch samples to run (default: all 206)")
    parser.add_argument("--refine", dest="refine", action="store_true", default=True, help="Enable refinement loop")
    parser.add_argument("--no-refine", dest="refine", action="store_false", help="Disable refinement loop")
    args = parser.parse_args()

    run_mismatches_testbed(max_samples=args.samples, enable_refinement=args.refine)
