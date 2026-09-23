"""
Prediction Stage 5 - Dual-Dimension Adaptive Anomaly Detection.

Two dimensions, one threshold model:

  retrospective - flags observations already in the result set
  prospective   - flags forecast points projected to breach the same bounds

Thresholds are derived from the series' own dispersion (IQR scaling combined
with Z-score normalisation) rather than hardcoded constants, so a stable
series gets tight bounds and a volatile one is not drowned in false alarms.
That adaptivity, applied simultaneously to past and future, is the Stage 5
contribution.
"""

import math
from dataclasses import dataclass, field, asdict


@dataclass
class AnomalyPoint:
    dimension: str = "HISTORICAL"    # HISTORICAL | PREDICTIVE
    index: int = 0
    label: str = ""
    value: float = 0.0
    direction: str = "HIGH"          # HIGH | LOW
    z_score: float = 0.0
    iqr_distance: float = 0.0
    severity: str = "MODERATE"       # MODERATE | SEVERE
    deviation_pct: float = 0.0
    detected_by: list = field(default_factory=list)   # ["IQR"], ["ZSCORE"], both


@dataclass
class AnomalyReport:
    evaluated: bool = False
    method: str = "ADAPTIVE_IQR_ZSCORE"
    detrended: bool = False
    trend_r2: float = 0.0
    lower_threshold: float = 0.0
    upper_threshold: float = 0.0
    median: float = 0.0
    mean: float = 0.0
    std: float = 0.0
    iqr: float = 0.0
    q1: float = 0.0
    q3: float = 0.0
    volatility_regime: str = "STABLE"     # STABLE | MODERATE | VOLATILE
    iqr_multiplier: float = 1.5
    z_threshold: float = 3.0
    historical_anomalies: list = field(default_factory=list)
    predictive_warnings: list = field(default_factory=list)
    skipped_reason: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["historical_anomalies"] = [
            asdict(a) if not isinstance(a, dict) else a for a in self.historical_anomalies
        ]
        d["predictive_warnings"] = [
            asdict(a) if not isinstance(a, dict) else a for a in self.predictive_warnings
        ]
        return d


MIN_POINTS_FOR_ANOMALY = 5

# Above this trend strength, dispersion is measured on residuals rather than
# raw values. On a growing series the raw IQR spans the whole growth range, so
# a genuine local spike sits comfortably inside the fence and is missed. This
# is the single largest source of false negatives in naive IQR detection, and
# removing the deterministic component before measuring spread is what makes
# the threshold genuinely adaptive rather than merely rescaled.
DETREND_R2_THRESHOLD = 0.50


def _quantile(sorted_values: list, q: float) -> float:
    """Linear-interpolation quantile (matches numpy's default 'linear' method)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_values[int(pos)]
    return sorted_values[lo] * (hi - pos) + sorted_values[hi] * (pos - lo)


# Volatility regimes. A volatile series earns wider bands, because at CV > 0.6
# a fixed 1.5*IQR fence flags roughly a fifth of ordinary business months.
_REGIMES = [
    (0.00, 0.20, "STABLE", 1.5, 2.5),
    (0.20, 0.60, "MODERATE", 2.0, 3.0),
    (0.60, float("inf"), "VOLATILE", 2.5, 3.5),
]


def _adaptive_parameters(values: list) -> tuple:
    """Return (regime_name, iqr_multiplier, z_threshold) from the series' own CV."""
    mean_v = sum(values) / len(values)
    if len(values) > 1:
        var = sum((v - mean_v) ** 2 for v in values) / (len(values) - 1)
        std = math.sqrt(var)
    else:
        std = 0.0
    cv = abs(std / mean_v) if mean_v else 0.0
    for low, high, name, k_iqr, z in _REGIMES:
        if low <= cv < high:
            return name, k_iqr, z, mean_v, std
    return "VOLATILE", 2.5, 3.5, mean_v, std


def _linear_baseline(values: list) -> tuple:
    """OLS trend line over the index. Returns (fitted_values, r_squared)."""
    n = len(values)
    if n < 3:
        return [sum(values) / n] * n, 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    if sxx == 0:
        return [mean_y] * n, 0.0
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values)) / sxx
    intercept = mean_y - slope * mean_x
    fitted = [intercept + slope * x for x in xs]
    ss_tot = sum((y - mean_y) ** 2 for y in values)
    if ss_tot == 0:
        return fitted, 1.0
    ss_res = sum((y - f) ** 2 for y, f in zip(values, fitted))
    return fitted, max(0.0, 1.0 - ss_res / ss_tot), slope, intercept


