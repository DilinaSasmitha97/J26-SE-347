"""
Integration rehearsal over HTTP (Stage 6).

Runs the whole chain through the component's real API, with stand-ins for the
parts other members own:

  question + hand-written SQL (fixtures.json)      stands in for Member 1
  security_context {tenant_id, denied_tables}      stands in for Member 3
  SQLite database -> member2_stub (masked, Member 2's exact /api/query shape)
                                                   stands in for Member 2
  POST /api/v4/analyze, /present, /simulate        this component, over HTTP

Checks, per call:

  CONTRACT   every field team_interface_contract.md promises a consumer is
             present with the documented type (sections 3.1 and 3.2)
  PRIVACY    no unmasked PII value from the database (every employee name and
             email, every approver email, every customer phone) appears
             anywhere in the JSON the API returns
  DENYLIST   a table in denied_tables is never named in the analysis
  TENANT     the same question and rows for two tenants never share a cache hit
  LATENCY    wall-clock time per endpoint as the client sees it

Run (after `python test_db/seed.py`):
    python test_db/run_api_rehearsal.py
Writes data_and_reports/integration_rehearsal.md and _results.json.
"""

import json
import os
import statistics
import sys
import time
import warnings
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "none")
warnings.filterwarnings("ignore", category=DeprecationWarning)

import db_config  # noqa: E402  (sets sys.path to the component directory)
import member2_stub  # noqa: E402
import profiler  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402

profiler.VERBOSE = False
REPORT_MD = db_config.COMPONENT_DIR / "data_and_reports" / "integration_rehearsal.md"
REPORT_JSON = db_config.COMPONENT_DIR / "data_and_reports" / "integration_rehearsal_results.json"

# Section 3.1 of the contract: what /api/v4/analyze promises other members.
ANALYZE_CONTRACT = {
    ("analysis", "intent", "primary_intent"): str,
    ("analysis", "semantic_roles", "metrics"): list,
    ("analysis", "semantic_roles", "dimensions"): list,
    ("analysis", "semantic_roles", "temporal_field"): str,
    ("analysis", "semantic_roles", "ordering"): str,
    ("analysis", "semantic_roles", "limit"): int,
    ("analysis", "semantic_roles", "limit_source"): str,
    ("analysis", "schema_binding", "affected_tables"): list,
    ("analysis", "governance", "pii_columns_referenced"): list,
    ("analysis", "prediction_request", "prediction_required"): bool,
    ("analysis", "prediction_request", "prediction_trigger"): str,
    ("analysis", "response_intent", "intent"): str,
    ("analysis", "response_intent", "blocks"): list,
    ("analysis", "warnings"): list,
}
# Section 3.2: the envelope the client renders.
PRESENT_CONTRACT = {
    ("status",): str,
    ("input", "masked_columns"): dict,
    ("response", "response_intent", "intent"): str,
    ("response", "blocks_emitted"): list,
    ("visualization", "_meta", "chart_type"): str,
    ("prediction", "stage_2_readiness", "verdict"): str,
    ("prediction", "stage_4_forecast", "generated"): bool,
    ("prediction", "stage_5_anomaly", "historical_anomalies"): list,
    ("summary", "text"): str,
    ("summary", "verification", "passed"): bool,
    ("warnings",): list,
    ("cache", "hit"): bool,
    ("profiling", "total_execution_ms"): (int, float),
}
ENUMS = {
    ("analysis", "semantic_roles", "limit_source"): {"EXPLICIT", "INFERRED", "NONE"},
    ("analysis", "prediction_request", "prediction_trigger"): {"EXPLICIT", "IMPLICIT", "NONE",
                                                               "DECLINED"},
    ("response", "response_intent", "intent"): {"SINGLE_ANSWER", "SHORT_SUMMARY", "TABLE_CONTENT",
                                                "CHART", "MIXED_SUMMARY"},
}
BLOCK_KEY = {"ANSWER": "answer", "SUMMARY": "summary", "TABLE": "table", "CHART": "chart"}


def _get(obj, path):
    for key in path:
        if not isinstance(obj, dict) or key not in obj:
            return KeyError
        obj = obj[key]
    return obj


def contract_problems(body: dict, contract: dict) -> list:
    out = []
    for path, typ in contract.items():
        value = _get(body, path)
        if value is KeyError:
            out.append(f"missing {'.'.join(path)}")
        elif not isinstance(value, typ) or (typ is int and isinstance(value, bool)):
            out.append(f"{'.'.join(path)} is {type(value).__name__}")
        elif path in ENUMS and value not in ENUMS[path]:
            out.append(f"{'.'.join(path)} = {value!r} not in the documented set")
    if "response" in body:
        for block in body["response"].get("blocks_emitted", []):
            if BLOCK_KEY.get(block) not in body["response"]:
                out.append(f"block {block} emitted but response.{BLOCK_KEY.get(block)} absent")
    return out


def raw_pii_values() -> set:
    """Every unmasked PII value in the database, read directly (not through the stub)."""
    conn = db_config.sqlite_connection(read_only=True)
    try:
        values = set()
        for sql in ("SELECT full_name, email FROM employees",
                    "SELECT approved_by_email FROM expenses",
                    "SELECT customer_phone FROM support_tickets"):
            for row in conn.execute(sql):
                values.update(str(v) for v in row if v)
    finally:
        conn.close()
    # Names are checked as whole names; very short tokens would match by chance.
    return {v for v in values if len(v) >= 6}


def leaked(body: dict, pii: set) -> list:
    text = json.dumps(body, ensure_ascii=False)
    return sorted(v for v in pii if v in text)


def _pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))] if values else None


