"""
Regression tests for the Stage 2 readiness classifier and SARIMA changes.

Runnable with plain `python test_readiness.py` or under pytest.
"""

import random
import sys
from datetime import date, timedelta

import pipeline
import prediction
from result_profiler import profile_results

_FAILURES = []


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def _month(t):
    return f"{2024 + t // 12:04d}-{t % 12 + 1:02d}-01"


def _monthly(n=24, noise=150.0, seed=1):
    rng = random.Random(seed)
    return [{"month": _month(t), "amount": round(5000 + 80 * t + rng.gauss(0, noise), 2)}
            for t in range(n)]


def _assess(rows):
    return prediction.assess_readiness(profile_results(rows), rows)


def test_three_level_decision():
    print("\n[1] Three-level decision with reason codes")
    ready = _assess(_monthly())
    check(ready.decision == "READY" and not ready.warnings, "clean monthly series is READY")
    gappy = _assess([r for i, r in enumerate(_monthly()) if i not in (6, 14)])
    check(gappy.decision == "READY_WITH_WARNING"
          and "MISSING_PERIODS_INTERPOLATED" in gappy.reason_codes and gappy.filled_periods == 2,
          "two missing months -> READY_WITH_WARNING, both reported as interpolated")
    sparse = _assess([r for i, r in enumerate(_monthly()) if i % 5 not in (1, 3)])
    check(sparse.decision == "NOT_READY" and sparse.verdict == "INCOMPLETE"
          and "IRREGULAR_INTERVALS" in sparse.reason_codes,
          "more than 25% of months missing -> NOT_READY / IRREGULAR_INTERVALS")
    nulls = _assess([dict(r, amount=None) if i % 3 == 0 else r for i, r in enumerate(_monthly())])
    check(nulls.decision == "NOT_READY" and "TOO_MANY_MISSING_VALUES" in nulls.reason_codes,
          "a third of values unreadable -> NOT_READY / TOO_MANY_MISSING_VALUES")
    short = _assess(_monthly(6))
    check(short.decision == "READY_WITH_WARNING" and "SIGNAL_NOT_ASSESSED" in short.reason_codes,
          "6 periods -> forecast with a 'too short to test' caution")
    grouped_rows = [{"month": _month(t), "region": g, "amount": 100.0 + t}
                    for t in range(12) for g in ("A", "B")]
    grouped = _assess(grouped_rows)
    check(grouped.decision == "NOT_READY" and grouped.reason_codes[0] == "MULTI_SERIES",
          "every refusal carries its reason code first")


def test_calendar_handling():
    print("\n[2] Calendar handling")
    rows, d = [], date(2025, 3, 3)
    while len(rows) < 40:
        if d.weekday() < 5:
            rows.append({"day": d.isoformat(), "revenue": 1000.0 + 3 * len(rows) + (len(rows) % 4) * 7})
        d += timedelta(days=1)
    prepared = prediction.prepare_series(rows, "day", "revenue", profile_results(rows).granularity)
    check(prepared["calendar"] == "BUSINESS_DAY" and prepared["missing_periods"] == 0,
          "weekday-only daily data: weekends are not counted as missing")
    gappy = [r for i, r in enumerate(_monthly()) if i not in (6, 14)]
    prepared = prediction.prepare_series(gappy, "month", "amount", "MONTH")
    check(len(prepared["values"]) == 24 and prepared["filled_indices"] == [6, 14],
          "missing months are placed back on the calendar grid")
    lo, hi = gappy[5]["amount"], gappy[6]["amount"]
    check(abs(prepared["values"][6] - (lo + hi) / 2) < 1e-9,
          "a single missing month is filled halfway between its neighbours")
    sparse = [r for i, r in enumerate(_monthly()) if i % 5 not in (1, 3)]
    check(profile_results(sparse).granularity == "MONTH",
          "sparse monthly data is still read as monthly, not quarterly")


def test_stationarity_evidence():
    print("\n[3] ADF + KPSS stationarity evidence")
    rng = random.Random(3)
    noise = [100 + rng.gauss(0, 5) for _ in range(40)]
    trend = [100 + 4 * t + rng.gauss(0, 2) for t in range(40)]
    s, t = prediction.stationarity_evidence(noise), prediction.stationarity_evidence(trend)
    check(s["assessed"] and s["verdict"] == "STATIONARY", "white noise reads as STATIONARY")
    check(t["assessed"] and t["verdict"] == "NON_STATIONARY", "a strong trend reads as NON_STATIONARY")
    check({"adf_p_value", "kpss_p_value"} <= set(s), "both p-values are reported")
    check(not prediction.stationarity_evidence(noise[:8])["assessed"],
          "fewer than 12 points: not assessed rather than guessed")
    report = _assess(_monthly(24))
    check(report.stationarity.get("assessed")
          and any(c.startswith("STATIONARITY_") for c in report.reason_codes),
          "readiness records the stationarity verdict as a reason code")


def test_sarima_and_bands():
    print("\n[4] SARIMA order and interval construction")
    check(prediction.SARIMA_ORDER == (0, 1, 1) and prediction.SARIMA_SEASONAL_ORDER == (0, 1, 1),
          "SARIMA uses the airline order chosen on development data")
    rng = random.Random(4)
    import math
    values = [1000 + 10 * t + 200 * math.sin(2 * math.pi * t / 12) + rng.gauss(0, 20)
              for t in range(36)]
    proj = prediction.project_series(values, "SARIMA", 3, 0.95, 12)
    check(proj["model"] == "SARIMA" and proj["interval_source"].startswith("residual_"),
          "SARIMA bands come from its residuals, not statsmodels' parameter-exact intervals")
    widths = [hi - lo for lo, hi in zip(proj["lower"], proj["upper"])]
    check(all(b > a for a, b in zip(widths, widths[1:])), "SARIMA bands widen with distance")
    check(prediction.MAX_EXPECTED_ERROR == 0.20, "gate threshold is the development-chosen 0.20")


def test_delivery_of_cautions():
    print("\n[5] A forecast shown with cautions says so")
    gappy = [r for i, r in enumerate(_monthly()) if i not in (6, 14)]
    env = pipeline.run("Show monthly expenses and predict the next 3 months",
                       rows=gappy, use_llm=False, enable_cache=False)
    readiness = env["prediction"]["stage_2_readiness"]
    notice = env["response"]["forecast_notice"]
    check(readiness["decision"] == "READY_WITH_WARNING", "pipeline readiness carries the decision")
    check(notice["readiness_decision"] == "READY_WITH_WARNING"
          and any(w["code"] == "MISSING_PERIODS_INTERPOLATED" for w in notice["warnings"]),
          "forecast_notice carries the decision and the warning")
    caution = [c for c in env["summary"]["claims"] if c["kind"] == "READINESS_CAUTION"]
    check(caution and env["summary"]["verification"]["passed"],
          "the caution is a verified summary claim")
    filled = env["prediction"]["stage_4_forecast"]["diagnostics"].get("interpolated_periods")
    anomalies = env["prediction"]["stage_5_anomaly"]["historical_anomalies"]
    check(filled == [6, 14] and all(a["index"] not in (6, 14) for a in anomalies),
          "interpolated months are recorded and never reported as anomalies")


def main() -> int:
    test_three_level_decision()
    test_calendar_handling()
    test_stationarity_evidence()
    test_sarima_and_bands()
    test_delivery_of_cautions()
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
