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
    # Historical points only: SPIKE (isolated, the next observation is back in
    # range), SUSTAINED (part of a run of same-direction anomalies, i.e. a level
    # shift) or UNCONFIRMED (isolated and the latest observation, so nothing
    # yet shows whether it is a spike or the start of a shift).
    pattern: str = ""


@dataclass
class AnomalyReport:
    evaluated: bool = False
    method: str = "ADAPTIVE_IQR_ZSCORE"
    detrended: bool = False
    trend_r2: float = 0.0
    seasonal: bool = False                # decided in the STL residual space
    seasonal_strength: float = 0.0
    period: int = 0
    predictive_space: str = ""            # space forecast points were screened in
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

# Which rule flags a point. COMBINED (the default) flags a breach of either the
# IQR fence or the Z-score threshold; IQR and ZSCORE apply one rule alone. The
# single-rule modes exist so the evaluation can measure what each contributes
# (proposal section 3.7).
DETECTION_METHODS = ("COMBINED", "IQR", "ZSCORE")

# Seasonal detection space. A seasonal series swings by its own pattern every
# cycle, so on raw levels (or about a straight trend line) the seasonal peaks
# and troughs set the fence and a genuine outlier sits inside it. When the
# series has at least MIN_CYCLES_FOR_STL full cycles and its STL seasonal
# strength reaches SEASONAL_STRENGTH_THRESHOLD, detection runs on the robust
# STL remainder instead. Strength follows Wang, Smith & Hyndman (2006):
# max(0, 1 - Var(remainder) / Var(seasonal + remainder)).
# Three cycles, not two: with two, each phase's seasonal value is the mean of
# two observations, so a spike is split evenly between itself and its partner
# a year earlier or later and cannot be told apart from the season.
SEASONAL_STRENGTH_THRESHOLD = 0.40
MIN_CYCLES_FOR_STL = 3

# Forecast models whose projection carries the seasonal pattern. Only these are
# screened against the seasonal expectation; a non-seasonal projection (naive,
# Holt, linear) has no seasonal shape, and comparing it with one would flag the
# model's simplification as an anomaly. Those are screened in the level space
# (raw or detrended) the Stage 2 detector uses.
SEASONAL_FORECAST_MODELS = ("SEASONAL_NAIVE", "SARIMA")


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


def _stl_components(values: list, period: int):
    """
    Returns (trend, seasonal, strength, spread_remainder) or None when STL fails.

    Two fits, each used for what it is good at. The ROBUST fit locates the
    expected value: its iterations down-weight an outlier, so the outlier stays
    in the remainder instead of leaking into the seasonal estimate (on 3-4
    cycles a plain fit spreads a spike over its phase and recall on 4-sigma
    spikes falls from 0.83 to 0.23). But with only 3-4 points per phase the
    robust fit hugs the points it keeps, so its remainder is peaked and its
    IQR understates the noise (5 % of clean points flagged). The spread is
    therefore measured on the remainder of the ordinary least-squares fit.
    """
    try:
        import numpy as np
        from statsmodels.tsa.seasonal import STL
    except ImportError:  # pragma: no cover - statsmodels is a hard requirement
        return None
    try:
        # Periodic season: one constant per phase (seasonal_deg=0 over a window
        # wider than the series). The default 7-point seasonal smoother, on a
        # business series of three or four cycles, follows each phase's few
        # points almost exactly and absorbs the outliers it should expose.
        settings = dict(period=period, seasonal=2 * len(values) + 1, seasonal_deg=0)
        fit = STL(values, robust=True, **settings).fit()
        plain = STL(values, robust=False, **settings).fit()
    except (ValueError, np.linalg.LinAlgError):
        return None
    trend, seasonal, resid = list(fit.trend), list(fit.seasonal), list(fit.resid)

    def var(xs):
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / len(xs)

    detrended = [s_ + r for s_, r in zip(seasonal, resid)]
    v_sr = var(detrended)
    strength = max(0.0, 1.0 - var(resid) / v_sr) if v_sr > 0 else 0.0
    return trend, seasonal, strength, list(plain.resid)


