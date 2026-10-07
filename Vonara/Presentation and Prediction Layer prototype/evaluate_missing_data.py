"""
Stage 8 - how much missing data can a forecast tolerate? (DEVELOPMENT data only)

The readiness classifier refuses a series when more than 20% of its values are
unreadable or more than 25% of its periods are empty, and fills smaller gaps by
linear interpolation (prepare_series). Those limits were set as policy in
Stage 2, not measured. This experiment measures what interpolated gaps do to
forecast accuracy, to show whether the limits sit in a sensible place.

Protocol:
  - The 100 M4_DEV series (36 months). For each, the last 3 months are the
    test; the 33 before are the history.
  - A share r of the history's interior months (never the first or last) is
    deleted at random, 5 times per series per r (seeds 0-4).
  - The gappy rows go through the live code: prepare_series fills the gaps,
    the guarded selector picks a model, project_series forecasts.
  - The forecast is compared with the true 3 months (sMAPE), and with the
    forecast made from the complete history.

An unreadable value and an empty period reach the model the same way (the row
is dropped, then the period is interpolated), so one experiment covers both.

Run:   python evaluate_missing_data.py
Writes data_and_reports/missing_data_sensitivity.md and _results.json.
"""

import json
import os
import random
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "none")

import evaluate_forecasting as ef  # noqa: E402

HERE = Path(__file__).resolve().parent
REPORT_MD = HERE / "data_and_reports" / "missing_data_sensitivity.md"
REPORT_JSON = HERE / "data_and_reports" / "missing_data_sensitivity_results.json"
RATES = [0.0, 0.10, 0.20, 0.25, 0.30, 0.40, 0.50]
REPEATS = 5


def _month(t: int) -> str:
    return f"{2020 + t // 12:04d}-{t % 12 + 1:02d}-01"


def run_series(series: dict) -> list:
    import prediction
    import profiler

    profiler.VERBOSE = False
    values = series["values"]
    history, test = values[:-ef.HORIZON], values[-ef.HORIZON:]
    out = []
    for rate in RATES:
        for seed in range(REPEATS if rate else 1):
            rng = random.Random(seed * 1000 + len(history))
            interior = list(range(1, len(history) - 1))
            drop = set(rng.sample(interior, round(rate * len(interior))))
            rows = [{"month": _month(t), "v": v} for t, v in enumerate(history) if t not in drop]
            prepared = prediction.prepare_series(rows, "month", "v", "MONTH")
            filled = prepared["values"]
            selection = prediction.select_model(ef._ANALYSIS, ef._ready(len(filled)), filled)
            # As the live code does (generate_forecast): filled positions are
            # left out of the band's residuals. FILLED_IN_BAND=1 reproduces the
            # behaviour before Stage 8 for comparison.
            excluded = [] if os.getenv("FILLED_IN_BAND") == "1" else prepared["filled_indices"]
            proj = prediction.project_series(filled, selection.model, ef.HORIZON,
                                             ef.CONFIDENCE, ef.PERIOD, interpolated=excluded)
            smapes = [ef.smape(a, f) for a, f in zip(test, proj["forecasts"])]
            out.append({"series": series["id"], "rate": rate, "seed": seed,
                        "missing_periods": prepared["missing_periods"],
                        "smape": statistics.mean(smapes),
                        "covered": sum(lo <= a <= hi for a, lo, hi in
                                       zip(test, proj["lower"], proj["upper"])) / ef.HORIZON})
    return out


def main() -> int:
    started = time.perf_counter()
    series = ef.m4_series(ef.M4_DEV, "M4_DEV")
    rows = []
    workers = int(os.getenv("WORKERS", "4"))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for result in pool.map(run_series, series, chunksize=4):
            rows.extend(result)

    complete = {r["series"]: r["smape"] for r in rows if r["rate"] == 0.0}
    table = []
    for rate in RATES:
        rs = [r for r in rows if r["rate"] == rate]
        increase = [r["smape"] - complete[r["series"]] for r in rs]
        table.append({
            "missing_rate": rate, "forecasts": len(rs),
            "smape_mean": statistics.mean(r["smape"] for r in rs),
            "smape_median": statistics.median(r["smape"] for r in rs),
            "smape_increase_mean": statistics.mean(increase),
            "worse_than_complete_by_5pp": sum(d > 5 for d in increase) / len(increase),
            "unreliable_rate": sum(r["smape"] > ef.UNRELIABLE_SMAPE for r in rs) / len(rs),
            "coverage95": statistics.mean(r["covered"] for r in rs),
        })
    results = {"protocol": {"series": len(series), "rates": RATES, "repeats": REPEATS,
                            "history": 33, "horizon": ef.HORIZON,
                            "unreliable_smape": ef.UNRELIABLE_SMAPE,
                            "policy_limits": {"max_missing_period_ratio": 0.25,
                                              "max_missing_value_ratio": 0.20}},
               "table": table, "runtime_seconds": round(time.perf_counter() - started, 1)}

    md = ["# Missing-data sensitivity (development data)", "",
          "Generated by `evaluate_missing_data.py`. Do not edit by hand.", "",
          f"{len(series)} M4_DEV series; a share of the 33-month history deleted at random "
          f"({REPEATS} draws per series), refilled by the live interpolation, forecast 3 months "
          "with the deployed selector. Current policy: refuse above 25% empty periods "
          "(20% unreadable values).", "",
          "| Months missing | Forecasts | sMAPE mean | sMAPE median | Increase vs complete | "
          "Worse by >5 pp | Unreliable (>20%) | 95% coverage |",
          "|---|---|---|---|---|---|---|---|"]
    for r in table:
        md.append(f"| {r['missing_rate'] * 100:.0f}% | {r['forecasts']} | {r['smape_mean']:.2f} | "
                  f"{r['smape_median']:.2f} | {r['smape_increase_mean']:+.2f} pp | "
                  f"{r['worse_than_complete_by_5pp'] * 100:.1f}% | "
                  f"{r['unreliable_rate'] * 100:.1f}% | {r['coverage95'] * 100:.1f}% |")
    md += ["", f"Runtime: {results['runtime_seconds']} s"]
    text = "\n".join(md) + "\n"
    print(text)
    REPORT_MD.write_text(text, encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