def main() -> int:
    client = TestClient(api.app)
    cases = json.loads((db_config.TEST_DB_DIR / "fixtures.json").read_text(encoding="utf-8"))["cases"]
    schema = db_config.schema_ddl()
    pii = raw_pii_values()
    timings = {"analyze": [], "present": [], "simulate": []}
    problems = {"contract": [], "privacy": [], "http": []}

    health = client.get("/api/v4/health").json()

    for case in cases:
        ctx = {"tenant_id": case["tenant"]}
        t0 = time.perf_counter()
        r = client.post("/api/v4/analyze", json={"user_query": case["question"],
                                                 "schema_meta": schema, "security_context": ctx})
        timings["analyze"].append((time.perf_counter() - t0) * 1000)
        if r.status_code != 200 or r.json().get("status") != "SUCCESS":
            problems["http"].append(f"{case['id']} analyze {r.status_code}")
        else:
            problems["contract"] += [f"{case['id']} analyze: {p}"
                                     for p in contract_problems(r.json(), ANALYZE_CONTRACT)]

        payload = member2_stub.query(case["sql"])
        body = {"user_query": case["question"], "member2_result": payload,
                "schema_meta": schema, "security_context": ctx}
        t0 = time.perf_counter()
        r = client.post("/api/v4/present", json=body)
        timings["present"].append((time.perf_counter() - t0) * 1000)
        if r.status_code != 200 or r.json().get("status") != "SUCCESS":
            problems["http"].append(f"{case['id']} present {r.status_code}: {r.text[:120]}")
            continue
        out = r.json()
        problems["contract"] += [f"{case['id']} present: {p}"
                                 for p in contract_problems(out, PRESENT_CONTRACT)]
        problems["privacy"] += [f"{case['id']} present: unmasked {v!r}" for v in leaked(out, pii)]

        if case.get("expect", {}).get("what_if") or case["group"] == "what-if":
            t0 = time.perf_counter()
            r = client.post("/api/v4/simulate", json={**body, "scenario_text": "reduce spending by 15%"})
            timings["simulate"].append((time.perf_counter() - t0) * 1000)
            if r.status_code != 200:
                problems["http"].append(f"{case['id']} simulate {r.status_code}")
            else:
                problems["privacy"] += [f"{case['id']} simulate: unmasked {v!r}"
                                        for v in leaked(r.json(), pii)]

    # DENYLIST: the employees table denied; a question about employees must not bind it.
    r = client.post("/api/v4/analyze", json={
        "user_query": "List all employees and their salaries by department",
        "schema_meta": schema,
        "security_context": {"tenant_id": "tenant_a", "denied_tables": ["employees"]}}).json()
    # Only what is BOUND counts: `unresolved_terms` echoes the user's own words
    # ("employees") and says nothing about the schema.
    binding = r["analysis"]["schema_binding"]
    roles = r["analysis"]["semantic_roles"]
    named = json.dumps([binding["affected_tables"], binding["affected_columns"],
                        roles["metrics"], roles["dimensions"]]).lower()
    denylist_ok = "employees" not in named
    # TENANT: the same question and rows for two tenants -> the other tenant
    # must not get a cache hit. The question text is new, so the first call
    # cannot be a hit left over from the loop above.
    case = next(c for c in cases if c["group"] == "kpi")
    payload = member2_stub.query(case["sql"])
    question = case["question"] + " (tenant isolation check)"
    hits = []
    for tenant in ("tenant_a", "tenant_a", "tenant_b"):
        out = client.post("/api/v4/present", json={
            "user_query": question, "member2_result": payload, "schema_meta": schema,
            "security_context": {"tenant_id": tenant}}).json()
        hits.append(out["cache"]["hit"])
    tenant_ok = hits == [False, True, False]

    results = {
        "health": health, "cases": len(cases), "pii_values_checked": len(pii),
        "problems": problems, "denylist_ok": denylist_ok,
        "tenant_cache_hits": hits, "tenant_isolation_ok": tenant_ok,
        "latency_ms": {k: {"calls": len(v), "median": statistics.median(v) if v else None,
                           "p95": _pct(v, 0.95), "max": max(v) if v else None}
                       for k, v in timings.items()},
    }
    lat = results["latency_ms"]
    md = ["# Integration rehearsal (Stage 6)", "",
          "Generated by `test_db/run_api_rehearsal.py`. Do not edit by hand. The component's real "
          "HTTP API (FastAPI test client) fed by stand-ins for the other members: fixture SQL for "
          "Member 1, a SQLite database and `member2_stub` (masked, Member 2's exact format) for "
          "Member 2, `security_context` for Member 3. LLM off.", "",
          "| Check | Result |", "|---|---|",
          f"| HTTP calls failing | {len(problems['http'])} |",
          f"| Contract fields missing or mistyped (analyze + present, {len(cases)} questions each) | "
          f"{len(problems['contract'])} |",
          f"| Unmasked PII values found in any response ({len(pii)} distinct values checked) | "
          f"**{len(problems['privacy'])}** |",
          f"| Denied table never named in the analysis | {'yes' if denylist_ok else '**NO**'} |",
          f"| Tenant cache isolation (hits for A, A, B: expected False, True, False) | "
          f"{hits} {'ok' if tenant_ok else '**FAILED**'} |", "",
          "| Endpoint | Calls | Median ms | p95 ms | Max ms |", "|---|---|---|---|---|"]
    for k, v in lat.items():
        if v["calls"]:
            md.append(f"| /api/v4/{k} | {v['calls']} | {v['median']:.0f} | {v['p95']:.0f} | {v['max']:.0f} |")
    for kind, items in problems.items():
        if items:
            md += ["", f"## {kind} problems", ""] + [f"- {p}" for p in items[:40]]
    text = "\n".join(md) + "\n"
    print(text)
    REPORT_MD.write_text(text, encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    failed = any(problems.values()) or not denylist_ok or not tenant_ok
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
