import os
import sys
import platform
import json
import sqlite3
import argparse
import time
from typing import List, Dict

# Prevent Python 3.12 Windows WMI query hang in platform module called by OpenAI SDK
if sys.platform == "win32":
    platform.win32_ver = lambda *args, **kwargs: ('10', '10.0.19045', 'SP0', 'Multiprocessor Free')
    platform.platform = lambda *args, **kwargs: 'Windows-10-10.0.19045-SP0'
    platform.system = lambda *args, **kwargs: 'Windows'
    platform.uname = lambda *args, **kwargs: platform.uname_result('Windows', 'PC', '10', '10.0.19045', 'AMD64')

from database import get_sqlite_connection, extract_sqlite_schema_as_create_statements
from main import translate
from profiler import CycleProfiler
from evaluate import yale_result_eq

MISMATCHES_FILE = os.path.join(os.path.dirname(__file__), "hard_join_mismatches.json")
DB_BASE_DIR = r"D:\spider_data\database"

def run_hard_testbed(max_samples: int = None, enable_refinement: bool = True):
    if not os.path.exists(MISMATCHES_FILE):
        print(f"[ERROR] Testbed file not found: {MISMATCHES_FILE}")
        return

    with open(MISMATCHES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if max_samples:
        data = data[:max_samples]

    total = len(data)
    yale_correct = 0
    strict_correct = 0
    healed = 0
    errors = 0

    print("=" * 70)
    print(f"      STAGE 5 HARD JOIN TESTBED RUNNER (N = {total})")
    print(f"      Option B: Post-Pruning Subgraph Join Path Injection")
    print("=" * 70)

    start_time = time.perf_counter()

    for idx, item in enumerate(data):
        q = item["question"]
        gold_sql = item["gold_sql"]
        db_id = item["db_id"]
        db_path = os.path.join(DB_BASE_DIR, db_id, f"{db_id}.sqlite")

        print(f"\n[{idx+1}/{total}] DB: {db_id} | Q: {q}")
        print(f"    Gold SQL:      {gold_sql.strip()}")

        try:
            conn = sqlite3.connect(db_path)
            schema = extract_sqlite_schema_as_create_statements(conn)

            pred_sql, token_stats = translate(
                nl_query=q,
                schema_meta=schema,
                enable_refinement=enable_refinement,
                db_conn=conn,
                full_schema_meta=schema
            )

            print(f"    Predicted SQL: {pred_sql.strip().replace(chr(10), ' ')}")

            cursor = conn.cursor()
            try:
                cursor.execute(pred_sql)
                p_rows = cursor.fetchall()
            except Exception as e:
                p_rows = None
                print(f"    [!] Predicted execution error: {e}")

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
                    yale_correct += 1
                    if is_strict:
                        print(f"    --> [YALE & STRICT MATCH] HEALED! (Was Hard Failure in Stage 5)")
                    else:
                        print(f"    --> [YALE PERMUTATION MATCH] HEALED! (Semantic Match)")
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

    elapsed = time.perf_counter() - start_time
    print("\n" + "=" * 70)
    print("                 HARD JOIN TESTBED SUMMARY REPORT")
    print("=" * 70)
    print(f"Total Hard Failures Evaluated: {total}")
    print(f"Newly Correct (Yale EX)      : {yale_correct} / {total} ({yale_correct/total*100:.1f}%)")
    print(f"Newly Correct (Strict EX)    : {strict_correct} / {total} ({strict_correct/total*100:.1f}%)")
    print(f"Saved by Compiler Refinement : {healed}")
    print(f"Pipeline / DB Errors         : {errors}")
    print(f"Total Wall-Clock Time        : {elapsed:.1f}s ({elapsed/total:.2f}s / query)")
    print("=" * 70)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage 5 Hard Join Testbed Runner")
    parser.add_argument("-n", "--samples", type=int, default=None, help="Max samples to run (default: all 53)")
    parser.add_argument("--refine", dest="refine", action="store_true", default=True, help="Enable refinement loop")
    parser.add_argument("--no-refine", dest="refine", action="store_false", help="Disable refinement loop")
    args = parser.parse_args()

    run_hard_testbed(max_samples=args.samples, enable_refinement=args.refine)
