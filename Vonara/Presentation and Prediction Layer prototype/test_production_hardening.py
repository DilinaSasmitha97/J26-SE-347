"""
Regression tests for the Stage 8 production hardening of the Stage 2 layer:
truncated input, input validation, configurable policy, holiday-aware
business days, non-negative ranges, the SARIMA time limit, horizon disclosure
and the "Other" group in category strategies.

Runnable with plain `python test_production_hardening.py` or under pytest.
"""

import json
import os
import random
import subprocess
import sys
import tempfile
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("LLM_PROVIDER", "none")
warnings.filterwarnings("ignore")

import input_adapter  # noqa: E402
import pipeline  # noqa: E402
import prediction  # noqa: E402
import profiler  # noqa: E402
import response_renderer  # noqa: E402
import strategies  # noqa: E402
from result_profiler import profile_results  # noqa: E402

profiler.VERBOSE = False
HERE = Path(__file__).resolve().parent
_FAILURES = []


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def _month(t):
    return f"{2023 + t // 12:04d}-{t % 12 + 1:02d}-01"


def _monthly(n=24, seed=1, base=5000.0, slope=80.0, noise=150.0):
    rng = random.Random(seed)
    return [{"month": _month(t), "amount": round(base + slope * t + rng.gauss(0, noise), 2)}
            for t in range(n)]


def _member2(rows, truncated=False, row_count=None):
    cols = list(rows[0])
    return {"columns": [{"name": c} for c in cols], "rows": [[r[c] for c in cols] for r in rows],
            "rowCount": row_count if row_count is not None else len(rows),
            "truncated": truncated, "masking": {"columns": []}}


def _run(question, payload, **kw):
    return pipeline.run(question, rows=payload, enable_cache=False, **kw)


# --------------------------------------------------------------------------


def test_truncated_input():
    print("\n[1] A result cut at the row limit is not forecast")
    rows = _monthly(24)
    profile = profile_results(rows)
    info = {"truncated": True, "row_count": 1000, "rows_received": 24}
    report = prediction.assess_readiness(profile, rows, input_info=info)
    check(report.decision == "NOT_READY" and report.verdict == "TRUNCATED"
          and report.reason_codes[0] == "INPUT_TRUNCATED" and "24 of 1000" in report.reason,
          "readiness refuses a truncated result and says how many rows arrived")
    complete = prediction.assess_readiness(profile, rows, input_info={"truncated": False})
    check(complete.decision != "NOT_READY" and complete.policy_version == prediction.CONFIG["version"],
          "the same rows, complete, are not refused; the policy version is recorded")

    env = _run("show monthly amount and forecast the next 3 months",
               _member2(rows, truncated=True, row_count=1000))
    notice = env["response"].get("forecast_notice") or {}
    check(not env["prediction"]["stage_4_forecast"]["generated"]
          and notice.get("status") == "REFUSED" and "row limit" in notice.get("reason", ""),
          "through the pipeline: no forecast, and the notice gives the row-limit reason")

    grouped = [{"month": _month(t), "region": g, "amount": 100.0 + 5 * t + i}
               for t in range(12) for i, g in enumerate(("North", "South", "East"))]
    env = _run("compare amount by region and forecast next quarter",
               _member2(grouped, truncated=True, row_count=500))
    strategy = env["prediction"]["stage_1_strategy_result"]
    check(strategy["requested"] != "NONE" and not strategy["executed"]
          and "row limit" in strategy["skipped_reason"],
          "category strategies are not run on a truncated result either")

    saved = prediction.REFUSE_TRUNCATED_INPUT
    prediction.REFUSE_TRUNCATED_INPUT = False
    try:
        lenient = prediction.assess_readiness(profile, rows, input_info=info)
    finally:
        prediction.REFUSE_TRUNCATED_INPUT = saved
    check(lenient.decision == "READY_WITH_WARNING" and "INPUT_TRUNCATED" in lenient.reason_codes,
          "with the policy switched off, truncation becomes a caution instead")