def detect_anomalies(
    values: list,
    labels: list = None,
    forecast=None,
    static_baseline: bool = False,
    allow_detrend: bool = True,
) -> AnomalyReport:
    """
    Run dual-dimension detection.

    When the series carries a strong deterministic trend, dispersion is measured
    on residuals about that trend rather than on raw levels (see
    DETREND_R2_THRESHOLD). Reported anomaly values remain the raw observations,
    so the user sees real numbers, but the *decision* is made in the space where
    "unusual" actually means unusual.

    Args:
        values:   historical measure values in chronological order.
        labels:   display labels aligned to `values`.
        forecast: a ForecastResult; when present its points are screened too.
        static_baseline: use the textbook fixed 1.5*IQR / z=3 rule on raw levels,
                  with no detrending. This is the control condition evaluate.py
                  compares the adaptive method against.
        allow_detrend: set False to force raw-level detection.
    """
    report = AnomalyReport()
    labels = labels or [str(i) for i in range(len(values))]

    if len(values) < MIN_POINTS_FOR_ANOMALY:
        report.skipped_reason = (
            f"Only {len(values)} observations; at least {MIN_POINTS_FOR_ANOMALY} "
            "are needed to estimate a dispersion threshold."
        )
        return report

    # --- choose the detection space -----------------------------------
    fit = _linear_baseline(values)
    baseline, r2 = fit[0], fit[1]
    slope, intercept = (fit[2], fit[3]) if len(fit) > 2 else (0.0, 0.0)
    report.trend_r2 = round(r2, 4)

    detrend = allow_detrend and not static_baseline and r2 >= DETREND_R2_THRESHOLD
    report.detrended = detrend

    if detrend:
        # Work on residuals; the fence is centred on zero by construction.
        working = [v - b for v, b in zip(values, baseline)]
        report.method = "ADAPTIVE_IQR_ZSCORE_DETRENDED"
    else:
        working = list(values)

    ordered = sorted(working)
    q1 = _quantile(ordered, 0.25)
    q3 = _quantile(ordered, 0.75)
    iqr = q3 - q1
    median = _quantile(ordered, 0.5)

    if static_baseline:
        regime, k_iqr, z_threshold = "STATIC", 1.5, 3.0
        mean_v = sum(working) / len(working)
        std = (
            math.sqrt(sum((v - mean_v) ** 2 for v in working) / (len(working) - 1))
            if len(working) > 1
            else 0.0
        )
        report.method = "STATIC_IQR_ZSCORE_BASELINE"
    else:
        # Volatility regime is always judged on the RAW series: it describes the
        # business quantity, not the residual, and a detrended residual would
        # always look "stable" around zero.
        regime, k_iqr, z_threshold, _, _ = _adaptive_parameters(values)
        mean_v = sum(working) / len(working)
        std = (
            math.sqrt(sum((v - mean_v) ** 2 for v in working) / (len(working) - 1))
            if len(working) > 1
            else 0.0
        )

    # A zero IQR (heavily tied series) would collapse the fence onto the
    # quartiles; fall back to standard deviation so detection stays meaningful.
    effective_iqr = iqr if iqr > 0 else (std if std > 0 else abs(median) * 0.1)

    if effective_iqr <= 0:
        # Every value is identical, or identical to its own trend line. There is
        # no dispersion to measure against, so "outlier" is undefined here -
        # refuse rather than divide by a zero scale.
        report.skipped_reason = (
            "The series has zero dispersion"
            + (" about its trend" if detrend else "")
            + "; with no variation there is nothing for an anomaly to deviate from."
        )
        return report

    report.evaluated = True
    report.q1, report.q3, report.iqr = round(q1, 4), round(q3, 4), round(iqr, 4)
    report.median, report.mean, report.std = round(median, 4), round(mean_v, 4), round(std, 4)
    report.volatility_regime = regime
    report.iqr_multiplier = k_iqr
    report.z_threshold = z_threshold
    report.lower_threshold = round(q1 - k_iqr * effective_iqr, 4)
    report.upper_threshold = round(q3 + k_iqr * effective_iqr, 4)

    raw_mean = sum(values) / len(values)
    n_hist = len(values)

    def to_working(raw_value: float, position: int) -> float:
        """Project a raw observation into the space the thresholds live in."""
        if not detrend:
            return raw_value
        # `position` is the index on the same axis the trend was fitted on;
        # forecast points continue that axis past the end of the history.
        return raw_value - (intercept + slope * position)

    def evaluate(raw_value: float, position: int, index: int, label: str, dimension: str):
        value = to_working(raw_value, position)
        z = abs(value - mean_v) / std if std > 0 else 0.0

        breaches_iqr = value > report.upper_threshold or value < report.lower_threshold
        if value > report.upper_threshold:
            direction, distance = "HIGH", (value - report.upper_threshold) / effective_iqr
        elif value < report.lower_threshold:
            direction, distance = "LOW", (report.lower_threshold - value) / effective_iqr
        else:
            # Z-score can still catch a point inside a wide IQR fence.
            if z <= z_threshold:
                return None
            direction = "HIGH" if value > mean_v else "LOW"
            distance = 0.0

        detected_by = []
        if breaches_iqr:
            detected_by.append("IQR")
        if z > z_threshold:
            detected_by.append("ZSCORE")

        return AnomalyPoint(
            dimension=dimension,
            index=index,
            label=label,
            # Always report the observation the user recognises, not the residual.
            value=round(raw_value, 4),
            direction=direction,
            z_score=round(z, 4),
            iqr_distance=round(distance, 4),
            severity="SEVERE" if (z > z_threshold + 1 or distance > 1.5) else "MODERATE",
            deviation_pct=round(
                ((raw_value - raw_mean) / raw_mean * 100.0) if raw_mean else 0.0, 2
            ),
            detected_by=detected_by,
        )

    # --- retrospective dimension ---------------------------------------
    for i, value in enumerate(values):
        found = evaluate(value, i, i, labels[i] if i < len(labels) else str(i), "HISTORICAL")
        if found:
            report.historical_anomalies.append(found)

    # --- prospective dimension -----------------------------------------
    if forecast is not None and getattr(forecast, "generated", False):
        for point in forecast.points:
            found = evaluate(
                point.predicted,
                n_hist - 1 + point.period_index,
                point.period_index,
                point.label,
                "PREDICTIVE",
            )
            if found:
                report.predictive_warnings.append(found)

    return report


def summarize_anomaly_state(report: AnomalyReport) -> str:
    """One-line status used in logs and the CLI demo."""
    if not report.evaluated:
        return f"anomaly detection skipped ({report.skipped_reason})"
    return (
        f"{len(report.historical_anomalies)} historical / "
        f"{len(report.predictive_warnings)} predicted anomalies "
        f"[regime={report.volatility_regime}, band="
        f"{report.lower_threshold:.1f}..{report.upper_threshold:.1f}]"
    )
