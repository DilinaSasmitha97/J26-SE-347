"""
Regression tests for the Stage 3 anomaly engine.

Runnable with plain `python test_anomaly.py` or under pytest.
"""

import math
import random
import sys

import anomaly as anomaly_mod
import prediction
import strategies

_FAILURES = []


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def _flat(n=30, seed=1, level=1000.0, sd=20.0):
    rng = random.Random(seed)
    return [level + rng.gauss(0, sd) for _ in range(n)]


def test_detection_methods():
    print("\n[1] IQR alone, Z-score alone, combined")
    values = _flat()
    values[10] += 200          # large: both rules
    values[20] += 75           # moderate: inside |z| 3, outside the fence
    by = {m: anomaly_mod.detect_anomalies(values, method=m) for m in anomaly_mod.DETECTION_METHODS}
    idx = {m: {a.index for a in r.historical_anomalies} for m, r in by.items()}
    check(idx["COMBINED"] == idx["IQR"] | idx["ZSCORE"],
          "combined flags exactly the union of the two single rules")
    check(10 in idx["IQR"] and 10 in idx["ZSCORE"], "a large spike is caught by both rules")
    check(all(a.detected_by == ["IQR"] for a in by["IQR"].historical_anomalies)
          and all(a.detected_by == ["ZSCORE"] for a in by["ZSCORE"].historical_anomalies),
          "a single-rule report attributes every flag to that rule")
    check(by["IQR"].method == "ADAPTIVE_IQR" and by["ZSCORE"].method == "ADAPTIVE_ZSCORE",
          "the report names the rule that was applied")
    try:
        anomaly_mod.detect_anomalies(values, method="MAD")
        check(False, "an unknown method is rejected")
    except ValueError:
        check(True, "an unknown method is rejected")


def _seasonal(n=48, seed=2, sd=150.0):
    rng = random.Random(seed)
    return [10000 + 60 * t + 2500 * math.sin(2 * math.pi * t / 12) + rng.gauss(0, sd)
            for t in range(n)]


def test_seasonal_space():
    print("\n[2] STL seasonal detection space")
    values = _seasonal()
    # A dip at a seasonal peak: still well inside the raw range of the series.
    peak = 27                                   # sin(2*pi*27/12) = 1
    values[peak] -= 1500
    plain = anomaly_mod.detect_anomalies(values)
    stl = anomaly_mod.detect_anomalies(values, period=12)
    check(stl.seasonal and stl.method == "ADAPTIVE_IQR_ZSCORE_STL"
          and stl.seasonal_strength >= anomaly_mod.SEASONAL_STRENGTH_THRESHOLD,
          "a strongly seasonal series is screened on the STL remainder")
    check(peak not in {a.index for a in plain.historical_anomalies}
          and peak in {a.index for a in stl.historical_anomalies},
          "a dip at a seasonal peak is missed on levels and caught in the seasonal space")
    check(all(a.value == round(values[a.index], 4) for a in stl.historical_anomalies),
          "flagged values are the raw observations, not the remainder")
    short = anomaly_mod.detect_anomalies(_seasonal(n=24), period=12)
    check(not short.seasonal, "fewer than three cycles: no seasonal space")
    rng = random.Random(4)
    noise = [1000 + rng.gauss(0, 30) for _ in range(48)]
    check(not anomaly_mod.detect_anomalies(noise, period=12).seasonal,
          "a series without a seasonal pattern stays in the level space")


def _forecast(model, predicted, granularity="MONTH"):
    return prediction.ForecastResult(
        generated=True, model=model, granularity=granularity,
        points=[prediction.ForecastPoint(period_index=h + 1, label=f"t+{h + 1}", predicted=p)
                for h, p in enumerate(predicted)])


def test_forecast_screening_space():
    print("\n[3] Forecast points are screened in the space they were produced in")
    values = _seasonal()
    n = len(values)
    seasonal_path = [10000 + 60 * t + 2500 * math.sin(2 * math.pi * t / 12)
                     for t in range(n, n + 3)]
    ok = anomaly_mod.detect_anomalies(values, forecast=_forecast("SARIMA", seasonal_path),
                                      period=12)
    check(ok.predictive_space == "SEASONAL" and not ok.predictive_warnings,
          "a seasonal forecast that follows the pattern raises no warning")
    flat = [values[-1]] * 3
    naive = anomaly_mod.detect_anomalies(values, forecast=_forecast("NAIVE", flat), period=12)
    check(naive.predictive_space in ("RAW", "DETRENDED") and not naive.predictive_warnings,
          "a naive forecast is not flagged for lacking the seasonal shape")
    shifted = [p + 4000 for p in seasonal_path]
    hit = anomaly_mod.detect_anomalies(values, forecast=_forecast("SARIMA", shifted), period=12)
    check(len(hit.predictive_warnings) == 3
          and all(w.direction == "HIGH" for w in hit.predictive_warnings),
          "a seasonal forecast lifted well above the pattern is warned on every period")


def test_patterns():
    print("\n[4] Spike, sustained shift, unconfirmed")
    values = _flat(30)
    values[8] += 250                                # isolated spike
    values[18] += 250                               # run of three
    values[19] += 260
    values[20] += 270
    values[29] -= 250                               # isolated, latest period
    report = anomaly_mod.detect_anomalies(values)
    pattern = {a.index: a.pattern for a in report.historical_anomalies}
    check(pattern.get(8) == "SPIKE", "an isolated anomaly followed by a normal period is a SPIKE")
    check(all(pattern.get(i) == "SUSTAINED" for i in (18, 19, 20)),
          "consecutive same-direction anomalies are SUSTAINED")
    check(pattern.get(29) == "UNCONFIRMED", "an isolated anomaly in the latest period is UNCONFIRMED")


def _persistence(values, model="NAIVE"):
    proj = prediction.project_series(values, model, 3, 0.95, 12)
    fc = prediction.ForecastResult(
        generated=True, model=proj["model"], granularity="MONTH", historical_values=values,
        points=[prediction.ForecastPoint(period_index=h + 1, label=f"t+{h + 1}", predicted=p,
                                         lower_bound=lo, upper_bound=hi)
                for h, (p, lo, hi) in enumerate(zip(proj["forecasts"], proj["lower"],
                                                    proj["upper"]))])
    report = anomaly_mod.detect_anomalies(values, forecast=fc, period=12)
    return strategies.anomaly_persistence(fc, report).details


def test_persistence_uses_pattern():
    print("\n[5] Anomaly persistence reads the pattern")
    spike = _flat(24)
    spike[-1] += 250
    d = _persistence(spike)
    check(d["pattern"] == "UNCONFIRMED" and d["basis"] == "FORECAST_WITHOUT_LATEST_POINT"
          and d["verdict"] == "RECOVERING",
          "a latest-period spike is not carried forward by a naive model")
    shift = _flat(24)
    for i in (21, 22, 23):
        shift[i] += 250
    d = _persistence(shift)
    check(d["pattern"] == "SUSTAINED" and d["run_length"] == 3 and d["verdict"] == "PERSISTING",
          "a three-period shift is projected to persist")
    old = _flat(24)
    old[-2] += 250
    d = _persistence(old)
    check(d["pattern"] == "SPIKE" and d["basis"] == "OBSERVED_RETURN" and d["verdict"] == "RECOVERING",
          "a spike already followed by a normal period is reported as recovered")


def main() -> int:
    test_detection_methods()
    test_seasonal_space()
    test_forecast_screening_space()
    test_patterns()
    test_persistence_uses_pattern()
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
