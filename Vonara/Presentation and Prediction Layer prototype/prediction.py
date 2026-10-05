"""
Prediction Layer - Stages 1 to 4.

  Stage 1  Intent-to-Prediction Mapping   `map_intent_to_strategy`
  Stage 2  Data Readiness Classifier      `assess_readiness`
  Stage 3  Dual-Signal Model Selection    `select_model`
  Stage 4  Confidence-Bounded Forecasting `generate_forecast`

Everything degrades gracefully: statsmodels/scipy are optional. When they are
absent the selector simply never chooses SARIMA, and the pure-Python estimators
(linear regression, Holt exponential smoothing, weighted moving average) carry
the load. That keeps the layer runnable in a bare environment and keeps the
evaluation numbers reproducible.
"""

import math
from dataclasses import dataclass, field, asdict
import warnings
from datetime import datetime, timedelta

from profiler import log_step
from result_profiler import extract_series
from schemas import (
    ForecastModel,
    Granularity,
    PredictionStrategy,
    QueryIntent,
    ReadinessVerdict,
    SEASONAL_PERIOD,
)

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False

try:
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    from statsmodels.tsa.stattools import acf, adfuller, kpss

    _HAS_STATSMODELS = True
except ImportError:  # pragma: no cover
    _HAS_STATSMODELS = False


# ==========================================================================
# Stage 1 - Intent-to-Prediction Mapping Algorithm
# ==========================================================================

# The formal mapping. Each entry states the predictive question the intent
# implies, and the model family that answers it. This table IS the research
# contribution for Stage 1: model choice becomes a function of query semantics
# rather than an arbitrary default.
INTENT_STRATEGY_MAP = {
    QueryIntent.TREND_ANALYSIS: (
        PredictionStrategy.TEMPORAL_FORECAST,
        "A measure tracked over time extends naturally into future periods.",
    ),
    QueryIntent.COMPARISON: (
        PredictionStrategy.CATEGORY_TRAJECTORY,
        "Each compared category is forecast separately to project which leads next.",
    ),
    QueryIntent.RANKING: (
        PredictionStrategy.CATEGORY_TRAJECTORY,
        "Ranked entities are projected forward to anticipate rank changes.",
    ),
    QueryIntent.DISTRIBUTION: (
        PredictionStrategy.DISTRIBUTION_SHIFT,
        "Distributional moments are projected to describe how the spread moves.",
    ),
    QueryIntent.PROPORTION: (
        PredictionStrategy.DISTRIBUTION_SHIFT,
        "Component shares are projected to describe compositional drift.",
    ),
    QueryIntent.ANOMALY_DETECTION: (
        PredictionStrategy.ANOMALY_PERSISTENCE,
        "Forecast values are tested against adaptive thresholds to judge persistence.",
    ),
    QueryIntent.CORRELATION: (
        PredictionStrategy.NONE,
        "A cross-sectional relationship carries no time axis to extrapolate.",
    ),
    QueryIntent.KPI_SINGLE_VALUE: (
        PredictionStrategy.NONE,
        "A single scalar has no series to extend.",
    ),
    QueryIntent.DETAIL_LOOKUP: (
        PredictionStrategy.NONE,
        "Row retrieval is not a predictive question.",
    ),
    QueryIntent.UNKNOWN: (
        PredictionStrategy.NONE,
        "Intent undetermined; prediction withheld.",
    ),
}


def map_intent_to_strategy(analysis) -> dict:
    """
    Stage 1. Translate the classified intent into a predictive strategy.

    An explicit user forecast request promotes a NONE strategy to
    TEMPORAL_FORECAST, because a direct instruction outranks the taxonomy
    default - but the promotion is recorded so the decision stays auditable.
    """
    intent = QueryIntent(analysis.primary_intent)
    strategy, rationale = INTENT_STRATEGY_MAP[intent]
    promoted = False

    if strategy is PredictionStrategy.NONE and analysis.prediction_trigger == "EXPLICIT":
        strategy = PredictionStrategy.TEMPORAL_FORECAST
        rationale = (
            f"Intent '{intent.value}' implies no forecast, but the user explicitly "
            "requested one; promoted to TEMPORAL_FORECAST."
        )
        promoted = True

    return {
        "intent": intent.value,
        "strategy": strategy.value,
        "rationale": rationale,
        "promoted_by_explicit_request": promoted,
        "prediction_requested": analysis.prediction_required,
    }


# ==========================================================================
# Stage 2 - Data Readiness Classifier
# ==========================================================================

# Gate thresholds. MIN_POINTS_* are the smallest samples at which each model's
# parameters are identifiable; they are deliberately low because multi-tenant
# business result sets are small (12-36 points is typical).
MIN_POINTS_ANY = 4
MIN_POINTS_TREND = 6
MIN_POINTS_SEASONAL = 24          # 2 full cycles at monthly granularity

# Gate 3 - forecastability. The question is asked on the series' own history:
# forecast each of the last SIGNAL_TEST_ORIGINS points one step ahead from the
# data before it, with each simple candidate, and keep the best mean absolute
# error. If even that best error exceeds MAX_EXPECTED_ERROR of the series level,
# noise dominates and no forecast is meaningful. The threshold is chosen on the
# DEVELOPMENT data (synthetic + M4 seed 2026) as the best F1 at refusing
# unreliable forecasts among thresholds whose refusals are right >= 80% of the
# time, then scored once on the held-out M4 seed-2027 sample
# (evaluate_forecasting.py). The first Stage 2 run chose 0.15 on synthetic data
# alone; its refusal precision on real data was 0.59.
MIN_POINTS_SIGNAL_TEST = 8
SIGNAL_TEST_ORIGINS = 6
MAX_EXPECTED_ERROR = 0.20

# Data-quality policy (Stage 2, proposal 3.5). Values that cannot be read
# (NULLs, unparseable cells) and calendar periods with no row are measured
# separately: a missing VALUE is information lost, a missing PERIOD is a hole
# in the time axis that a model would silently close up.
MAX_MISSING_VALUE_RATIO = 0.20    # more unreadable cells than this -> NOT_READY
MAX_MISSING_PERIOD_RATIO = 0.25   # more empty periods than this -> NOT_READY
NEAR_CONSTANT_CV = 0.01           # below this, a forecast adds next to nothing
MIN_POINTS_STATIONARITY = 12      # ADF/KPSS have almost no power below this

# Three-level decision (proposal 3.5 / FR05).
DECISION_READY = "READY"
DECISION_WARN = "READY_WITH_WARNING"
DECISION_NOT_READY = "NOT_READY"
DECISION_NOT_EVALUATED = "NOT_EVALUATED"

# The pre-Stage-2 rule, kept only so the benchmark can compare against it.
LEGACY_MAX_NOISE_RATIO = 1.5      # coefficient of variation ceiling
LEGACY_MIN_SIGNAL_R2 = 0.05       # below this, no exploitable structure


