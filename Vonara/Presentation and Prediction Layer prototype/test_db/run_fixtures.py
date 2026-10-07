"""
End-to-end integration run: MySQL -> Member 2 stub -> Component 4.

For every case in fixtures.json:
  1. run the hand-written SQL through member2_stub (read-only, masked,
     Member 2's exact wire format)
  2. feed that payload to pipeline.run exactly as /api/v4/present would
  3. check what the USER receives - the rendered response blocks - not just
     what the pipeline computed internally

The forecast checks are deliberately about delivery. A forecast that was
computed but never reaches a rendered block is a failure, and so is a
refused forecast whose reason the user never sees.

Usage:
    python test_db/run_fixtures.py                 all cases
    python test_db/run_fixtures.py --only F01 C05  selected cases
    python test_db/run_fixtures.py --group what-if one group
    python test_db/run_fixtures.py --verbose       also print each response
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import db_config
from db_config import OUTPUT_DIR

os.environ.setdefault("LLM_PROVIDER", "none")  # deterministic: results must be reproducible

import member2_stub  # noqa: E402
import pipeline  # noqa: E402
from summarization import fmt  # noqa: E402

FIXTURES_PATH = Path(__file__).resolve().parent / "fixtures.json"
CHECKS = ("ran", "intent", "response_intent", "forecast", "warnings", "what_if")

# Response keys that are metadata, not something a user reads.
_NON_CONTENT_KEYS = {"response_intent", "blocks_emitted", "blocks_declared", "chart"}


# ==========================================================================
# What the user actually sees
# ==========================================================================


def visible_text(response: dict) -> str:
    """
    Everything a client renders as text or cells, excluding the chart.

    Unknown block keys are included on purpose: when a new block type (for
    example a forecast notice) is added to the renderer, it counts as visible
    without this harness having to learn about it first.
    """
    parts = []
    summary = response.get("summary") or {}
    parts.append(summary.get("text", ""))
    answer = response.get("answer") or {}
    for key in ("label", "display_value", "qualifier"):
        parts.append(str(answer.get(key, "")))
    table = response.get("table") or {}
    parts.append(json.dumps(table.get("rows", []), default=str))
    parts.append(table.get("limit_note", ""))
    for key, value in response.items():
        if key not in _NON_CONTENT_KEYS | {"summary", "answer", "table"}:
            parts.append(json.dumps(value, default=str))
    return "\n".join(p for p in parts if p)


def _number_shown(value: float, text: str) -> bool:
    for token in {fmt(value), f"{value:.2f}", f"{round(value)}"}:
        if re.search(rf"(?<![\d.,]){re.escape(token)}(?![\d])", text):
            return True
    return False


def forecast_visible(envelope: dict) -> bool:
    response = envelope["response"]
    chart = (response.get("chart") or {}).get("spec") or {}
    if chart.get("_meta", {}).get("forecast_layered"):
        return True
    points = envelope["prediction"]["stage_4_forecast"].get("points") or []
    text = visible_text(response)
    return any(_number_shown(p["predicted"], text) for p in points)


def refusal_visible(envelope: dict) -> bool:
    pred = envelope["prediction"]
    reasons = [pred["stage_4_forecast"].get("skipped_reason", ""),
               pred["stage_2_readiness"].get("reason", "")]
    text = visible_text(envelope["response"])
    return any(r and r[:60] in text for r in reasons)


# ==========================================================================
# Checks
# ==========================================================================


def evaluate_case(case: dict, envelope: dict) -> dict:
    expect = case["expect"]
    analysis = envelope["analysis"]
    response = envelope["response"]
    pred = envelope["prediction"]
    results = {"ran": (True, "")}

    intent = analysis["intent"]["primary_intent"]
    results["intent"] = (intent in expect["intent"],
                         f"got {intent}, expected {'/'.join(expect['intent'])}")

    shape = response["response_intent"]["intent"]
    wanted = expect.get("response_intent")
    results["response_intent"] = (
        None if wanted is None else shape in wanted,
        f"got {shape}" + (f", expected {'/'.join(wanted)}" if wanted else ""),
    )

    generated = pred["stage_4_forecast"]["generated"]
    shown = generated and forecast_visible(envelope)
    refused_shown = (not generated) and refusal_visible(envelope)
    mode = expect["forecast"]
    detail = (f"generated={generated} shown={shown} refusal_shown={refused_shown} "
              f"readiness={pred['stage_2_readiness']['verdict']}")
    if mode == "SHOWN":
        ok = shown
    elif mode == "REFUSED":
        ok = refused_shown
    elif mode == "ANSWERED":
        ok = shown or refused_shown
    elif mode == "NONE":
        ok = not shown
    else:
        ok = None
    results["forecast"] = (ok, f"{mode}: {detail}")

    required = expect.get("warnings_include") or []
    missing = [w for w in required if w not in envelope.get("warnings", [])]
    results["warnings"] = (None if not required else not missing,
                           f"missing {missing}" if missing else "")

    wi = expect.get("what_if")
    if wi:
        scenario = pred["stage_6_scenario"]
        spec = scenario.get("spec") or {}
        ok = (scenario.get("simulated") == wi["simulated"]
              and spec.get("direction") == wi["direction"]
              and float(spec.get("magnitude_pct", 0)) == float(wi["magnitude_pct"]))
        results["what_if"] = (ok, f"got simulated={scenario.get('simulated')} "
                                  f"{spec.get('direction')} {spec.get('magnitude_pct')}%")
    else:
        results["what_if"] = (None, "")
    return results


def anomaly_against_truth(case: dict, envelope: dict, truth: dict) -> dict:
    """Score detected historical anomalies against the injected ones, by month index."""
    series = truth["tenants"][case["tenant"]][case["truth_series"]]
    injected = set(series["anomaly_indices"])
    report = envelope["prediction"]["stage_5_anomaly"]
    detected = {a["index"] for a in report.get("historical_anomalies", [])}
    months = truth["tenants"][case["tenant"]]["months"]
    hits = injected & detected
    return {
        "injected": sorted(months[i] for i in injected),
        "detected": sorted(months[i] for i in detected if i < len(months)),
        "true_positives": len(hits),
        "false_positives": len(detected - injected),
        "recall": round(len(hits) / len(injected), 3) if injected else None,
    }


# ==========================================================================
# Runner
# ==========================================================================


def run(cases: list, verbose: bool = False) -> list:
    truth_path = OUTPUT_DIR / "ground_truth.json"
    truth = json.loads(truth_path.read_text(encoding="utf-8")) if truth_path.exists() else None
    schema = db_config.schema_ddl()
    records = []

    conn = db_config.reader_connection()
    try:
        for case in cases:
            record = {"id": case["id"], "group": case["group"], "question": case["question"]}
            try:
                payload = member2_stub.query(case["sql"], conn=conn)
                envelope = pipeline.run(
                    case["question"], rows=payload, schema_meta=schema,
                    security_context={"tenant_id": case["tenant"]},
                    use_llm=False, enable_cache=False,
                )
                results = evaluate_case(case, envelope)
                record.update({
                    "rows": payload["rowCount"],
                    "masked_columns": envelope["input"]["masked_columns"],
                    "intent": envelope["analysis"]["intent"]["primary_intent"],
                    "response_intent": envelope["response"]["response_intent"]["intent"],
                    "chart": envelope["visualization"]["_meta"]["chart_type"],
                    "readiness": envelope["prediction"]["stage_2_readiness"]["verdict"],
                    "model": envelope["prediction"]["stage_3_model_selection"]["model"],
                    "warnings": envelope.get("warnings", []),
                })
                if case.get("truth_series") and truth:
                    record["anomaly_vs_truth"] = anomaly_against_truth(case, envelope, truth)
                if verbose:
                    record["visible_text"] = visible_text(envelope["response"])[:600]
            except Exception as exc:  # noqa: BLE001 - a crash is a result, not an abort
                results = {name: (None, "") for name in CHECKS}
                results["ran"] = (False, f"{type(exc).__name__}: {exc}")
            record["checks"] = {k: {"ok": v[0], "detail": v[1]} for k, v in results.items()}
            records.append(record)
    finally:
        conn.close()
    return records


def print_report(records: list, verbose: bool = False) -> int:
    print(f"\n{'ID':<5} {'group':<18} {'rows':>5}  {'intent':<18} {'shape':<14} "
          f"{'chart':<12} {'readiness':<20} result")
    print("-" * 118)
    for r in records:
        failed = [k for k, v in r["checks"].items() if v["ok"] is False]
        status = "PASS" if not failed else "FAIL " + ",".join(failed)
        print(f"{r['id']:<5} {r['group']:<18} {r.get('rows', '-'):>5}  "
              f"{r.get('intent', '-'):<18} {r.get('response_intent', '-'):<14} "
              f"{r.get('chart', '-'):<12} {r.get('readiness', '-'):<20} {status}")
        for name in failed:
            print(f"        {name}: {r['checks'][name]['detail']}")
        if verbose and r.get("visible_text"):
            print("        shown: " + r["visible_text"].replace("\n", " | ")[:300])

    print("\nCHECK SUMMARY (cases where the check applies)")
    for name in CHECKS:
        applied = [r["checks"][name]["ok"] for r in records if r["checks"][name]["ok"] is not None]
        if applied:
            passed = sum(applied)
            print(f"  {name:<16} {passed:>3} / {len(applied):<3} "
                  f"({100.0 * passed / len(applied):5.1f}%)")

    by_group = defaultdict(Counter)
    for r in records:
        failed = any(v["ok"] is False for v in r["checks"].values())
        by_group[r["group"]]["fail" if failed else "pass"] += 1
    print("\nBY GROUP")
    for group, c in by_group.items():
        print(f"  {group:<18} {c['pass']:>3} pass  {c['fail']:>3} fail")

    scored = [r for r in records if r.get("anomaly_vs_truth")]
    if scored:
        print("\nANOMALIES vs INJECTED GROUND TRUTH")
        for r in scored:
            a = r["anomaly_vs_truth"]
            print(f"  {r['id']}: injected {a['injected']}  detected {a['detected']}  "
                  f"recall={a['recall']}  false_positives={a['false_positives']}")

    total_failed = sum(any(v["ok"] is False for v in r["checks"].values()) for r in records)
    print(f"\n{len(records) - total_failed} / {len(records)} cases fully passed.")
    return 1 if total_failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", nargs="*", help="case ids to run")
    parser.add_argument("--group", help="run one group only")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    cases = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))["cases"]
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only)]
    if args.group:
        cases = [c for c in cases if c["group"] == args.group]

    try:
        records = run(cases, verbose=args.verbose)
    except db_config.DatabaseNotConfigured as exc:
        print(f"Cannot run fixtures: {exc}")
        return 2

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / "fixture_results.json"
    out.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    code = print_report(records, verbose=args.verbose)
    print(f"Full results: {out}")
    return code


if __name__ == "__main__":
    sys.exit(main())
