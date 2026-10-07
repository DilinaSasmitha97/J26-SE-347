"""
Regression tests for Stage 6 (integration rehearsal and the fixes it found).

Runnable with plain `python test_integration.py` or under pytest. Builds the
SQLite test database first when it is missing.
"""

import inspect
import os
import sys
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "none")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "test_db"))

import db_config  # noqa: E402
import member2_stub  # noqa: E402
import pipeline  # noqa: E402
import profiler  # noqa: E402
import query_analyzer as qa  # noqa: E402
import response_intent  # noqa: E402
import sqlite_mysql  # noqa: E402
from result_profiler import profile_results  # noqa: E402

profiler.VERBOSE = False
_FAILURES = []


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def _ensure_database():
    if db_config.backend() == "sqlite" and not db_config.sqlite_path().exists():
        import seed
        seed.load_sqlite(seed.build_dataset())


def test_mysql_compatibility():
    print("\n[1] SQLite runs the MySQL fixture SQL with MySQL's semantics")
    check(sqlite_mysql._date_format("2025-03-17", "%Y-%m-01") == "2025-03-01",
          "DATE_FORMAT month bucket")
    check(sqlite_mysql._date_format("2025-03-17", "%M %Y") == "March 2025",
          "DATE_FORMAT %M is the month name, as in MySQL (not minutes, as in Python)")
    check(sqlite_mysql._shift("2025-03-17", 0, "DAY", -1) == "2025-03-17"
          and sqlite_mysql._shift("2025-03-31", 1, "MONTH", 1) == "2025-04-30",
          "DATE_ADD clamps the day at the end of a shorter month")
    check(sqlite_mysql._concat(2025, "-Q", 1) == "2025-Q1" and sqlite_mysql._concat("a", None) is None,
          "CONCAT joins values and is NULL when any part is NULL")
    rewritten = sqlite_mysql.rewrite(
        "SELECT DATE_SUB(opened_date, INTERVAL WEEKDAY(opened_date) DAY) AS w FROM t")
    check(rewritten == "SELECT MYSQL_DATE_SUB(opened_date, WEEKDAY(opened_date), 'DAY') AS w FROM t",
          "DATE_SUB(x, INTERVAL n DAY) is rewritten to a registered function")
    cols = sqlite_mysql.schema_columns(db_config.schema_ddl())
    src = sqlite_mysql.column_sources(
        "SELECT e.email AS mail, full_name, CONCAT(full_name, '!') AS x, s.revenue "
        "FROM employees e JOIN sales s ON s.tenant_id = e.tenant_id",
        ["mail", "full_name", "x", "revenue"], cols)
    check(src == [("employees", "email"), ("employees", "full_name"), (None, None),
                  ("sales", "revenue")],
          "column sources: alias, unqualified column in a join, expression, qualified column")
    check(sqlite_mysql.wire(3419.57) == "3419.57" and sqlite_mysql.wire(12) == 12,
          "money is serialised as a decimal string, counts stay integers")


def test_member2_stand_in():
    print("\n[2] Member 2 stand-in on SQLite: format, masking, read-only")
    out = member2_stub.query("SELECT full_name, email, department FROM employees "
                             "WHERE tenant_id = 'tenant_a' ORDER BY employee_id LIMIT 3")
    masked = {c["name"]: c["piiType"] for c in out["masking"]["columns"]}
    check(masked == {"full_name": "PERSON", "email": "EMAIL"},
          "PII columns found from their source columns and masked")
    check(all("*" in row[1] and "@" in row[1] for row in out["rows"])
          and all(row[2] and "*" not in row[2] for row in out["rows"]),
          "emails partially masked, non-PII department left intact")
    check(isinstance(out["rows"][0], list) and {"columns", "rowCount", "truncated"} <= set(out),
          "rows are arrays beside a columns list, as Member 2's /api/query returns")
    try:
        member2_stub.query("DELETE FROM expenses")
        check(False, "a non-SELECT statement is refused")
    except member2_stub.StubQueryError:
        check(True, "a non-SELECT statement is refused")
    conn = db_config.reader_connection()
    try:
        conn.execute("UPDATE expenses SET amount = 0")
        check(False, "the reader connection cannot write")
    except Exception:  # noqa: BLE001 - sqlite3.OperationalError: readonly database
        check(True, "the reader connection cannot write")
    finally:
        conn.close()


