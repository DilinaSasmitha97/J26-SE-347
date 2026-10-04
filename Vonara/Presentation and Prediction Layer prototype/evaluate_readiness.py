"""
Readiness-decision correctness (proposal Table 7: "create labelled
READY / NOT_READY cases; report accuracy and false-ready rate").

Each case is a result set with dates, generated with a property that fixes
its correct decision by DEFINITION, before the classifier is run:

  NOT_READY           no time axis, fewer than 4 observations, a constant
                      series, more than 20% unreadable values, more than 25%
                      empty periods, pure noise (noise 50% of the level, no
                      trend), one series per category, raw unaggregated rows
  READY_WITH_WARNING  a few empty periods, a few unreadable values, a
                      near-constant series, a 4-7 period history (too short to
                      test predictability)
  READY               clean regular series - monthly, quarterly, weekly,
                      business-daily, yearly - with 3-8% noise

Every case type is generated with N_SEEDS different random seeds, so no
result rests on one lucky series. Reported: three-level accuracy, two-level
(ready / not ready) accuracy, the false-ready rate (a NOT_READY case allowed
through - the costly error) and the false-refusal rate, plus a confusion
matrix and every miss with its reason codes.

Run:  python evaluate_readiness.py
"""

import json
import os
import random
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "none")

import prediction  # noqa: E402
import profiler  # noqa: E402
from result_profiler import profile_results  # noqa: E402

profiler.VERBOSE = False

HERE = Path(__file__).resolve().parent
REPORT_MD = HERE / "data_and_reports" / "readiness_benchmark.md"
REPORT_JSON = HERE / "data_and_reports" / "readiness_benchmark_results.json"

SEED = 2026
N_SEEDS = 5
READY, WARN, NOT_READY = "READY", "READY_WITH_WARNING", "NOT_READY"


def _month(t: int) -> str:
    return f"{2023 + t // 12:04d}-{t % 12 + 1:02d}-01"


def _series(rng, n, noise, trend=0.02, level=None):
    level = level or rng.uniform(2_000, 60_000)
    return [max(level * 0.05, level * (1 + trend * t) + rng.gauss(0, level * noise))
            for t in range(n)]


def monthly(rng, n=24, noise=0.05, trend=0.02):
    return [{"month": _month(t), "amount": round(v, 2)}
            for t, v in enumerate(_series(rng, n, noise, trend))]


def quarterly(rng, n=16):
    return [{"quarter": f"{2021 + t // 4}-Q{t % 4 + 1}", "amount": round(v, 2)}
            for t, v in enumerate(_series(rng, n, 0.04))]


def weekly(rng, n=52):
    start = date(2025, 1, 6)
    return [{"week_start": (start + timedelta(weeks=t)).isoformat(), "orders": round(v, 2)}
            for t, v in enumerate(_series(rng, n, 0.05, 0.005))]


def business_daily(rng, n=60):
    out, d = [], date(2025, 3, 3)
    values = _series(rng, n, 0.04, 0.003)
    while len(out) < n:
        if d.weekday() < 5:
            out.append({"day": d.isoformat(), "revenue": round(values[len(out)], 2)})
        d += timedelta(days=1)
    return out


def yearly(rng, n=10):
    return [{"year": 2015 + t, "revenue": round(v, 2)} for t, v in enumerate(_series(rng, n, 0.03))]


def drop_periods(rows, k, rng):
    """Remove k interior periods (never the first or last)."""
    gone = set(rng.sample(range(1, len(rows) - 1), k))
    return [r for i, r in enumerate(rows) if i not in gone]


def null_values(rows, k, rng, column="amount"):
    gone = set(rng.sample(range(len(rows)), k))
    return [dict(r, **{column: None}) if i in gone else r for i, r in enumerate(rows)]


CASES = [
    # (case type, expected decision, expected reason code or None, builder)
    ("clean monthly 24", READY, None, lambda r: monthly(r, 24, 0.05)),
    ("clean monthly 36", READY, None, lambda r: monthly(r, 36, 0.08)),
    ("clean quarterly 16", READY, None, quarterly),
    ("clean weekly 52", READY, None, weekly),
    ("clean business-daily 60", READY, None, business_daily),
    ("clean yearly 10", READY, None, yearly),
    ("2-3 missing months of 24", WARN, "MISSING_PERIODS_INTERPOLATED",
     lambda r: drop_periods(monthly(r, 24), r.randint(2, 3), r)),
    ("2-3 unreadable values of 24", WARN, "MISSING_VALUES_DROPPED",
     lambda r: null_values(monthly(r, 24), r.randint(2, 3), r)),
    ("near-constant monthly 24", WARN, "NEAR_CONSTANT",
     lambda r: [{"month": _month(t), "amount": round(5_000 + r.uniform(-10, 10), 2)}
                for t in range(24)]),
    ("short monthly 5-7", WARN, "SIGNAL_NOT_ASSESSED", lambda r: monthly(r, r.randint(5, 7))),
    ("no time axis", NOT_READY, "NO_TIME_AXIS",
     lambda r: [{"region": x, "amount": round(r.uniform(1e3, 9e3), 2)}
                for x in ("North", "South", "East", "West", "Central")]),
    ("3 observations", NOT_READY, "INSUFFICIENT_POINTS", lambda r: monthly(r, 3)),
    ("constant series", NOT_READY, "CONSTANT_SERIES",
     lambda r: [{"month": _month(t), "amount": 750.0} for t in range(18)]),
    ("8+ of 24 values unreadable", NOT_READY, "TOO_MANY_MISSING_VALUES",
     lambda r: null_values(monthly(r, 24), r.randint(8, 12), r)),
    ("8+ of 24 months missing", NOT_READY, "IRREGULAR_INTERVALS",
     lambda r: drop_periods(monthly(r, 24), r.randint(8, 12), r)),
    ("pure noise (50%)", NOT_READY, "LOW_SIGNAL", lambda r: monthly(r, 24, 0.50, 0.0)),
    ("one series per region", NOT_READY, "MULTI_SERIES",
     lambda r: [{"month": _month(t), "region": g, "amount": round(r.uniform(1e3, 9e3), 2)}
                for t in range(18) for g in ("North", "South", "East")]),
]


