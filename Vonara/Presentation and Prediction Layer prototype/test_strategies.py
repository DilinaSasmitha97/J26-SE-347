"""
Regression tests for result layouts and the Stage 1 strategies.

Runnable with plain `python test_strategies.py` or under pytest.
"""

import random
import sys
from types import SimpleNamespace

import pipeline
import strategies
import synthetic_data as sd
from result_profiler import profile_results

_FAILURES = []
ANALYSIS = SimpleNamespace(primary_intent="COMPARISON")


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def _month(t):
    return f"{2024 + t // 12:04d}-{t % 12 + 1:02d}-01"


def crossing_rows(periods=16):
    """B starts below A and overtakes it just after the last observed month."""
    rows = []
    for t in range(periods):
        rows.append({"month": _month(t), "region": "A", "revenue": 50_000 + 100 * t})
        rows.append({"month": _month(t), "region": "B", "revenue": 30_000 + 1_300 * t})
        rows.append({"month": _month(t), "region": "C", "revenue": 20_000 + 50 * t})
    return rows


def test_layouts():
    print("\n[1] Result layout inference")
    single = profile_results(sd.generate_timeseries(n_periods=12)[0])
    grouped = profile_results(crossing_rows())
    events = profile_results([{"invoice_date": _month(t % 6), "amount": 100 + t} for t in range(30)])
    cross = profile_results(sd.generate_categorical(5))
    check(single.layout == "SINGLE", "one row per month is SINGLE")
    check(grouped.layout == "GROUPED" and grouped.group_column == "region",
          "month x region is GROUPED by region")
    check(events.layout == "EVENTS", "several raw rows per month with no grouping column is EVENTS")
    check(cross.layout == "CROSS_SECTIONAL", "no time axis is CROSS_SECTIONAL")


def test_category_trajectory():
    print("\n[2] Category trajectory")
    rows = crossing_rows()
    result = strategies.category_trajectory(profile_results(rows), rows, ANALYSIS, 3)
    d = result.details
    check(result.executed and len(d["categories"]) == 3, "every category forecast separately")
    check(d["current_leader"]["category"] == "A", "current leader read from the last period")
    check(d["projected_leader_end"]["category"] == "B" or d["projected_leader"]["category"] == "B",
          "the faster-growing category is projected to take the lead")
    cross = sd.generate_categorical(5)
    refused = strategies.category_trajectory(profile_results(cross), cross, ANALYSIS, 3)
    check(not refused.executed and "over time" in refused.skipped_reason,
          "a result with one value per category is refused with a reason")


def test_distribution_shift():
    print("\n[3] Distribution shift")
    rows = crossing_rows()
    shares = strategies.distribution_shift(profile_results(rows), rows, ANALYSIS, 3)
    d = shares.details
    check(shares.executed_as == "SHARE_SHIFT", "grouped result -> share shift")
    check(abs(sum(s["share_next_pct"] for s in d["shares"]) - 100) < 0.1
          and abs(sum(s["share_now_pct"] for s in d["shares"]) - 100) < 0.1,
          "shares sum to 100% now and projected")
    check(d["largest_gain"]["category"] == "B", "the growing category gains the most share")

    rng = random.Random(3)
    # Several transactions share each date, as raw invoices do; with unique
    # dates the rows would be indistinguishable from a daily series.
    raw = [{"invoice_date": f"2024-{m:02d}-{d:02d}", "amount": round(rng.uniform(80, 120) + 5 * m, 2)}
           for m in range(1, 10) for d in range(1, 28, 3) for _ in range(2)]
    quart = strategies.distribution_shift(profile_results(raw), raw, ANALYSIS, 3)
    check(quart.executed_as == "QUARTILE_SHIFT" and "median" in quart.details["projected"],
          "raw rows over 9 months -> projected quartiles")
    few = [r for r in raw if r["invoice_date"] < "2024-04"]
    check(not strategies.distribution_shift(profile_results(few), few, ANALYSIS, 3).executed,
          "fewer than 6 months of raw rows is refused")


def test_pipeline_grouped():
    print("\n[4] Pipeline on a grouped result")
    rows = crossing_rows()
    env = pipeline.run("Show monthly revenue by region and forecast the next 3 months",
                       rows=rows, use_llm=False, enable_cache=False)
    sr = env["prediction"]["stage_1_strategy_result"]
    text = env["summary"]["text"]
    check(env["prediction"]["stage_2_readiness"]["verdict"] == "MULTI_SERIES",
          "single-series forecast declines the mixed series")
    check(sr["executed"] and sr["executed_as"] == "CATEGORY_TRAJECTORY",
          "a trend over several series is forecast per series")
    check("per period" not in text and "Over the period the value" not in text,
          "no per-period statistics computed on the interleaved rows")
    check("No forecast was produced" not in text, "no contradictory 'no forecast' sentence")
    check(env["summary"]["verification"].get("passed"), "every number in the summary verified")
    check(env["response"]["forecast_notice"]["status"] == "SHOWN", "user is told the forecast is shown")
    check(env["prediction"]["stage_5_anomaly"]["skipped_reason"] != "",
          "anomaly bands are not computed on the mixture")


def test_anomaly_persistence_structure():
    print("\n[5] Anomaly persistence")
    rng = random.Random(4)
    base = [10_000 + 50 * t + rng.gauss(0, 200) for t in range(24)]
    shifted = base[:-2] + [v + 3_000 for v in base[-2:]]
    rows = [{"month": _month(t), "amount": round(v, 2)} for t, v in enumerate(shifted)]
    env = pipeline.run("Are there unusual months in my expenses and will they continue next quarter?",
                       rows=rows, use_llm=False, enable_cache=False)
    sr = env["prediction"]["stage_1_strategy_result"]
    check(sr["requested"] == "ANOMALY_PERSISTENCE", "anomaly intent maps to persistence")
    if sr["executed"]:
        check(sr["details"]["verdict"] in ("RECOVERING", "PERSISTING", "WORSENING", "NO_RECENT_ANOMALY"),
              "verdict is one of the closed set")
        check(any(c["kind"] == "STRATEGY_HEADLINE" for c in env["summary"]["claims"]),
              "the verdict is stated as a verified claim")
    else:
        check(bool(sr["skipped_reason"]), "a skipped persistence check says why")

    old = base[:5] + [base[5] + 4_000] + base[6:]
    stale = strategies.anomaly_persistence(*_forecast_and_report(old))
    check(stale.details.get("verdict") == "NO_RECENT_ANOMALY",
          "an anomaly 18 periods ago is not 'recent'")


def _forecast_and_report(values):
    import anomaly as anomaly_mod
    import prediction

    ready = prediction.ReadinessReport(is_ready=True, granularity="MONTH", n_points=len(values))
    sel = prediction.select_model(SimpleNamespace(primary_intent="TREND_ANALYSIS"), ready, values)
    proj = prediction.project_series(values, sel.model, 3)
    fc = prediction.ForecastResult(generated=True, model=proj["model"], historical_values=values,
                                   points=[prediction.ForecastPoint(period_index=h + 1, label=f"t+{h + 1}",
                                                                    predicted=p, lower_bound=lo,
                                                                    upper_bound=hi)
                                           for h, (p, lo, hi) in enumerate(zip(
                                               proj["forecasts"], proj["lower"], proj["upper"]))])
    return fc, anomaly_mod.detect_anomalies(values, forecast=fc)


def main() -> int:
    test_layouts()
    test_category_trajectory()
    test_distribution_shift()
    test_pipeline_grouped()
    test_anomaly_persistence_structure()
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