@dataclass
class ReadinessReport:
    verdict: str = ReadinessVerdict.NOT_TEMPORAL.value
    is_ready: bool = False
    temporal_valid: bool = False
    statistically_sufficient: bool = False
    signal_adequate: bool = False
    n_points: int = 0
    dropped_rows: int = 0
    granularity: str = Granularity.NONE.value
    coefficient_of_variation: float = 0.0
    trend_r2: float = 0.0
    expected_relative_error: float = None   # best in-history one-step error / level
    skill_vs_naive: float = None            # best in-history MAE / naive MAE
    signal_test: dict = field(default_factory=dict)
    # Three-level outcome + machine-readable reasons (proposal 3.5 / FR05).
    decision: str = DECISION_NOT_EVALUATED
    reason_codes: list = field(default_factory=list)
    warnings: list = field(default_factory=list)     # [{"code", "message"}]
    stationarity: dict = field(default_factory=dict)
    missing_value_ratio: float = 0.0
    missing_period_ratio: float = 0.0
    filled_periods: int = 0
    reason: str = ""
    checks: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _linear_fit(values: list) -> tuple:
    """OLS of value on index. Returns (slope, intercept, r_squared)."""
    n = len(values)
    if n < 2:
        return 0.0, (values[0] if values else 0.0), 0.0
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values))
    if sxx == 0:
        return 0.0, mean_y, 0.0
    slope = sxy / sxx
    intercept = mean_y - slope * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in values)
    if ss_tot == 0:
        return slope, intercept, 1.0
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, values))
    return slope, intercept, max(0.0, 1.0 - ss_res / ss_tot)


def in_history_errors(values: list, models: list, origins: int = SIGNAL_TEST_ORIGINS,
                      period: int = 12) -> dict:
    """
    One-step-ahead mean absolute error of each model on the series' own history.

    For each of the last `origins` positions t, the model is fitted to
    values[:t] and asked for values[t]. Only data before t is ever used, so
    this is an honest (if short) out-of-sample test that needs no future data.
    A seasonal naive is evaluated only at origins with a full cycle behind them.
    Returns {model: (mae, n_origins)}; models with no valid origin are omitted.
    """
    n = len(values)
    first = max(4, n - origins)
    out = {}
    for model in models:
        errors = []
        for t in range(first, n):
            if model == ForecastModel.SEASONAL_NAIVE.value and t <= period:
                continue
            forecast = project_series(values[:t], model, 1, 0.95, period)["forecasts"][0]
            errors.append(abs(values[t] - forecast))
        if errors:
            out[model] = (sum(errors) / len(errors), len(errors))
    return out


def forecastability(values: list, period: int = 12) -> dict:
    """
    Gate 3: how predictable is this series, judged only from its own history?

    Candidates are cheap and assumption-light (naive, seasonal naive, linear,
    Holt), so the test measures the data rather than any one model's fit.
    """
    n = len(values)
    if n < MIN_POINTS_SIGNAL_TEST:
        return {"assessed": False, "reason": f"{n} < {MIN_POINTS_SIGNAL_TEST} points"}
    candidates = [ForecastModel.NAIVE.value, ForecastModel.LINEAR_REGRESSION.value,
                  ForecastModel.EXPONENTIAL_SMOOTHING.value]
    if period > 1 and n > period + 2:
        candidates.append(ForecastModel.SEASONAL_NAIVE.value)
    errors = in_history_errors(values, candidates, SIGNAL_TEST_ORIGINS, period)
    level = sum(abs(v) for v in values) / n or 1e-9
    best_model = min(errors, key=lambda m: errors[m][0])
    best_mae = errors[best_model][0]
    naive_mae = errors[ForecastModel.NAIVE.value][0]
    return {
        "assessed": True,
        "origins": errors[ForecastModel.NAIVE.value][1],
        "mae_by_model": {m: round(e, 4) for m, (e, _) in errors.items()},
        "best_model": best_model,
        "expected_relative_error": best_mae / level,
        "skill_vs_naive": best_mae / naive_mae if naive_mae else 1.0,
        "threshold": MAX_EXPECTED_ERROR,
    }