def main() -> int:
    master = random.Random(SEED)
    records = []
    for name, expected, code, build in CASES:
        for k in range(N_SEEDS):
            rng = random.Random(master.randint(1, 10**9))
            rows = build(rng)
            report = prediction.assess_readiness(profile_results(rows), rows)
            records.append({
                "case": name, "seed": k, "expected": expected, "expected_code": code,
                "decision": report.decision, "verdict": report.verdict,
                "reason_codes": report.reason_codes,
                "code_ok": code is None or code in report.reason_codes,
                "stationarity": report.stationarity.get("verdict"),
            })

    def ready(d):
        return d in (READY, WARN)

    n = len(records)
    exact = sum(r["decision"] == r["expected"] for r in records)
    binary = sum(ready(r["decision"]) == ready(r["expected"]) for r in records)
    not_ready = [r for r in records if r["expected"] == NOT_READY]
    ready_cases = [r for r in records if r["expected"] != NOT_READY]
    false_ready = sum(ready(r["decision"]) for r in not_ready)
    false_refusal = sum(not ready(r["decision"]) for r in ready_cases)
    codes_checked = [r for r in records if r["expected_code"]]
    confusion = Counter((r["expected"], r["decision"]) for r in records)
    unneeded = Counter(c for r in records if r["expected"] == READY and r["decision"] == WARN
                       for c in r["reason_codes"] if not c.startswith("STATIONARITY_")
                       or c == "STATIONARITY_CONFLICT")

    summary = {
        "cases": n, "case_types": len(CASES), "seeds_per_type": N_SEEDS,
        "three_level_accuracy": exact / n, "two_level_accuracy": binary / n,
        "false_ready_rate": false_ready / len(not_ready),
        "false_refusal_rate": false_refusal / len(ready_cases),
        "reason_code_accuracy": sum(r["code_ok"] for r in codes_checked) / len(codes_checked),
        "confusion": {f"{a} -> {b}": c for (a, b), c in sorted(confusion.items())},
        "unneeded_warning_codes_on_clean_series": dict(unneeded),
    }

    levels = (READY, WARN, NOT_READY)
    md = ["# Readiness-decision benchmark", "",
          "Generated by `evaluate_readiness.py`. Do not edit by hand.", "",
          f"{n} labelled result sets: {len(CASES)} case types x {N_SEEDS} seeds. Each case's "
          "correct decision is fixed by how it was generated (see the module docstring).", "",
          "| Metric | Value |", "|---|---|",
          f"| Three-level accuracy (READY / WARNING / NOT_READY) | {exact / n * 100:.1f}% ({exact}/{n}) |",
          f"| Two-level accuracy (forecast / no forecast) | {binary / n * 100:.1f}% ({binary}/{n}) |",
          f"| False-ready rate (NOT_READY case let through) | {summary['false_ready_rate'] * 100:.1f}% "
          f"({false_ready}/{len(not_ready)}) |",
          f"| False-refusal rate (forecastable case refused) | {summary['false_refusal_rate'] * 100:.1f}% "
          f"({false_refusal}/{len(ready_cases)}) |",
          f"| Correct reason code given | {summary['reason_code_accuracy'] * 100:.1f}% |", "",
          "Confusion matrix (rows = correct decision, columns = classifier):", "",
          "| | " + " | ".join(levels) + " |", "|---|---|---|---|"]
    for a in levels:
        md.append(f"| {a} | " + " | ".join(str(confusion.get((a, b), 0)) for b in levels) + " |")
    md += ["", "| Case type | Expected | Correct | Decisions given |", "|---|---|---|---|"]
    for name, expected, _, _ in CASES:
        rs = [r for r in records if r["case"] == name]
        given = Counter(r["decision"] for r in rs)
        md.append(f"| {name} | {expected} | {sum(r['decision'] == expected for r in rs)}/{len(rs)} | "
                  + ", ".join(f"{d} x{c}" for d, c in given.items()) + " |")
    misses = [r for r in records if r["decision"] != r["expected"] or not r["code_ok"]]
    if misses:
        md += ["", "Misses:", "", "| Case | Expected | Got | Reason codes |", "|---|---|---|---|"]
        for r in misses:
            md.append(f"| {r['case']} (seed {r['seed']}) | {r['expected']} | {r['decision']} | "
                      f"{', '.join(r['reason_codes'])} |")

    text = "\n".join(md) + "\n"
    print(text)
    REPORT_MD.write_text(text, encoding="utf-8")
    REPORT_JSON.write_text(json.dumps({"summary": summary, "records": records}, indent=2),
                           encoding="utf-8")
    print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