def test_forecast_opt_out():
    print("\n[3] A declined forecast is not produced, even with the LLM on")
    a = qa.analyze("Show my monthly expenses without a forecast", None)
    check(a.prediction_trigger == "DECLINED" and not a.prediction_required,
          "'without a forecast' declines; it is no longer read as a request")
    check(not qa.analyze("Show monthly revenue, no predictions please", None).prediction_required,
          "'no predictions please' declines the implicit trend forecast too")
    rule = qa._rule_analysis("Show my monthly expenses without a forecast", qa.parse_schema(None))
    llm_out = qa._validate_llm_payload(
        {"primary_intent": "TREND_ANALYSIS", "intent_confidence": 0.9,
         "prediction_trigger": "EXPLICIT", "prediction_required": True}, {})
    merged = qa._merge(rule, llm_out)
    check(merged.prediction_trigger == "DECLINED" and not merged.prediction_required,
          "an LLM that reads 'forecast' as a request cannot switch the forecast back on")
    check(qa.analyze("Show my monthly expenses and forecast the next 3 months", None)
          .prediction_trigger == "EXPLICIT", "an ordinary forecast request is unchanged")


def test_llm_policy_and_defaults():
    print("\n[4] LLM: off by default, and a confident rule verdict stands")
    defaults = {
        "pipeline.run": inspect.signature(pipeline.run).parameters["use_llm"].default,
        "pipeline.analyze_only": inspect.signature(pipeline.analyze_only).parameters["use_llm"].default,
        "query_analyzer.analyze": inspect.signature(qa.analyze).parameters["use_llm"].default,
    }
    import api
    defaults["api AnalyzeRequest"] = api.AnalyzeRequest.model_fields["use_llm"].default
    defaults["api PresentRequest"] = api.PresentRequest.model_fields["use_llm"].default
    check(not any(defaults.values()), f"use_llm defaults to False everywhere ({defaults})")
    tables = qa.parse_schema(None)
    rule = qa._rule_analysis("Show my total expenses by month over time", tables)
    llm_out = qa._validate_llm_payload({"primary_intent": "DETAIL_LOOKUP", "intent_confidence": 0.95}, {})
    check(rule.intent_confidence >= qa.RULE_INTENT_TRUST_THRESHOLD
          and qa._merge(rule, llm_out).primary_intent == rule.primary_intent,
          "a confident LLM does not override a confident rule intent")
    weak = qa._rule_analysis("sales stuff", tables)
    llm_out = qa._validate_llm_payload({"primary_intent": "KPI_SINGLE_VALUE", "intent_confidence": 0.9}, {})
    check(qa._merge(weak, llm_out).primary_intent == "KPI_SINGLE_VALUE",
          "a confident LLM fills in when the rules found no intent")


def test_charts_and_profiling():
    print("\n[5] Histograms, scatter plots, wide grouped results")
    import random
    rng = random.Random(6)
    rows = [{"amount": round(rng.gauss(500, 120), 2)} for _ in range(60)]
    env = pipeline.run("Show the distribution of individual expense amounts", rows=rows,
                       enable_cache=False)
    check(env["visualization"]["_meta"]["chart_type"] == "histogram",
          "a distribution over one measure gets a histogram, not a table (G2)")
    rows = [{"units": u, "revenue": round(u * 9.5 + rng.gauss(0, 20), 2)} for u in range(5, 65)]
    env = pipeline.run("Is there a relationship between units sold and revenue?", rows=rows,
                       enable_cache=False)
    check(env["visualization"]["_meta"]["chart_type"] == "scatter",
          "a correlation over two measures gets a scatter plot (G2)")
    rows = [{"vendor": f"Vendor {chr(65 + i)}", "total": 1000.0 + 37 * i} for i in range(15)]
    check(profile_results(rows).dimension_columns == ["vendor"],
          "15 vendors with one total each: the vendor column is a category, not a key")
    rows = [{"vendor_code": f"V{i:03d}", "total": 1000.0 + i} for i in range(15)]
    check(profile_results(rows).dimension_columns == [],
          "a column named like a key (_code) is still treated as a key")


def test_response_shape_fixes():
    print("\n[6] Response-shape fixes from the integration run")
    cls = response_intent.classify
    check(cls("What is the all-time high for daily signups?").intent == "SINGLE_ANSWER",
          "an extreme of a daily series is one figure")
    check(cls("What is my average monthly spend?").intent == "SINGLE_ANSWER",
          "an average monthly figure is one figure")
    check(cls("Show the monthly count of expenses nobody approved").intent != "SINGLE_ANSWER",
          "a monthly count is a series")
    check(cls("List my monthly expenses and predict the next 3 months").intent == "TABLE_CONTENT",
          "an explicit 'list' outranks the period word")
    check(cls("Briefly summarise my monthly sales and forecast the next quarter").intent
          == "SHORT_SUMMARY", "'briefly' keeps a summary short even when a forecast is named")
    scores, hits = qa._score_intents("what percent of total spend is software")
    check(not hits[qa.QueryIntent.COMPARISON], "'per' no longer matches inside 'percent'")