def test_input_validation():
    print("\n[2] Malformed Member 2 payloads fail clearly")
    try:
        input_adapter.adapt_result({"columns": [], "rows": [["2024-01-01", "5"]]})
        raised = False
    except input_adapter.InputFormatError:
        raised = True
    check(raised, "rows without column names are rejected, not silently emptied")
    bad_count = input_adapter.adapt_result({"columns": [{"name": "a"}], "rows": [[1]],
                                            "rowCount": "lots"})
    check("INVALID_ROW_COUNT" in bad_count.warnings and bad_count.row_count == 1,
          "a non-numeric rowCount is reported, not a crash")
    unknown = input_adapter.adapt_result({"columns": [{"name": "a"}], "rows": [[1]],
                                          "masking": {"columns": [{"name": "email",
                                                                   "piiType": "EMAIL"}]}})
    check("MASKED_COLUMN_NOT_FOUND" in unknown.warnings,
          "masking that names a missing column is flagged")
    from fastapi.testclient import TestClient

    import api

    reply = TestClient(api.app).post("/api/v4/present", json={
        "user_query": "show totals", "member2_result": {"columns": [], "rows": [["x", 1]]}}).json()
    check(reply.get("status") == "ERROR" and reply.get("error_code") == "INPUT_FORMAT_ERROR",
          "the API reports a malformed payload as INPUT_FORMAT_ERROR, not a component failure")


def test_configuration():
    print("\n[3] Policy is read from forecast_config.json")
    shipped = json.loads((HERE / "forecast_config.json").read_text(encoding="utf-8"))
    check(prediction.CONFIG["version"] == shipped["version"]
          and prediction.MAX_EXPECTED_ERROR == shipped["readiness"]["max_expected_error"]["default"]
          and prediction.max_expected_error("MONTH") == shipped["readiness"]["max_expected_error"]["MONTH"],
          "constants and the per-granularity limit come from the shipped file")
    with tempfile.TemporaryDirectory() as tmp:
        override = Path(tmp) / "policy.json"
        override.write_text(json.dumps({"version": "test-override", "readiness": {
            "max_expected_error": {"default": 0.5, "DAY": 0.35}, "min_points_any": 7}}))
        code = ("import prediction as p; print(p.CONFIG['version'], p.MAX_EXPECTED_ERROR, "
                "p.max_expected_error('DAY'), p.MIN_POINTS_ANY, p.MAX_MISSING_PERIOD_RATIO)")
        out = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True, text=True,
                             env={**os.environ, "C4_FORECAST_CONFIG": str(override)})
        check(out.stdout.split() == ["test-override", "0.5", "0.35", "7", "0.25"],
              "C4_FORECAST_CONFIG overrides chosen values and keeps defaults for the rest")


def test_business_days_and_holidays():
    print("\n[4] Business-day calendars skip weekends and configured holidays")
    start = date(2026, 3, 2)                       # a Monday
    days, d = [], start
    while len(days) < 30:
        if d.weekday() < 5 and d != date(2026, 3, 13):   # 13 March: the holiday
            days.append(d)
        d += timedelta(days=1)
    rows = [{"day": x.isoformat(), "orders": 100 + i % 7 * 3} for i, x in enumerate(days)]
    saved = prediction.HOLIDAYS
    try:
        prediction.HOLIDAYS = frozenset()
        plain = prediction.prepare_series(rows, "day", "orders", "DAY")
        prediction.HOLIDAYS = frozenset({"2026-03-13"})
        aware = prediction.prepare_series(rows, "day", "orders", "DAY")
        friday = datetime(2026, 4, 10)             # next trading days: Mon 13, Tue 14
        steps = [prediction._next_timestamp(friday, "DAY", k, "BUSINESS_DAY").date()
                 for k in (1, 2)]
        prediction.HOLIDAYS = frozenset({"2026-04-13"})
        holiday_step = prediction._next_timestamp(friday, "DAY", 1, "BUSINESS_DAY").date()
    finally:
        prediction.HOLIDAYS = saved
    check(plain["missing_periods"] == 1 and aware["missing_periods"] == 0
          and aware["calendar"] == "BUSINESS_DAY",
          "a configured holiday is not counted as a missing day")
    check(steps == [date(2026, 4, 13), date(2026, 4, 14)] and holiday_step == date(2026, 4, 14),
          "forecast dates skip the weekend, and a holiday on the next trading day")