def detect_anomalies(
    values: list,
    labels: list = None,
    forecast=None,
    static_baseline: bool = False,
    allow_detrend: bool = True,
    method: str = "COMBINED",
    period: int = None,
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
        method:   COMBINED (IQR fence or Z-score), IQR (fence only) or ZSCORE
                  (Z-score only). Ignored by the static baseline, which is
                  always the textbook combination.
        period:   seasonal period of the series (12 for months, 4 for quarters,
                  ...). With enough cycles and a strong enough seasonal
                  pattern, detection runs on the STL remainder (see
                  SEASONAL_STRENGTH_THRESHOLD). None or 1 disables it.
    """
    if method not in DETECTION_METHODS:
        raise ValueError(f"method must be one of {DETECTION_METHODS}, got {method!r}")
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

    n_hist = len(values)
    stl = None
    if (allow_detrend and not static_baseline and period and period > 1
            and n_hist >= MIN_CYCLES_FOR_STL * period):
        stl = _stl_components(values, period)
        if stl is not None:
            report.seasonal_strength = round(stl[2], 4)
            report.period = period
            if stl[2] < SEASONAL_STRENGTH_THRESHOLD:
                stl = None
    seasonal = stl is not None
    report.seasonal = seasonal

    detrend = (allow_detrend and not static_baseline and not seasonal
               and r2 >= DETREND_R2_THRESHOLD)
    report.detrended = detrend

    if seasonal:
        trend_c, seasonal_c, _, spread_remainder = stl
        # Trend beyond the history: straight line through the last cycle of the
        # STL trend. Season beyond the history: the same phase of the last cycle.
        tail = trend_c[-period:]
        tail_fit = _linear_baseline(tail)
        tail_slope = tail_fit[2] if len(tail_fit) > 2 else 0.0

        def expected_at(position: int) -> float:
            if position < n_hist:
                return trend_c[position] + seasonal_c[position]
            ahead = position - (n_hist - 1)
            phase = n_hist - period + (position - n_hist) % period
            return trend_c[-1] + tail_slope * ahead + seasonal_c[phase]

        # Thresholds come from the plain fit's remainder (see _stl_components);
        # points are judged against the robust expectation in to_working().
        # That remainder is what is left after fitting period - 1 seasonal
        # constants and a loess trend, so it is narrower than the noise it
        # stands for. Widen the spread estimate by sqrt(n / (n - df)), the same
        # correction as the n - p divisor of a regression residual variance.
        trend_window = int(1.5 * period) + 1          # STL's default: smallest odd
        trend_window += 1 - trend_window % 2          # integer above 1.5 * period
        df = (period - 1) + 2.0 * n_hist / trend_window
        scale = math.sqrt(n_hist / max(n_hist - df, 1.0))
        working = [w * scale for w in spread_remainder]
        report.method = "ADAPTIVE_IQR_ZSCORE_STL"
    elif detrend:
        def expected_at(position: int) -> float:
            return intercept + slope * position

        # Work on residuals; the fence is centred on zero by construction.
        working = [v - b for v, b in zip(values, baseline)]
        report.method = "ADAPTIVE_IQR_ZSCORE_DETRENDED"
    else:
        expected_at = None
        working = list(values)
    if method != "COMBINED" and not static_baseline:
        report.method = report.method.replace("IQR_ZSCORE", method)

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

    def to_working(raw_value: float, position: int) -> float:
        """Project a raw observation into the space the thresholds live in."""
        if expected_at is None:
            return raw_value
        # `position` is the index on the same axis the baseline was fitted on;
        # forecast points continue that axis past the end of the history.
        return raw_value - expected_at(position)

    def evaluate(raw_value: float, position: int, index: int, label: str, dimension: str):
        value = to_working(raw_value, position)
        z = abs(value - mean_v) / std if std > 0 else 0.0

        breaches_iqr = value > report.upper_threshold or value < report.lower_threshold
        breaches_z = z > z_threshold
        if not static_baseline:
            if method == "IQR" and not breaches_iqr:
                return None
            if method == "ZSCORE" and not breaches_z:
                return None
        if value > report.upper_threshold:
            direction, distance = "HIGH", (value - report.upper_threshold) / effective_iqr
        elif value < report.lower_threshold:
            direction, distance = "LOW", (report.lower_threshold - value) / effective_iqr
        else:
            # Z-score can still catch a point inside a wide IQR fence.
            if not breaches_z:
                return None
            direction = "HIGH" if value > mean_v else "LOW"
            distance = 0.0

        detected_by = []
        if breaches_iqr and (static_baseline or method != "ZSCORE"):
            detected_by.append("IQR")
        if breaches_z and (static_baseline or method != "IQR"):
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
    classify_patterns(report.historical_anomalies, n_hist)

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
        report.predictive_space = "SEASONAL" if seasonal else (
            "DETRENDED" if detrend else "RAW")
        if seasonal and getattr(forecast, "model", "") not in SEASONAL_FORECAST_MODELS:
            level = detect_anomalies(values, labels, forecast=forecast, method=method,
                                     allow_detrend=allow_detrend)
            report.predictive_warnings = level.predictive_warnings
            report.predictive_space = "DETRENDED" if level.detrended else "RAW"

    return report


def classify_patterns(anomalies: list, n_hist: int) -> None:
    """
    Label each historical anomaly SPIKE, SUSTAINED or UNCONFIRMED (in place).

    A spike and the start of a level shift look identical at the moment they
    happen; only the observations after them tell them apart. So the label is
    read from the neighbours: a run of two or more consecutive same-direction
    anomalies is SUSTAINED, an isolated one followed by a normal observation is
    a SPIKE, and an isolated one in the latest period is UNCONFIRMED.
    """
    direction_at = {a.index: a.direction for a in anomalies}
    for a in anomalies:
        neighbours = (direction_at.get(a.index - 1), direction_at.get(a.index + 1))
        if a.direction in neighbours:
            a.pattern = "SUSTAINED"
        elif a.index >= n_hist - 1:
            a.pattern = "UNCONFIRMED"
        else:
            a.pattern = "SPIKE"


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