def _period_index(d: datetime, granularity: str, origin: datetime) -> int:
    """Integer position of a date on the regular calendar grid of `granularity`."""
    g = Granularity(granularity) if granularity else Granularity.NONE
    if g is Granularity.MONTH:
        return (d.year - origin.year) * 12 + d.month - origin.month
    if g is Granularity.QUARTER:
        return (d.year - origin.year) * 4 + (d.month - 1) // 3 - (origin.month - 1) // 3
    if g is Granularity.YEAR:
        return d.year - origin.year
    if g is Granularity.WEEK:
        return (d.date() - origin.date()).days // 7
    if g is Granularity.HOUR:
        return int((d - origin).total_seconds() // 3600)
    return (d.date() - origin.date()).days


def prepare_series(rows: list, time_column: str, value_column: str,
                   granularity: str) -> dict:
    """
    Turn result rows into the regular series a model is allowed to see.

    1. Rows whose date or value cannot be read are dropped and counted.
    2. The remaining observations are placed on the calendar grid of the
       detected granularity (months, quarters, weeks, ...). Daily data that
       contains no weekend dates is treated as a business-day calendar, so
       weekends are not counted as missing.
    3. Empty grid positions are filled by linear interpolation between their
       neighbours - an explicit, documented rule - and reported, so readiness
       can warn about them (few) or refuse the series (many).

    The interpolated points exist only for the model: anomaly detection and
    summary statements never report a filled value as an observation.
    """
    dates, values = extract_series(rows, time_column, value_column)
    out = {
        "dates": list(dates), "values": list(values), "n_rows": len(rows),
        "dropped": len(rows) - len(values), "expected_periods": len(values),
        "missing_periods": 0, "filled_indices": [], "calendar": "NONE",
        "duplicate_periods": 0,
    }
    if len(values) < 2 or not granularity or granularity == Granularity.NONE.value:
        return out

    g = Granularity(granularity)
    business_days = (g is Granularity.DAY and all(d.weekday() < 5 for d in dates))
    out["calendar"] = "BUSINESS_DAY" if business_days else g.value
    origin = dates[0]

    if business_days:
        grid, cur = [], origin
        while cur <= dates[-1]:
            if cur.weekday() < 5:
                grid.append(cur)
            cur += timedelta(days=1)
        position = {d.date(): i for i, d in enumerate(grid)}
        index = [position.get(d.date()) for d in dates]
        slot_dates = list(grid)
    else:
        index = [_period_index(d, granularity, origin) for d in dates]
        slot_dates = None

    if any(i is None for i in index) or len(set(index)) != len(index):
        # Two observations fall in one period: the granularity was misread or
        # the data is not one value per period. Leave the series untouched and
        # let readiness report it.
        out["duplicate_periods"] = len(index) - len(set(i for i in index if i is not None))
        return out

    span = index[-1] + 1
    by_slot = dict(zip(index, values))
    filled, series = [], []
    for slot in range(span):
        if slot in by_slot:
            series.append(by_slot[slot])
            continue
        lo = max(i for i in by_slot if i < slot)
        hi = min(i for i in by_slot if i > slot)
        weight = (slot - lo) / (hi - lo)
        series.append(by_slot[lo] + weight * (by_slot[hi] - by_slot[lo]))
        filled.append(slot)

    if slot_dates is None:
        slot_dates = [_next_timestamp(origin, granularity, s) if s else origin
                      for s in range(span)]
    out.update({
        "dates": slot_dates, "values": series, "expected_periods": span,
        "missing_periods": len(filled), "filled_indices": filled,
    })
    return out


def stationarity_evidence(values: list) -> dict:
    """
    ADF and KPSS read together (proposal 3.5; Dickey & Fuller [5], KPSS [6]).

    The two tests have opposite null hypotheses - ADF: "has a unit root",
    KPSS: "is stationary" - so their agreement is informative and their
    disagreement is itself a finding:

      ADF rejects, KPSS does not   -> STATIONARY
      ADF does not, KPSS rejects   -> NON_STATIONARY (trend or unit root:
                                      handled by differencing / trend models)
      both reject                  -> CONFLICT (typical of a level shift or
                                      changing variance: a forecast caution)
      neither rejects              -> INCONCLUSIVE (too little data to tell;
                                      expected on short series)
    """
    if not _HAS_STATSMODELS or len(values) < MIN_POINTS_STATIONARITY:
        return {"assessed": False,
                "reason": f"fewer than {MIN_POINTS_STATIONARITY} points or statsmodels missing"}
    if len({round(v, 10) for v in values}) <= 1:
        return {"assessed": False, "reason": "constant series"}
    try:
        with warnings.catch_warnings():
            # KPSS warns when its p-value is outside the tabulated 0.01-0.10
            # range; the bound it returns is still the right side of 0.05.
            warnings.simplefilter("ignore")
            adf_p = float(adfuller(values, autolag="AIC")[1])
            kpss_p = float(kpss(values, regression="c", nlags="auto")[1])
    except Exception as exc:  # noqa: BLE001 - both tests fail on degenerate input
        return {"assessed": False, "reason": f"test failed ({exc})"}
    adf_stationary, kpss_stationary = adf_p < 0.05, kpss_p >= 0.05
    if adf_stationary and kpss_stationary:
        verdict = "STATIONARY"
    elif not adf_stationary and not kpss_stationary:
        verdict = "NON_STATIONARY"
    elif adf_stationary:
        verdict = "CONFLICT"
    else:
        verdict = "INCONCLUSIVE"
    return {"assessed": True, "adf_p_value": round(adf_p, 4),
            "kpss_p_value": round(kpss_p, 4), "verdict": verdict}


def legacy_signal_adequate(values: list) -> bool:
    """The pre-Stage-2 Gate 3 (CV/R² rule). Benchmark comparison only."""
    mean_v = sum(values) / len(values)
    std = math.sqrt(sum((v - mean_v) ** 2 for v in values) / (len(values) - 1))
    cv = abs(std / mean_v) if mean_v else float("inf")
    _, _, r2 = _linear_fit(values)
    return not (cv > LEGACY_MAX_NOISE_RATIO and r2 < LEGACY_MIN_SIGNAL_R2)


_VERDICT_CODES = {
    ReadinessVerdict.NOT_TEMPORAL.value: "NO_TIME_AXIS",
    ReadinessVerdict.MULTI_SERIES.value: "MULTI_SERIES",
    ReadinessVerdict.NOT_AGGREGATED.value: "NOT_AGGREGATED",
    ReadinessVerdict.INSUFFICIENT_POINTS.value: "INSUFFICIENT_POINTS",
    ReadinessVerdict.DEGENERATE.value: "CONSTANT_SERIES",
    ReadinessVerdict.LOW_SIGNAL.value: "LOW_SIGNAL",
}


PARTIAL_EDGE_RATIO = 0.40       # an edge period below this share of the median is flagged
MIN_POINTS_PARTIAL_EDGE = 6


def _partial_edge_periods(values: list) -> list:
    """'first' / 'last' when that period is far below the median of the others."""
    if len(values) < MIN_POINTS_PARTIAL_EDGE or min(values) < 0:
        return []
    inner = sorted(values[1:-1])
    median = inner[len(inner) // 2]
    if median <= 0:
        return []
    return [name for name, v in (("first", values[0]), ("last", values[-1]))
            if v < PARTIAL_EDGE_RATIO * median]


def _warn(report, code: str, message: str) -> None:
    report.warnings.append({"code": code, "message": message})
    report.reason_codes.append(code)


def assess_readiness(profile, rows: list, value_column: str = None) -> ReadinessReport:
    """
    Stage 2. Decide whether this result set can support a forecast at all.

    Returns a three-level `decision` - READY, READY_WITH_WARNING or NOT_READY -
    with `reason_codes`, alongside the detailed `verdict`. Gates, in order:
    temporal validity, data completeness (unreadable values, empty periods),
    statistical sufficiency, signal quality (constant / near-constant /
    forecastability), plus ADF+KPSS stationarity evidence. A refusal always
    names its reason; a caution never blocks the forecast but travels with it.
    """
    report = _assess_readiness(profile, rows, value_column)
    if report.is_ready:
        report.decision = DECISION_WARN if report.warnings else DECISION_READY
    else:
        report.decision = DECISION_NOT_READY
        code = _VERDICT_CODES.get(report.verdict)
        if code and code not in report.reason_codes:
            report.reason_codes.insert(0, code)
    return report


def _assess_readiness(profile, rows: list, value_column: str = None) -> ReadinessReport:
    report = ReadinessReport()

    # --- Gate 1: temporal validity ------------------------------------
    if not profile.temporal_column:
        report.verdict = ReadinessVerdict.NOT_TEMPORAL.value
        report.reason = "No column in the result set could be interpreted as a time axis."
        report.checks.append("temporal_validity: FAIL (no temporal column)")
        return report

    value_column = value_column or (
        profile.measure_columns[0] if profile.measure_columns else None
    )
    if not value_column:
        report.verdict = ReadinessVerdict.NOT_TEMPORAL.value
        report.reason = "No numeric measure column available to forecast."
        report.checks.append("temporal_validity: FAIL (no measure column)")
        return report

    layout = getattr(profile, "layout", "SINGLE")
    if layout == "GROUPED":
        report.verdict = ReadinessVerdict.MULTI_SERIES.value
        report.granularity = profile.granularity
        report.temporal_valid = True
        report.reason = (
            f"The result holds one series per '{profile.group_column}'; they are "
            f"forecast separately rather than as one mixed series."
        )
        report.checks.append(f"temporal_validity: MULTI_SERIES (grouped by '{profile.group_column}')")
        return report
    if layout == "EVENTS":
        report.verdict = ReadinessVerdict.NOT_AGGREGATED.value
        report.granularity = profile.granularity
        report.reason = (
            f"The result has several rows per period with no grouping column, so there "
            f"is no single value per period to forecast; ask for a total or an average "
            f"per period instead."
        )
        report.checks.append("temporal_validity: FAIL (several unaggregated rows per period)")
        return report

    prepared = prepare_series(rows, profile.temporal_column, value_column, profile.granularity)
    values = prepared["values"]
    report.dropped_rows = prepared["dropped"]
    report.granularity = profile.granularity
    report.temporal_valid = True
    report.checks.append(
        f"temporal_validity: PASS (axis='{profile.temporal_column}', "
        f"granularity={profile.granularity})"
    )

    # --- Gate 1b: completeness ------------------------------------------
    n_rows = max(1, prepared["n_rows"])
    report.missing_value_ratio = round(prepared["dropped"] / n_rows, 4)
    if report.missing_value_ratio > MAX_MISSING_VALUE_RATIO:
        report.verdict = ReadinessVerdict.INCOMPLETE.value
        report.reason_codes.append("TOO_MANY_MISSING_VALUES")
        report.reason = (
            f"{prepared['dropped']} of {prepared['n_rows']} rows have no usable date or "
            f"value (limit {MAX_MISSING_VALUE_RATIO * 100:.0f}%), too many to forecast from."
        )
        report.checks.append(f"completeness: FAIL ({report.missing_value_ratio * 100:.0f}% unreadable)")
        return report
    if prepared["dropped"]:
        _warn(report, "MISSING_VALUES_DROPPED",
              f"{prepared['dropped']} of {prepared['n_rows']} rows had no usable value and "
              "were left out.")

    expected = max(1, prepared["expected_periods"])
    report.missing_period_ratio = round(prepared["missing_periods"] / expected, 4)
    if report.missing_period_ratio > MAX_MISSING_PERIOD_RATIO:
        report.verdict = ReadinessVerdict.INCOMPLETE.value
        report.reason_codes.append("IRREGULAR_INTERVALS")
        report.reason = (
            f"{prepared['missing_periods']} of {expected} periods between the first and last "
            f"date have no data (limit {MAX_MISSING_PERIOD_RATIO * 100:.0f}%); filling that "
            "many gaps would invent most of the series."
        )
        report.checks.append(f"regularity: FAIL ({report.missing_period_ratio * 100:.0f}% of periods empty)")
        return report
    if prepared["missing_periods"]:
        report.filled_periods = prepared["missing_periods"]
        _warn(report, "MISSING_PERIODS_INTERPOLATED",
              f"{prepared['missing_periods']} of {expected} periods had no data and were "
              "filled by linear interpolation for the forecast only.")
    if prepared["duplicate_periods"]:
        report.verdict = ReadinessVerdict.INCOMPLETE.value
        report.reason_codes.append("IRREGULAR_INTERVALS")
        report.reason = (
            f"The dates do not fall on a regular {profile.granularity.lower()} calendar "
            f"({prepared['duplicate_periods']} periods hold more than one row), so there "
            "is no single value per period to forecast."
        )
        report.checks.append("regularity: FAIL (dates off any regular calendar)")
        return report
    report.checks.append(
        f"regularity: PASS ({prepared['missing_periods']} empty periods filled, "
        f"calendar={prepared['calendar']})"
    )
    report.n_points = len(values)

    # --- Gate 2: statistical sufficiency ------------------------------
    if report.n_points < MIN_POINTS_ANY:
        report.verdict = ReadinessVerdict.INSUFFICIENT_POINTS.value
        report.reason = (
            f"Only {report.n_points} usable observations; at least "
            f"{MIN_POINTS_ANY} are required for any forecast."
        )
        report.checks.append(f"sufficiency: FAIL ({report.n_points} < {MIN_POINTS_ANY})")
        return report
    report.statistically_sufficient = True
    report.checks.append(f"sufficiency: PASS ({report.n_points} observations)")

    # --- Gate 3: signal quality ---------------------------------------
    mean_v = sum(values) / len(values)
    if len({round(v, 10) for v in values}) == 1:
        report.verdict = ReadinessVerdict.DEGENERATE.value
        report.reason = "The series is constant; a forecast would carry no information."
        report.checks.append("signal_quality: FAIL (constant series)")
        return report

    variance = sum((v - mean_v) ** 2 for v in values) / (len(values) - 1)
    std = math.sqrt(variance)
    cv = abs(std / mean_v) if mean_v else float("inf")
    _, _, r2 = _linear_fit(values)

    report.coefficient_of_variation = round(cv, 4)
    report.trend_r2 = round(r2, 4)
    if cv < NEAR_CONSTANT_CV:
        _warn(report, "NEAR_CONSTANT",
              f"Values vary by under {NEAR_CONSTANT_CV * 100:.0f}% of their level; the "
              "forecast will add little beyond the current value.")

    # A first or last period far below the rest is often incomplete: data that
    # starts mid-week, or "this month so far". A forecast built on a partial
    # last period starts from a level that is not real. Rows alone cannot prove
    # a period is partial - a genuine collapse looks the same - so this only
    # discloses the risk; nothing is dropped (Stage 6: integration fixture F07,
    # whose first "week" held 3 tickets against a typical 31).
    edge = _partial_edge_periods(values)
    for position in edge:
        _warn(report, "PARTIAL_EDGE_PERIOD",
              f"The {position} period is under {PARTIAL_EDGE_RATIO * 100:.0f}% of the typical "
              "period and may be incomplete (for example a period still in progress); "
              "check it before relying on the forecast.")

    report.stationarity = stationarity_evidence(values)
    if report.stationarity.get("verdict") == "CONFLICT":
        _warn(report, "STATIONARITY_CONFLICT",
              "The ADF and KPSS stationarity tests disagree, which usually means a level "
              "shift or changing variability; treat the forecast range with care.")
    elif report.stationarity.get("assessed"):
        report.reason_codes.append(f"STATIONARITY_{report.stationarity['verdict']}")

    period = SEASONAL_PERIOD.get(Granularity(profile.granularity), 1) \
        if profile.granularity else 1
    test = forecastability(values, period)
    report.signal_test = test

    if not test["assessed"]:
        # Too short to judge predictability from its own history. Stage 3 will
        # use the weighted moving average, the conservative short-series choice.
        report.signal_adequate = True
        report.checks.append(
            f"signal_quality: NOT ASSESSED ({report.n_points} < "
            f"{MIN_POINTS_SIGNAL_TEST} points for an in-history test); proceeding"
        )
        _warn(report, "SIGNAL_NOT_ASSESSED",
              f"Only {report.n_points} periods of history: too few to test how predictable "
              "the series is, so the forecast uses a conservative moving average.")
    else:
        err = test["expected_relative_error"]
        report.expected_relative_error = round(err, 4)
        report.skill_vs_naive = round(test["skill_vs_naive"], 4)
        detail = (
            f"best in-history one-step error {err * 100:.1f}% of level "
            f"({test['best_model']}, {test['origins']} origins)"
        )
        if err > MAX_EXPECTED_ERROR:
            report.verdict = ReadinessVerdict.LOW_SIGNAL.value
            report.reason = (
                f"Series is dominated by noise: on its own history, the best simple "
                f"forecast missed by {err * 100:.0f}% of the typical value on average "
                f"(limit {MAX_EXPECTED_ERROR * 100:.0f}%), so a forecast would not be "
                "meaningful."
            )
            report.checks.append(f"signal_quality: FAIL ({detail})")
            return report
        report.signal_adequate = True
        report.checks.append(f"signal_quality: PASS ({detail})")

    report.is_ready = True
    report.verdict = ReadinessVerdict.READY.value
    report.reason = ("All readiness gates passed." if not report.warnings else
                     "Ready, with cautions: " + " ".join(w["message"] for w in report.warnings))
    return report


# ==========================================================================
# Stage 3 - Dual-Signal Model Selection
# ==========================================================================


@dataclass
class ModelSelection:
    model: str = ForecastModel.NONE.value
    reason: str = ""
    seasonal_period: int = 1
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _adf_stationarity(values: list) -> tuple:
    """Augmented Dickey-Fuller. Returns (is_stationary, p_value)."""
    if not _HAS_STATSMODELS or len(values) < 8:
        return None, None
    try:
        p_value = float(adfuller(values, autolag="AIC")[1])
        return p_value < 0.05, p_value
    except Exception:  # noqa: BLE001 - ADF is fragile on short/degenerate series
        return None, None


def _seasonal_strength(values: list, period: int) -> float:
    """
    Autocorrelation at the seasonal lag - the practical test for seasonality.

    Returns 0.0 when the series is too short to evaluate the lag.
    """
    if period <= 1 or len(values) < period * 2:
        return 0.0
    if _HAS_STATSMODELS:
        try:
            coefs = acf(values, nlags=period, fft=False)
            return float(abs(coefs[period]))
        except Exception:  # noqa: BLE001
            pass
    # Pure-Python Pearson autocorrelation at the seasonal lag.
    n = len(values)
    mean_v = sum(values) / n
    denom = sum((v - mean_v) ** 2 for v in values)
    if denom == 0:
        return 0.0
    num = sum(
        (values[i] - mean_v) * (values[i - period] - mean_v) for i in range(period, n)
    )
    return abs(num / denom)


SEASONAL_ACF_THRESHOLD = 0.35
VOLATILITY_THRESHOLD = 0.45     # CV above which the series counts as volatile
STRONG_TREND_R2 = 0.55


def _rule_selection(analysis, readiness: ReadinessReport, values: list) -> ModelSelection:
    """
    Stage 3 rules. Choose a forecasting model from TWO signal families:

      semantic  - the classified query intent (what the user is asking)
      statistical - stationarity, seasonal autocorrelation, trend R², volatility

    Neither signal alone is sufficient: intent knows the user wants a trend but
    not whether the data is seasonal; statistics know the data is seasonal but
    not whether the user is comparing categories. The combination is the
    contribution.
    """
    selection = ModelSelection()
    if not readiness.is_ready:
        selection.reason = f"Readiness gate returned {readiness.verdict}."
        return selection

    intent = QueryIntent(analysis.primary_intent)
    n = len(values)
    period = SEASONAL_PERIOD.get(Granularity(readiness.granularity), 1)

    slope, _, r2 = _linear_fit(values)
    mean_v = sum(values) / n
    std = math.sqrt(sum((v - mean_v) ** 2 for v in values) / (n - 1)) if n > 1 else 0.0
    cv = abs(std / mean_v) if mean_v else float("inf")
    seasonality = _seasonal_strength(values, period)
    is_stationary, adf_p = _adf_stationarity(values)

    selection.seasonal_period = period
    selection.signals = {
        "semantic_intent": intent.value,
        "n_points": n,
        "trend_r2": round(r2, 4),
        "trend_slope": round(slope, 6),
        "coefficient_of_variation": round(cv, 4),
        "seasonal_lag": period,
        "seasonal_acf": round(seasonality, 4),
        "adf_stationary": is_stationary,
        "adf_p_value": round(adf_p, 4) if adf_p is not None else None,
        "stationarity": stationarity_evidence(values),
        "statsmodels_available": _HAS_STATSMODELS,
    }

    # --- decision rules, most specific first ---------------------------
    if n < MIN_POINTS_TREND:
        selection.model = ForecastModel.WEIGHTED_MOVING_AVERAGE.value
        selection.reason = (
            f"Only {n} points: below the {MIN_POINTS_TREND}-point threshold at which "
            "trend or seasonal parameters are identifiable, so a weighted moving "
            "average is the only defensible estimator."
        )
        return selection

    seasonal_ready = (
        _HAS_STATSMODELS
        and period > 1
        and n >= MIN_POINTS_SEASONAL
        and seasonality >= SEASONAL_ACF_THRESHOLD
    )

    if intent in (QueryIntent.TREND_ANALYSIS, QueryIntent.ANOMALY_DETECTION) and seasonal_ready:
        selection.model = ForecastModel.SARIMA.value
        selection.reason = (
            f"Trend-oriented intent with seasonal structure (ACF at lag {period} = "
            f"{seasonality:.2f} over {n} points): SARIMA models level and season jointly."
        )
        return selection

    if intent is QueryIntent.TREND_ANALYSIS and r2 >= STRONG_TREND_R2:
        selection.model = ForecastModel.LINEAR_REGRESSION.value
        selection.reason = (
            f"Trend intent with strong linear structure (R² = {r2:.2f}): "
            "ordinary least squares extrapolates it with the tightest intervals."
        )
        return selection

    if intent in (QueryIntent.COMPARISON, QueryIntent.RANKING, QueryIntent.PROPORTION) and cv > VOLATILITY_THRESHOLD:
        selection.model = ForecastModel.EXPONENTIAL_SMOOTHING.value
        selection.reason = (
            f"Category-trajectory intent over volatile data (CV = {cv:.2f}): "
            "exponential smoothing tracks level shifts without over-fitting noise."
        )
        return selection

    if seasonal_ready:
        selection.model = ForecastModel.SARIMA.value
        selection.reason = (
            f"Seasonal structure detected (ACF at lag {period} = {seasonality:.2f}) "
            "despite a non-trend intent."
        )
        return selection

    if r2 >= STRONG_TREND_R2:
        selection.model = ForecastModel.LINEAR_REGRESSION.value
        selection.reason = f"Clear linear structure (R² = {r2:.2f}) with no seasonality."
        return selection

    selection.model = ForecastModel.EXPONENTIAL_SMOOTHING.value
    selection.reason = (
        f"No dominant trend (R² = {r2:.2f}) or seasonality (ACF = {seasonality:.2f}); "
        "Holt exponential smoothing is the robust default."
    )
    return selection


def select_model(analysis, readiness: ReadinessReport, values: list,
                 guard: bool = True) -> ModelSelection:
    """
    Stage 3. Dual-signal rule selection, then a benchmark guard.

    The rules (`_rule_selection`) pick a model from query intent plus
    statistical signals. The guard then asks whether that choice actually
    beats the naive benchmarks on this series' own history (one-step-ahead,
    same origins as Gate 3). If it does not, the better benchmark is used
    instead and the reason says so. A rule that sounds right but loses to
    "next month equals this month" should not be shown to a user.

    SARIMA is exempt: an in-history check would need one SARIMA refit per
    origin (~0.3 s each) on every request, and SARIMA is only chosen after an
    explicit seasonal-autocorrelation test. The benchmark reports how the
    guarded and unguarded selectors compare, including this exemption.
    """
    selection = _rule_selection(analysis, readiness, values)
    if not guard or not readiness.is_ready:
        return selection
    chosen = selection.model
    if chosen in (ForecastModel.NONE.value, ForecastModel.SARIMA.value)             or len(values) < MIN_POINTS_SIGNAL_TEST:
        return selection

    period = selection.seasonal_period
    baselines = [ForecastModel.NAIVE.value]
    if period > 1 and len(values) > period + 2:
        baselines.append(ForecastModel.SEASONAL_NAIVE.value)
    errors = in_history_errors(values, [chosen] + baselines, SIGNAL_TEST_ORIGINS, period)
    if chosen not in errors:
        return selection
    best_baseline = min((b for b in baselines if b in errors), key=lambda b: errors[b][0])
    chosen_mae, base_mae = errors[chosen][0], errors[best_baseline][0]
    selection.signals["guard"] = {
        "rule_choice": chosen,
        "rule_choice_mae": round(chosen_mae, 4),
        "best_baseline": best_baseline,
        "best_baseline_mae": round(base_mae, 4),
        "origins": errors[chosen][1],
    }
    if chosen_mae > base_mae:
        selection.model = best_baseline
        selection.reason = (
            f"{selection.reason} However, on this series' own history it did not beat "
            f"the {best_baseline.replace('_', ' ').lower()} benchmark (one-step MAE "
            f"{chosen_mae:,.2f} vs {base_mae:,.2f}), so the benchmark is used instead."
        )
        selection.signals["guard"]["overridden"] = True
    else:
        selection.signals["guard"]["overridden"] = False
    return selection


# ==========================================================================
# Stage 4 - Confidence-Bounded Forecast Generation
# ==========================================================================

# Two-sided normal critical values. A t-distribution would be marginally more
# honest at n<30; the residual bootstrap widening below more than compensates.
_Z = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


@dataclass
class ForecastPoint:
    period_index: int = 0
    timestamp: str = ""
    label: str = ""
    predicted: float = 0.0
    lower_bound: float = 0.0
    upper_bound: float = 0.0
    interval_width: float = 0.0


@dataclass
class ForecastResult:
    generated: bool = False
    model: str = ForecastModel.NONE.value
    model_reason: str = ""
    value_column: str = ""
    time_column: str = ""
    granularity: str = Granularity.NONE.value
    horizon: int = 0
    confidence_level: float = 0.95
    points: list = field(default_factory=list)      # list[ForecastPoint]
    in_sample_rmse: float = 0.0
    in_sample_mae: float = 0.0
    in_sample_mape: float = 0.0
    residual_std: float = 0.0
    historical_dates: list = field(default_factory=list)
    historical_values: list = field(default_factory=list)
    fitted_values: list = field(default_factory=list)
    skipped_reason: str = ""
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["points"] = [asdict(p) if not isinstance(p, dict) else p for p in self.points]
        return d


def _period_delta(granularity: str, steps: int):
    """Advance a timestamp by `steps` periods of the given granularity."""
    g = Granularity(granularity) if granularity else Granularity.NONE
    if g is Granularity.HOUR:
        return timedelta(hours=steps)
    if g is Granularity.DAY:
        return timedelta(days=steps)
    if g is Granularity.WEEK:
        return timedelta(weeks=steps)
    if g is Granularity.MONTH:
        return timedelta(days=30 * steps)
    if g is Granularity.QUARTER:
        return timedelta(days=91 * steps)
    if g is Granularity.YEAR:
        return timedelta(days=365 * steps)
    return timedelta(days=steps)


def _add_months(base: datetime, months: int) -> datetime:
    """Calendar-correct month arithmetic, clamping the day to month length."""
    total = base.month - 1 + months
    year = base.year + total // 12
    month = total % 12 + 1
    day = min(base.day, [31, 29 if year % 4 == 0 and (year % 100 or year % 400 == 0)
                         else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return datetime(year, month, day)


def _next_timestamp(last: datetime, granularity: str, steps: int) -> datetime:
    g = Granularity(granularity) if granularity else Granularity.NONE
    if g is Granularity.MONTH:
        return _add_months(last, steps)
    if g is Granularity.QUARTER:
        return _add_months(last, 3 * steps)
    if g is Granularity.YEAR:
        return _add_months(last, 12 * steps)
    return last + _period_delta(granularity, steps)


_LABEL_FORMAT = {
    Granularity.HOUR: "%Y-%m-%d %H:00",
    Granularity.DAY: "%Y-%m-%d",
    Granularity.WEEK: "%Y-W%V",
    Granularity.MONTH: "%b %Y",
    Granularity.QUARTER: "%b %Y",
    Granularity.YEAR: "%Y",
    Granularity.NONE: "%Y-%m-%d",
}


def _format_label(ts: datetime, granularity: str) -> str:
    g = Granularity(granularity) if granularity else Granularity.NONE
    if g is Granularity.QUARTER:
        return f"{ts.year}-Q{(ts.month - 1) // 3 + 1}"
    return ts.strftime(_LABEL_FORMAT.get(g, "%Y-%m-%d"))


# --- estimators -----------------------------------------------------------


def _fit_linear(values: list, horizon: int) -> tuple:
    """Returns (fitted_in_sample, forecasts)."""
    slope, intercept, _ = _linear_fit(values)
    n = len(values)
    fitted = [intercept + slope * i for i in range(n)]
    forecasts = [intercept + slope * (n + h) for h in range(horizon)]
    return fitted, forecasts


HOLT_DAMPING = 0.9


def _fit_holt(values: list, horizon: int, alpha: float = 0.5, beta: float = 0.3,
              phi: float = HOLT_DAMPING) -> tuple:
    """
    Damped-trend Holt exponential smoothing (Gardner & McKenzie 1985).

    alpha/beta are fixed rather than optimised: with 12-36 observations, MLE
    over the smoothing constants over-fits. The trend is damped by phi each
    period, so a slope estimated from a short noisy history flattens out
    instead of being extrapolated indefinitely. With phi = 1 this is the
    classic undamped Holt, which the Stage 2 benchmark found to be the least
    accurate model on short business-like series (it projects noise as trend).
    """
    if not values:
        return [], []
    level = values[0]
    trend = values[1] - values[0] if len(values) > 1 else 0.0
    fitted = [level]
    for v in values[1:]:
        prev_level = level
        forecast = level + phi * trend
        fitted.append(forecast)
        level = alpha * v + (1 - alpha) * forecast
        trend = beta * (level - prev_level) + (1 - beta) * phi * trend
    forecasts = []
    damped = 0.0
    for h in range(horizon):
        damped += phi ** (h + 1)
        forecasts.append(level + damped * trend)
    return fitted, forecasts


def _fit_wma(values: list, horizon: int, window: int = 3) -> tuple:
    """
    Weighted moving average with linearly increasing recency weights.

    Forecasts are produced recursively, so the projection decays toward the
    recent level - the correct conservative behaviour for very short series.
    """
    w = min(window, len(values))
    weights = list(range(1, w + 1))

    fitted = []
    for i in range(len(values)):
        if i == 0:
            fitted.append(values[0])
            continue
        span = values[max(0, i - w) : i]
        ws = weights[-len(span):]
        fitted.append(sum(v * k for v, k in zip(span, ws)) / sum(ws))

    working = list(values)
    forecasts = []
    for _ in range(horizon):
        span = working[-w:]
        ws = weights[-len(span):]
        nxt = sum(v * k for v, k in zip(span, ws)) / sum(ws)
        forecasts.append(nxt)
        working.append(nxt)
    return fitted, forecasts


def _fit_naive(values: list, horizon: int) -> tuple:
    """
    Random-walk benchmark: every future value equals the last observation.

    The in-sample fit is the one-step version (y_hat[t] = y[t-1]), so its
    residuals are exactly the period-to-period changes - the quantity the
    interval construction then scales by sqrt(h), which is the textbook
    random-walk interval.
    """
    if not values:
        return [], []
    fitted = [values[0]] + list(values[:-1])
    return fitted, [values[-1]] * horizon


def _fit_seasonal_naive(values: list, horizon: int, period: int) -> tuple:
    """
    Seasonal benchmark: each future value equals the same period one cycle ago.

    The first `period` observations have no in-sample counterpart; they are
    fitted with their own value (zero residual) and excluded from the residual
    spread by `project_series`, which skips the first `period` residuals for
    this model.
    """
    n = len(values)
    if period <= 1 or n <= period:
        return _fit_naive(values, horizon)
    fitted = [values[i] if i < period else values[i - period] for i in range(n)]
    forecasts = [values[n - period + (h % period)] for h in range(horizon)]
    return fitted, forecasts


# Controlled order selection (proposal 3.6 step 2). Candidates were compared
# by rolling-origin backtest on the DEVELOPMENT data (synthetic + M4 seed 2026),
# never on the held-out M4 test sample:
#   (0,1,1)(0,1,1)  "airline" (Box & Jenkins [11])   mean MASE 1.69
#   per-series AICc choice among three candidates     mean MASE 2.03
#   (1,1,1)(1,1,1)  the Stage 1 order                  mean MASE 7.04 (12 blow-ups)
# Two parameters instead of four is what a 24-36 point history can support.
SARIMA_ORDER = (0, 1, 1)
SARIMA_SEASONAL_ORDER = (0, 1, 1)


def _fit_sarima(values: list, horizon: int, period: int, confidence: float) -> tuple:
    """
    Seasonal ARIMA with the airline order SARIMA_ORDER x SARIMA_SEASONAL_ORDER.

    Returns (fitted, forecasts, lower, upper) or None if the fit fails - the
    caller then falls back to exponential smoothing rather than erroring out.
    `lower`/`upper` are returned as None: statsmodels' own intervals treat the
    estimated parameters as exact and covered only ~75% of outcomes for a
    nominal 95% on the development data, so `project_series` builds SARIMA's
    band from its residuals like every other model's (~92%).
    """
    if not _HAS_STATSMODELS:
        return None
    try:
        model = SARIMAX(
            values,
            order=SARIMA_ORDER,
            seasonal_order=SARIMA_SEASONAL_ORDER + (period,),
            enforce_stationarity=False,
            enforce_invertibility=False,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")   # convergence chatter on short series
            fit = model.fit(disp=False)
        fitted = [float(v) for v in fit.fittedvalues]
        mean = [float(v) for v in fit.get_forecast(steps=horizon).predicted_mean]
        return fitted, mean, None, None
    except Exception as exc:  # noqa: BLE001
        log_step(f"SARIMA fit failed ({exc}); falling back.", level="WARN")
        return None


def _accuracy(actual: list, fitted: list) -> tuple:
    """In-sample RMSE, MAE, MAPE over the overlapping span."""
    pairs = [(a, f) for a, f in zip(actual, fitted)]
    if not pairs:
        return 0.0, 0.0, 0.0
    n = len(pairs)
    rmse = math.sqrt(sum((a - f) ** 2 for a, f in pairs) / n)
    mae = sum(abs(a - f) for a, f in pairs) / n
    nonzero = [(a, f) for a, f in pairs if a != 0]
    mape = (
        100.0 * sum(abs((a - f) / a) for a, f in nonzero) / len(nonzero)
        if nonzero
        else 0.0
    )
    return rmse, mae, mape


def project_series(
    values: list,
    model: str,
    horizon: int,
    confidence: float = 0.95,
    seasonal_period: int = 12,
) -> dict:
    """
    Fit one model to a bare series and project it with confidence bounds.

    This is the single forecasting code path: `generate_forecast` uses it for
    live requests and the benchmark harness uses it for backtests, so the
    evaluation measures exactly what users receive.

    Interval construction (every model, SARIMA included): the half-width at
    step h is

        z * residual_std * widening(h) * small_sample_penalty

    widening(h) is sqrt(h) - accumulating uncertainty in a random-walk sense,
    so bounds genuinely widen with distance - except for the seasonal naive,
    whose error only accumulates once per full cycle (sqrt(floor((h-1)/m)+1)).
    The penalty inflates intervals on short series, the adaptation claimed for
    small multi-tenant datasets.

    Returns a dict with: model (as actually used, after any SARIMA fallback),
    fallback_note, fitted, forecasts, lower, upper, residual_std, rmse, mae,
    mape, interval_source, small_sample_penalty, z.
    """
    m = ForecastModel(model)
    n = len(values)
    used = m
    fallback_note = ""
    lower_direct = upper_direct = None
    skip_residuals = 0

    if m is ForecastModel.SARIMA:
        # Seasonal differencing needs two full cycles to be identifiable at
        # all; below that statsmodels returns numerically explosive forecasts.
        sarima = (_fit_sarima(values, horizon, seasonal_period, confidence)
                  if n >= 2 * seasonal_period else None)
        if sarima:
            fitted, forecasts, lower_direct, upper_direct = sarima
            # The first cycle + 1 fitted values are start-up artefacts of the
            # double differencing, not forecasts; they would inflate the band.
            skip_residuals = seasonal_period + 1
        elif n < 2 * seasonal_period:
            used = ForecastModel.EXPONENTIAL_SMOOTHING
            fallback_note = (f" [SARIMA needs {2 * seasonal_period} points, only {n}; "
                             "fell back to exponential smoothing]")
            fitted, forecasts = _fit_holt(values, horizon)
        else:
            used = ForecastModel.EXPONENTIAL_SMOOTHING
            fallback_note = " [SARIMA fit failed; fell back to exponential smoothing]"
            fitted, forecasts = _fit_holt(values, horizon)
    elif m is ForecastModel.LINEAR_REGRESSION:
        fitted, forecasts = _fit_linear(values, horizon)
    elif m is ForecastModel.WEIGHTED_MOVING_AVERAGE:
        fitted, forecasts = _fit_wma(values, horizon)
    elif m is ForecastModel.NAIVE:
        fitted, forecasts = _fit_naive(values, horizon)
        skip_residuals = 1      # y_hat[0] = y[0] is not a forecast
    elif m is ForecastModel.SEASONAL_NAIVE:
        fitted, forecasts = _fit_seasonal_naive(values, horizon, seasonal_period)
        skip_residuals = seasonal_period if n > seasonal_period else 1
    else:
        fitted, forecasts = _fit_holt(values, horizon)

    span = min(len(fitted), n)
    rmse, mae, mape = _accuracy(values[skip_residuals:span], fitted[skip_residuals:span])
    residuals = [a - f for a, f in zip(values[skip_residuals:span], fitted[skip_residuals:span])]
    resid_std = (
        math.sqrt(sum(r ** 2 for r in residuals) / max(1, len(residuals) - 1))
        if len(residuals) > 1
        else 0.0
    )

    z = _Z.get(round(confidence, 2), 1.96)
    # Inflate intervals on short series: +50% at n=6, negligible past n=30.
    small_sample_penalty = 1.0 + (3.0 / max(n, 4))
    seasonal_widening = used is ForecastModel.SEASONAL_NAIVE and n > seasonal_period

    lower, upper = [], []
    for h, value in enumerate(forecasts):
        if lower_direct is not None and h < len(lower_direct):
            # statsmodels' intervals assume the fitted parameters are exact; on
            # 24-36 points they are not, and the benchmark measured ~60% coverage
            # for a nominal 95%. The same short-series penalty as the other
            # models is applied around the model's own interval.
            centre_half = (upper_direct[h] - lower_direct[h]) / 2.0
            lo = value - centre_half * small_sample_penalty
            hi = value + centre_half * small_sample_penalty
        else:
            steps = (h // seasonal_period + 1) if seasonal_widening else (h + 1)
            half = z * resid_std * math.sqrt(steps) * small_sample_penalty
            # Guarantee a non-degenerate band even on a perfect in-sample fit.
            half = max(half, abs(value) * 0.02 * math.sqrt(h + 1))
            lo, hi = value - half, value + half
        lower.append(float(lo))
        upper.append(float(hi))

    return {
        "model": used.value,
        "fallback_note": fallback_note,
        "fitted": [float(f) for f in fitted[:span]],
        "forecasts": [float(f) for f in forecasts],
        "lower": lower,
        "upper": upper,
        "residual_std": resid_std,
        "rmse": rmse,
        "mae": mae,
        "mape": mape,
        "interval_source": "model" if lower_direct is not None else "residual_bootstrap",
        "small_sample_penalty": small_sample_penalty,
        "z": z,
    }


def generate_forecast(
    analysis,
    profile,
    rows: list,
    readiness: ReadinessReport,
    selection: ModelSelection,
    horizon: int = None,
    confidence: float = 0.95,
    value_column: str = None,
) -> ForecastResult:
    """
    Stage 4. Produce forward projections with progressively widening bounds.

    The fitting and interval construction live in `project_series` (shared
    with the benchmark); this function adds the time axis, labels and the
    envelope fields around it.
    """
    result = ForecastResult(confidence_level=confidence)

    if not readiness.is_ready:
        result.skipped_reason = readiness.reason
        result.model = ForecastModel.NONE.value
        return result

    value_column = value_column or (
        profile.measure_columns[0] if profile.measure_columns else None
    )
    time_column = profile.temporal_column
    prepared = prepare_series(rows, time_column, value_column, readiness.granularity)
    dates, values = prepared["dates"], prepared["values"]
    if prepared["filled_indices"]:
        result.diagnostics["interpolated_periods"] = prepared["filled_indices"]

    if horizon is None:
        horizon = analysis.horizon.value or 3
    horizon = max(1, min(int(horizon), 24))

    # Never project further than half the observed span: extrapolating 12
    # periods from 8 observations is not a forecast, it is a guess.
    max_horizon = max(1, len(values) // 2)
    if horizon > max_horizon:
        result.diagnostics["horizon_clamped_from"] = horizon
        horizon = max_horizon

    result.value_column = value_column
    result.time_column = time_column
    result.granularity = readiness.granularity
    result.horizon = horizon
    result.model = selection.model
    result.model_reason = selection.reason
    result.historical_dates = [d.isoformat() for d in dates]
    result.historical_values = values

    projection = project_series(values, selection.model, horizon, confidence,
                                selection.seasonal_period)
    result.model = projection["model"]
    result.model_reason += projection["fallback_note"]
    n = len(values)
    rmse, mape = projection["rmse"], projection["mape"]
    result.fitted_values = [round(f, 4) for f in projection["fitted"]]
    result.in_sample_rmse = round(rmse, 4)
    result.in_sample_mae = round(projection["mae"], 4)
    result.in_sample_mape = round(mape, 4)
    result.residual_std = round(projection["residual_std"], 4)
    small_sample_penalty, z = projection["small_sample_penalty"], projection["z"]

    last_date = dates[-1] if dates else datetime.now()

    for h, (value, lo, hi) in enumerate(
        zip(projection["forecasts"], projection["lower"], projection["upper"])
    ):
        ts = _next_timestamp(last_date, result.granularity, h + 1)
        result.points.append(
            ForecastPoint(
                period_index=h + 1,
                timestamp=ts.isoformat(),
                label=_format_label(ts, result.granularity),
                predicted=round(float(value), 4),
                lower_bound=round(float(lo), 4),
                upper_bound=round(float(hi), 4),
                interval_width=round(float(hi - lo), 4),
            )
        )

    result.generated = True
    result.diagnostics.update(
        {
            "n_observations": n,
            "small_sample_penalty": round(small_sample_penalty, 4),
            "z_score": z,
            "interval_source": projection["interval_source"],
            "seasonal_period": selection.seasonal_period,
        }
    )
    log_step(
        f"Forecast generated: {result.model} x{horizon} on '{value_column}' "
        f"(RMSE {rmse:.2f}, MAPE {mape:.1f}%)"
    )
    return result


def backtest(values: list, model: str, holdout: int = 3, seasonal_period: int = 12) -> dict:
    """
    Hold-out backtest used by evaluate.py to report OUT-OF-SAMPLE accuracy.

    In-sample RMSE flatters every model; the research metrics must come from
    data the model never saw, so the last `holdout` points are withheld.
    """
    if len(values) <= holdout + 3:
        return {"ok": False, "reason": "series too short to backtest"}

    train, test = values[:-holdout], values[-holdout:]
    forecasts = project_series(train, model, holdout, 0.95, seasonal_period)["forecasts"]

    rmse, mae, mape = _accuracy(test, forecasts)
    return {
        "ok": True,
        "model": model,
        "holdout": holdout,
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "mape": round(mape, 4),
        "actual": test,
        "predicted": [round(f, 4) for f in forecasts],
    }
