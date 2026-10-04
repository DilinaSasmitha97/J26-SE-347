"""
Regression tests for the Stage 3 anomaly engine.

Runnable with plain `python test_anomaly.py` or under pytest.
"""

import random
import sys

import anomaly as anomaly_mod

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


def main() -> int:
    test_detection_methods()
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