def test_non_negative_ranges():
    print("\n[5] A measure that is never negative gets no negative forecast or range")
    counts = [40, 36, 33, 29, 27, 22, 20, 16, 13, 11, 8, 6]
    proj = prediction.project_series(counts, "LINEAR_REGRESSION", 6, 0.95, 12)
    check(min(proj["forecasts"]) >= 0 and min(proj["lower"]) >= 0 and proj["clipped_at_zero"] > 0,
          "a falling count is clipped at zero, and the clipping is counted")
    profit = [5, -3, 4, -6, 2, -8, 1, -9, 0, -11, -2, -12]
    proj = prediction.project_series(profit, "LINEAR_REGRESSION", 3, 0.95, 12)
    check(min(proj["lower"]) < 0 and proj["clipped_at_zero"] == 0,
          "a measure that can be negative (profit) is left alone")

    rows = [{"week": (date(2026, 1, 5) + timedelta(weeks=t)).isoformat(),
             "tickets": v} for t, v in enumerate([40, 37, 35, 33, 30, 28, 26, 23, 21, 19,
                                                   17, 15, 13, 11, 9, 7])]
    env = _run("show weekly tickets and forecast the next 6 weeks", rows)
    fc = env["prediction"]["stage_4_forecast"]
    notes = (env["response"].get("forecast_notice") or {}).get("notes", [])
    if fc["generated"]:
        check(all(p["lower_bound"] >= 0 for p in fc["points"])
              and (fc["diagnostics"]["clipped_at_zero"] == 0
                   or any(n["code"] == "RANGE_CLIPPED_AT_ZERO" for n in notes)),
              "through the pipeline: ranges stay at or above zero and clipping is disclosed")
    else:
        check(False, f"the ticket forecast was expected ({fc['skipped_reason']})")


def test_sarima_time_limit():
    print("\n[6] A slow SARIMA fit falls back instead of blocking the response")
    rng = random.Random(3)
    seasonal = [1000 + 300 * ((t % 12) in (10, 11)) + 5 * t + rng.gauss(0, 20) for t in range(48)]
    saved = prediction.SARIMA_TIMEOUT_SECONDS
    try:
        prediction.SARIMA_TIMEOUT_SECONDS = 1e-6
        slow = prediction.project_series(seasonal, "SARIMA", 3, 0.95, 12)
    finally:
        prediction.SARIMA_TIMEOUT_SECONDS = saved
    normal = prediction.project_series(seasonal, "SARIMA", 3, 0.95, 12)
    check(slow["model"] == "EXPONENTIAL_SMOOTHING" and "longer than" in slow["fallback_note"],
          "over the time limit: damped Holt is used, and the reason says so")
    check(normal["model"] == "SARIMA", "within the limit: SARIMA as before")
    fc = SimpleNamespace(model_reason="Seasonal." + slow["fallback_note"], diagnostics={},
                         horizon=3)
    notes = response_renderer.forecast_notes(fc)
    check(any(n["code"] == "MODEL_FALLBACK" and n["message"].startswith("SARIMA took")
              for n in notes), "the fallback is a forecast-notice note")


def test_horizon_disclosure():
    print("\n[7] The notice says where the horizon came from and if it was shortened")
    env = _run("show monthly amount and forecast the next 9 months", _monthly(10))
    notice = env["response"].get("forecast_notice") or {}
    check(notice.get("horizon_source") == "QUESTION" and notice.get("horizon_requested") == 9
          and notice.get("horizon") == 5
          and any(n["code"] == "HORIZON_SHORTENED" for n in notice.get("notes", [])),
          "9 asked for on 10 months: 5 shown, with the reason")
    env = _run("show monthly amount and forecast it", _monthly(24))
    notice = env["response"].get("forecast_notice") or {}
    check(notice.get("horizon_source") == "DEFAULT" and notice.get("horizon") == 3,
          "no horizon in the question: the default of 3, labelled as the default")


def test_other_group():
    print("\n[8] More than 12 categories: the rest form 'Other', so shares are of the true total")
    vendors = [f"V{i:02d}" for i in range(15)]
    rows = [{"month": _month(t), "vendor": v, "spend": 1000.0 - 50 * i + 3 * t}
            for t in range(12) for i, v in enumerate(vendors)]
    profile = profile_results(rows)
    analysis = SimpleNamespace(primary_intent="COMPARISON")
    traj = strategies.category_trajectory(profile, rows, analysis, 1, 0.95)
    others = [c for c in traj.details.get("categories", []) if c.get("is_other")]
    check(traj.executed and len(others) == 1 and others[0]["members"] == 3
          and traj.details["grouped_into_other"] == ["V12", "V13", "V14"],
          "the 3 smallest of 15 vendors are summed into one 'Other' series")
    check(not traj.details["projected_leader"]["category"].startswith("Other")
          and all(not r["category"].startswith("Other") for r in traj.details["rank_changes"]),
          "'Other' is never named as a leader or in a ranking change")
    shift = strategies.distribution_shift(profile, rows, analysis, 1, 0.95)
    shares = shift.details.get("shares", [])
    total_now = sum(r["spend"] for r in rows if r["month"] == _month(11))
    v00 = next(s for s in shares if s["category"] == "V00")
    check(abs(sum(s["share_now_pct"] for s in shares) - 100) < 0.1
          and abs(v00["share_now_pct"] - 100 * (1000 + 33) / total_now) < 0.01,
          "shares sum to 100% and each is a share of the full 15-vendor total")
    check(not shift.details["largest_gain"]["is_other"]
          and not shift.details["largest_loss"]["is_other"],
          "'Other' is never reported as the largest gain or loss")