def test_found_by_the_ui():
    print("\n[7] Stage 7: defects found by rendering the UI")
    import math
    import summarization
    import warnings
    warnings.filterwarnings("ignore")
    rows = [{"month": f"{2023 + t // 12}-{t % 12 + 1:02d}-01",
             "total": round(20000 + 6000 * math.sin(2 * math.pi * t / 12) + (2500 if t == 16 else 0), 2)}
            for t in range(36)]
    env = pipeline.run("Show my monthly expenses over time", rows=rows, enable_cache=False)
    spec, meta = env["visualization"], env["visualization"]["_meta"]
    check(env["prediction"]["stage_5_anomaly"].get("seasonal")
          and "R3_THRESHOLD_RULES" not in meta["extension_rules_applied"],
          "a seasonal series' normal range (a deviation) is not drawn as levels on the value axis")
    shapes = [l["encoding"]["shape"] for l in spec.get("layer", []) if "shape" in l.get("encoding", {})]
    check(all(s.get("scale", {}).get("range") == ["triangle-up", "diamond"] for s in shapes),
          "anomaly markers keep their triangle (past) / diamond (forecast) shapes")
    noisy = [{"month": f"{2023 + t // 12}-{t % 12 + 1:02d}-01", "spend": v}
             for t, v in enumerate([8200, 10100, 10300, 9000, 13500, 8100, 1800, 8600, 3700, 5500,
                                    7100, 6700, 6800, 13600, 6000, 2900, 8400, 11300, 8400, 5600])]
    env = pipeline.run("Show monthly spend", rows=noisy, enable_cache=False)
    rules = [l for l in env["visualization"].get("layer", []) if l.get("mark", {}).get("type") == "rule"]
    bounds = [r["bound"] for l in rules for r in l["data"]["values"]]
    check("lower" not in bounds or env["prediction"]["stage_5_anomaly"]["lower_threshold"] >= 0,
          "a lower fence below zero is not drawn for a measure that is never negative")
    staff = [{"full_name": n, "hire_date": d, "salary": s} for n, d, s in
             [("A", "2018-12-12", 164300), ("B", "2019-09-26", 110700), ("C", "2020-05-11", 161600),
              ("D", "2021-02-18", 150200), ("E", "2023-02-18", 229200)]]
    env = pipeline.run("List all employees in the Finance department", rows=staff, enable_cache=False)
    check(not env["prediction"]["stage_5_anomaly"]["evaluated"]
          and not any(c["dimension"] == "ANOMALY" for c in env["summary"]["claims"]),
          "a list of records gets no anomaly bands and no outlier claims")
    texts = " ".join(c["text"] for c in env["summary"]["claims"])
    check(not any(c["kind"] == "CHANGE" for c in env["summary"]["claims"])
          and "per period" not in texts and "returned period" not in texts,
          "a list of records with a date column is not described as a time series")
    check(summarization._total_of("total amount") == "Total amount"
          and summarization._total_of("revenue") == "Total revenue",
          "no 'Total total amount' in summaries")
    from fastapi.testclient import TestClient
    import demo_api
    client = TestClient(demo_api.app)
    datasets = client.get("/demo/datasets").json()["datasets"]
    rows = client.post("/demo/rows", json={"dataset_id": "employees"}).json()
    check(len(datasets) == 11 and {"columns", "rows", "masking"} <= set(rows["member2_result"]),
          "demo routes list the data sources and return Member 2's masked payload")
    out = client.post("/api/v4/present", json={"user_query": "List all employees in the Finance department",
                                                **rows}).json()
    check(out["status"] == "SUCCESS" and out["response"]["blocks_emitted"] == ["TABLE"],
          "that payload goes through the real /api/v4/present unchanged")
    vendors = client.post("/demo/rows", json={"dataset_id": "by_vendor"}).json()
    out = client.post("/api/v4/present", json={"user_query": "show spend by vendor", **vendors}).json()
    spec = out["visualization"]
    check(out["response"]["blocks_emitted"] != ["CHART"] or bool(spec.get("mark") or spec.get("layer")),
          "a CHART block always carries a drawable spec (a row lookup asked for as a chart gets bars)")


def main() -> int:
    _ensure_database()
    test_mysql_compatibility()
    test_member2_stand_in()
    test_forecast_opt_out()
    test_llm_policy_and_defaults()
    test_charts_and_profiling()
    test_response_shape_fixes()
    test_found_by_the_ui()
    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} check(s) failed:")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