def test_adopted_candidates():
    print("\n[9] Changes adopted from the development experiment (stage8_candidates.md)")
    import csv

    with (HERE / "benchmark_data" / "m4_monthly_dev_long72.csv").open(encoding="utf-8") as fh:
        series = {r["series_id"]: [float(v) for v in r["values"].split()]
                  for r in csv.DictReader(fh)}
    train = series["M36475"][:60]          # the series SARIMA failed on (MASE 57)
    analysis = SimpleNamespace(primary_intent="TREND_ANALYSIS")
    ready = prediction.ReadinessReport(is_ready=True, granularity="MONTH", n_points=len(train))
    selection = prediction.select_model(analysis, ready, train)
    guard = selection.signals.get("guard", {})
    check(prediction.GUARD_SARIMA and guard.get("rule_choice") == "SARIMA"
          and guard.get("overridden") and selection.model in ("NAIVE", "SEASONAL_NAIVE"),
          "SARIMA must beat the benchmarks too: on M36475 it does not, and is replaced")

    long_series, short_series = series["M36475"][:60], series["M36475"][:36]
    fixed_long = prediction._fit_holt(long_series, 3)[1]
    used_long = prediction.project_series(long_series, "EXPONENTIAL_SMOOTHING", 3)["forecasts"]
    fixed_short = prediction._fit_holt(short_series, 3)[1]
    used_short = prediction.project_series(short_series, "EXPONENTIAL_SMOOTHING", 3)["forecasts"]
    check(prediction.FITTED_SMOOTHING_MIN_POINTS == 48 and used_long != fixed_long
          and used_short == fixed_short,
          "smoothing constants are estimated from 48 points, fixed below")

    found = None
    for seed in range(400):
        rng = random.Random(seed)
        values = [100 + (25 if t >= 15 else 0) + rng.gauss(0, 9) for t in range(30)]
        verdict = prediction.stationarity_evidence(values).get("verdict")
        err = prediction.forecastability(values, 12).get("expected_relative_error") or 0
        if verdict == "CONFLICT" and prediction.CONFLICT_NOISE_LIMIT < err < prediction.MAX_EXPECTED_ERROR:
            found = values
            break
    rows = [{"month": _month(t), "amount": v} for t, v in enumerate(found or [])]
    if found:
        refused = prediction.assess_readiness(profile_results(rows), rows)
        saved = prediction.CONFLICT_NOISE_LIMIT
        prediction.CONFLICT_NOISE_LIMIT = None
        try:
            allowed = prediction.assess_readiness(profile_results(rows), rows)
        finally:
            prediction.CONFLICT_NOISE_LIMIT = saved
        check(refused.decision == "NOT_READY" and "stationarity tests disagree" in refused.reason
              and allowed.decision != "NOT_READY",
              "a level shift with an 8-20% in-history error is refused; without the rule it was not")
    else:
        check(False, "a level-shift series for the conflict rule was found")


def test_filled_months_not_in_band():
    print("\n[10] Filled-in months do not narrow the forecast range")
    rows = [r for i, r in enumerate(_monthly(30, seed=7, noise=400.0)) if i not in (5, 9, 13, 17, 21)]
    prepared = prediction.prepare_series(rows, "month", "amount", "MONTH")
    values, filled = prepared["values"], prepared["filled_indices"]
    counted = prediction.project_series(values, "LINEAR_REGRESSION", 3)
    excluded = prediction.project_series(values, "LINEAR_REGRESSION", 3, interpolated=filled)
    check(filled == [5, 9, 13, 17, 21]
          and excluded["residual_std"] > counted["residual_std"]
          and excluded["upper"][0] - excluded["lower"][0] > counted["upper"][0] - counted["lower"][0],
          "leaving the 5 filled months out of the residuals widens the band, as it should")
    env = _run("show monthly amount and forecast the next 3 months", rows)
    fc = env["prediction"]["stage_4_forecast"]
    check(fc["generated"] and fc["diagnostics"]["interpolated_periods"] == filled
          and abs(fc["residual_std"] - round(excluded["residual_std"], 4)) < 1e-6,
          "the live forecast measures its band without the filled months")


def main() -> int:
    test_truncated_input()
    test_input_validation()
    test_configuration()
    test_business_days_and_holidays()
    test_non_negative_ranges()
    test_sarima_time_limit()
    test_horizon_disclosure()
    test_other_group()
    test_adopted_candidates()
    test_filled_months_not_in_band()
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
