"""
Prediction Stage 1 execution - the strategy-specific predictions.

Stage 1 (`prediction.map_intent_to_strategy`) decides WHAT KIND of predictive
question an intent implies. This module answers each kind:

  TEMPORAL_FORECAST    extend the series (Stage 4 does this for one series;
                       for a GROUPED result each category is extended here)
  CATEGORY_TRAJECTORY  forecast every category and project which one leads
                       next period, and whether the ranking changes
  DISTRIBUTION_SHIFT   project how the distribution moves: category SHARES
                       for a grouped result, per-period QUARTILES for raw
                       rows, the forecast's position in the historical
                       distribution for a single series
  ANOMALY_PERSISTENCE  for a recent anomaly, does the forecast stay beyond the
                       adaptive threshold (persisting / worsening) or return
                       inside it (recovering)

Each strategy runs only on result layouts where its question is meaningful
(result_profiler.infer_layout) and otherwise returns a specific reason. All
forecasts come from prediction.project_series with the guarded selector, so
they inherit the same benchmark-validated behaviour as Stage 4.
"""

from dataclasses import asdict, dataclass, field
from types import SimpleNamespace

import anomaly as anomaly_mod
import prediction
from result_profiler import extract_grouped_series, parse_date, parse_number
from schemas import Granularity, PredictionStrategy, SEASONAL_PERIOD

MAX_CATEGORIES = 12
OTHER_LABEL = "Other"
RECENT_WINDOW = 3            # an anomaly in the last N periods counts as "recent"
MIN_DISTRIBUTION_PERIODS = 6


@dataclass
class StrategyResult:
    requested: str = PredictionStrategy.NONE.value
    executed_as: str = ""
    executed: bool = False
    skipped_reason: str = ""
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ==========================================================================
# Shared: forecast one bare series the way Stage 3/4 would
# ==========================================================================


def _period(profile) -> int:
    try:
        return SEASONAL_PERIOD.get(Granularity(profile.granularity), 1)
    except ValueError:
        return 1


def forecast_values(values: list, dates: list, profile, analysis, horizon: int,
                    confidence: float) -> dict:
    """Guarded model selection + projection for one series; None if too short."""
    if len(values) < prediction.MIN_POINTS_ANY:
        return None
    period = _period(profile)
    readiness = prediction.ReadinessReport(is_ready=True, granularity=profile.granularity,
                                           n_points=len(values))
    intent = SimpleNamespace(primary_intent=getattr(analysis, "primary_intent", "TREND_ANALYSIS"))
    selection = prediction.select_model(intent, readiness, values)
    h = max(1, min(horizon, len(values) // 2))
    proj = prediction.project_series(values, selection.model, h, confidence, period)
    test = prediction.forecastability(values, period)
    points = []
    for i, (p, lo, hi) in enumerate(zip(proj["forecasts"], proj["lower"], proj["upper"])):
        ts = prediction._next_timestamp(dates[-1], profile.granularity, i + 1) if dates else None
        points.append({
            "period_index": i + 1,
            "label": prediction._format_label(ts, profile.granularity) if ts else f"t+{i + 1}",
            "timestamp": ts.isoformat() if ts else "",
            "predicted": round(p, 4), "lower": round(lo, 4), "upper": round(hi, 4),
        })
    return {
        "model": proj["model"],
        "points": points,
        "low_signal": bool(test.get("assessed")
                           and test["expected_relative_error"]
                           > prediction.max_expected_error(profile.granularity)),
        "n": len(values),
    }


# ==========================================================================
# CATEGORY_TRAJECTORY
# ==========================================================================


def category_trajectory(profile, rows, analysis, horizon=3, confidence=0.95) -> StrategyResult:
    result = StrategyResult(requested=PredictionStrategy.CATEGORY_TRAJECTORY.value,
                            executed_as=PredictionStrategy.CATEGORY_TRAJECTORY.value)
    measure = profile.measure_columns[0] if profile.measure_columns else ""
    if profile.layout == "CROSS_SECTIONAL":
        dim = profile.dimension_columns[0] if profile.dimension_columns else "category"
        result.skipped_reason = (
            f"Which {dim} will lead next period can only be projected from values over "
            f"time, and this result has a single value per {dim}. Ask for the figures "
            f"by month and {dim} to get a projection."
        )
        return result
    if profile.layout != "GROUPED" or not measure:
        result.skipped_reason = "The result does not contain one series per category."
        return result

    series = extract_grouped_series(rows, profile.temporal_column, profile.group_column, measure)
    # Keep the largest categories by their latest value; a ranking over dozens
    # of categories is not readable and most will be too short anyway.
    ranked = sorted(series.items(), key=lambda kv: -(kv[1][1][-1] if kv[1][1] else 0))
    categories, skipped = [], []
    for name, (dates, values) in ranked[:MAX_CATEGORIES]:
        fc = forecast_values(values, dates, profile, analysis, horizon, confidence)
        if fc is None:
            skipped.append(name)
            continue
        categories.append({"category": name, "last_label": prediction._format_label(
            dates[-1], profile.granularity), "last_actual": round(values[-1], 4), **fc})
    # The rest are summed into one "Other" series instead of being dropped:
    # shares of the total (DISTRIBUTION_SHIFT) are only right if the total is
    # (Stage 8 - before, 15 vendors gave shares of the top 12's total). "Other"
    # is never ranked or named as a leader; it is not a category.
    rest = ranked[MAX_CATEGORIES:]
    other_members = [name for name, _ in rest]
    if rest:
        by_date = {}
        for _, (dates, values) in rest:
            for d, v in zip(dates, values):
                by_date[d] = by_date.get(d, 0.0) + v
        other_dates = sorted(by_date)
        other_values = [by_date[d] for d in other_dates]
        fc = forecast_values(other_values, other_dates, profile, analysis, horizon, confidence)
        if fc is not None:
            categories.append({"category": f"{OTHER_LABEL} ({len(other_members)} more)",
                               "is_other": True,
                               "members": len(other_members),
                               "last_label": prediction._format_label(
                                   other_dates[-1], profile.granularity),
                               "last_actual": round(other_values[-1], 4), **fc})
    named = [c for c in categories if not c.get("is_other")]
    if len(named) < 2:
        result.skipped_reason = (
            f"Fewer than two {profile.group_column} values have the "
            f"{prediction.MIN_POINTS_ANY}+ periods needed to forecast and compare them."
        )
        return result

    now = sorted(named, key=lambda c: -c["last_actual"])
    nxt = sorted(named, key=lambda c: -c["points"][0]["predicted"])
    end = sorted(named, key=lambda c: -c["points"][-1]["predicted"])
    leader, runner_up = nxt[0], nxt[1]
    clear_lead = leader["points"][0]["lower"] > runner_up["points"][0]["upper"]
    rank_now = {c["category"]: i + 1 for i, c in enumerate(now)}
    rank_changes = [
        {"category": c["category"], "rank_now": rank_now[c["category"]], "rank_next": i + 1}
        for i, c in enumerate(nxt) if rank_now[c["category"]] != i + 1
    ]
    result.executed = True
    result.details = {
        "group_column": profile.group_column,
        "measure": measure,
        "categories": categories,
        "skipped_categories": skipped,
        "grouped_into_other": other_members,
        "current_leader": {"category": now[0]["category"], "value": now[0]["last_actual"],
                           "label": now[0]["last_label"]},
        "projected_leader": {"category": leader["category"],
                             "value": leader["points"][0]["predicted"],
                             "label": leader["points"][0]["label"]},
        "projected_leader_end": {"category": end[0]["category"],
                                 "value": end[0]["points"][-1]["predicted"],
                                 "label": end[0]["points"][-1]["label"]},
        "runner_up": {"category": runner_up["category"],
                      "value": runner_up["points"][0]["predicted"]},
        "leader_changes": now[0]["category"] != leader["category"],
        "clear_lead": clear_lead,
        "rank_changes": rank_changes,
        "low_signal_categories": [c["category"] for c in named if c["low_signal"]],
    }
    return result


# ==========================================================================
# DISTRIBUTION_SHIFT
# ==========================================================================


def _quantile(sorted_values: list, q: float) -> float:
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def distribution_shift(profile, rows, analysis, horizon=3, confidence=0.95,
                       forecast=None) -> StrategyResult:
    result = StrategyResult(requested=PredictionStrategy.DISTRIBUTION_SHIFT.value)
    measure = profile.measure_columns[0] if profile.measure_columns else ""

    if profile.layout == "GROUPED":
        # Shares of the total, now vs the next projected period.
        trajectory = category_trajectory(profile, rows, analysis, horizon, confidence)
        if not trajectory.executed:
            result.skipped_reason = trajectory.skipped_reason
            return result
        cats = trajectory.details["categories"]
        total_now = sum(c["last_actual"] for c in cats)
        total_next = sum(c["points"][0]["predicted"] for c in cats)
        if total_now <= 0 or total_next <= 0:
            result.skipped_reason = "Shares are undefined when the total is not positive."
            return result
        shares = []
        for c in cats:
            now = 100.0 * c["last_actual"] / total_now
            nxt = 100.0 * c["points"][0]["predicted"] / total_next
            shares.append({"category": c["category"], "share_now_pct": round(now, 2),
                           "share_next_pct": round(nxt, 2),
                           "change_pp": round(nxt - now, 2),
                           "is_other": bool(c.get("is_other"))})
        shares.sort(key=lambda s: -s["change_pp"])
        # "Other" counts towards the total but is never named as a mover.
        movers = [s for s in shares if not s["is_other"]]
        result.executed = True
        result.executed_as = "SHARE_SHIFT"
        result.details = {
            "group_column": profile.group_column, "measure": measure, "shares": shares,
            "from_label": cats[0]["last_label"], "to_label": cats[0]["points"][0]["label"],
            "largest_gain": movers[0], "largest_loss": movers[-1],
            "categories_forecast": trajectory.details["categories"],
        }
        return result

    if profile.layout == "EVENTS":
        # Raw rows: per-period quartiles, each projected one period ahead.
        by_period = {}
        for row in rows:
            d = parse_date(row.get(profile.temporal_column))
            v = parse_number(row.get(measure))
            if d is None or v is None:
                continue
            by_period.setdefault((d.year, d.month), []).append(v)
        periods = sorted(by_period)
        if len(periods) < MIN_DISTRIBUTION_PERIODS:
            result.skipped_reason = (
                f"Only {len(periods)} months of individual values; at least "
                f"{MIN_DISTRIBUTION_PERIODS} are needed to project how the distribution moves."
            )
            return result
        stats = {"p25": [], "median": [], "p75": []}
        for key in periods:
            ordered = sorted(by_period[key])
            stats["p25"].append(_quantile(ordered, 0.25))
            stats["median"].append(_quantile(ordered, 0.50))
            stats["p75"].append(_quantile(ordered, 0.75))
        dates = [parse_date(f"{y:04d}-{m:02d}-01") for y, m in periods]
        monthly = SimpleNamespace(granularity=Granularity.MONTH.value)
        projected = {}
        for name, values in stats.items():
            fc = forecast_values(values, dates, monthly, analysis, 1, confidence)
            projected[name] = fc["points"][0]["predicted"] if fc else None
        result.executed = True
        result.executed_as = "QUARTILE_SHIFT"
        result.details = {
            "measure": measure, "periods": len(periods),
            "last_label": prediction._format_label(dates[-1], Granularity.MONTH.value),
            "next_label": prediction._format_label(
                prediction._next_timestamp(dates[-1], Granularity.MONTH.value, 1),
                Granularity.MONTH.value),
            "last": {k: round(v[-1], 4) for k, v in stats.items()},
            "projected": {k: round(v, 4) for k, v in projected.items() if v is not None},
        }
        return result

    if profile.layout == "SINGLE" and forecast is not None and forecast.generated:
        # One series: where do the projected values sit in the historical spread?
        history = sorted(forecast.historical_values)
        positions = []
        for p in forecast.points:
            below = sum(1 for v in history if v < p.predicted)
            positions.append({"label": p.label, "predicted": p.predicted,
                              "percentile": round(100.0 * below / len(history), 1)})
        result.executed = True
        result.executed_as = "PERCENTILE_POSITION"
        result.details = {
            "measure": forecast.value_column, "positions": positions,
            "historical_median": round(_quantile(history, 0.5), 4),
        }
        return result

    result.skipped_reason = (
        "How the distribution will shift can only be projected from values over time; "
        "this result has no time axis." if profile.layout == "CROSS_SECTIONAL"
        else "No forecast was available to compare against the historical distribution."
    )
    return result


# ==========================================================================
# ANOMALY_PERSISTENCE
# ==========================================================================


def anomaly_persistence(forecast, anomaly_report) -> StrategyResult:
    result = StrategyResult(requested=PredictionStrategy.ANOMALY_PERSISTENCE.value,
                            executed_as=PredictionStrategy.ANOMALY_PERSISTENCE.value)
    if forecast is None or not forecast.generated:
        result.skipped_reason = (getattr(forecast, "skipped_reason", "")
                                 or "No forecast was available to test persistence against.")
        return result
    if anomaly_report is None or not anomaly_report.evaluated:
        result.skipped_reason = (getattr(anomaly_report, "skipped_reason", "")
                                 or "Anomaly thresholds could not be computed.")
        return result

    n = len(forecast.historical_values)
    recent = [a for a in anomaly_report.historical_anomalies if a.index >= n - RECENT_WINDOW]
    result.executed = True
    if not recent:
        latest = anomaly_report.historical_anomalies[-1] if anomaly_report.historical_anomalies else None
        result.details = {
            "verdict": "NO_RECENT_ANOMALY",
            "recent_window": RECENT_WINDOW,
            "latest_anomaly": {"label": latest.label, "value": latest.value,
                               "direction": latest.direction} if latest else None,
        }
        return result

    anomaly = recent[-1]
    pattern = anomaly.pattern or "UNCONFIRMED"
    horizon = len(forecast.points)
    run = _run_length(anomaly_report.historical_anomalies, anomaly)
    basis = "FORECAST"
    warnings = anomaly_report.predictive_warnings
    if pattern == "SPIKE":
        # Isolated and already followed by an in-range observation: the data
        # itself shows the return, no projection needed.
        warnings, basis = [], "OBSERVED_RETURN"
    elif pattern == "UNCONFIRMED":
        # One observation cannot show whether it is a spike or the start of a
        # shift. Letting it drive the projection is what made a naive model
        # carry every last-period spike forward (Stage 2: 59.8 % on spikes).
        # Project from the history before it instead, and screen that.
        alt = _forecast_without_latest(forecast)
        if alt is not None:
            rescreen = anomaly_mod.detect_anomalies(
                forecast.historical_values, forecast=alt,
                period=_granularity_period(forecast.granularity))
            if rescreen.evaluated:
                warnings, basis = rescreen.predictive_warnings, "FORECAST_WITHOUT_LATEST_POINT"
    same_side = [w for w in warnings if w.direction == anomaly.direction]
    if not same_side:
        verdict = "RECOVERING"
    else:
        # Distance beyond the band, in the detection space, for each warned point.
        distances = [w.iqr_distance for w in sorted(same_side, key=lambda w: w.index)]
        worsening = (len(same_side) == horizon and len(distances) > 1
                     and all(b > a for a, b in zip(distances, distances[1:])))
        verdict = "WORSENING" if worsening else "PERSISTING"
    result.details = {
        "verdict": verdict,
        "anomaly": {"label": anomaly.label, "value": anomaly.value,
                    "direction": anomaly.direction, "severity": anomaly.severity},
        "pattern": pattern,
        "run_length": run,
        "basis": basis,
        "projected_breaches": len(same_side),
        "horizon": horizon,
        "breach_labels": [w.label for w in sorted(same_side, key=lambda w: w.index)],
        "model": forecast.model,
        "note": {
            "OBSERVED_RETURN": "The anomaly was a one-off: the following observation "
                               "was already back inside the threshold.",
            "FORECAST_WITHOUT_LATEST_POINT": "A single latest anomaly cannot yet be told "
                                             "apart from the start of a level shift; the "
                                             "projection is made without it, so a shift "
                                             "that has only just begun is not yet visible.",
            "FORECAST": "The anomaly has lasted several consecutive periods (a level "
                        "shift); the verdict reflects the selected model's projection.",
        }[basis],
    }
    return result


def _run_length(anomalies: list, anomaly) -> int:
    """Consecutive same-direction anomalies ending at `anomaly`."""
    flagged = {a.index for a in anomalies if a.direction == anomaly.direction}
    run, i = 0, anomaly.index
    while i in flagged:
        run, i = run + 1, i - 1
    return run


def _granularity_period(granularity) -> int:
    try:
        return SEASONAL_PERIOD.get(Granularity(granularity), 1)
    except ValueError:
        return 1


def _forecast_without_latest(forecast):
    """The same model's forecast for the same periods, fitted without the last point."""
    history = list(forecast.historical_values)[:-1]
    horizon = len(forecast.points)
    period = _granularity_period(forecast.granularity)
    if len(history) < 3 or not horizon:
        return None
    try:
        proj = prediction.project_series(history, forecast.model, horizon + 1,
                                         forecast.confidence_level, period if period > 1 else 12)
    except (ValueError, ArithmeticError, IndexError):
        return None
    # Step 1 of this projection is the period that holds the anomaly; steps
    # 2..h+1 are the periods the original forecast covers.
    return prediction.ForecastResult(
        generated=True, model=proj["model"], granularity=forecast.granularity,
        historical_values=list(forecast.historical_values),
        points=[prediction.ForecastPoint(period_index=p.period_index, label=p.label,
                                         predicted=v, lower_bound=lo, upper_bound=hi)
                for p, v, lo, hi in zip(forecast.points, proj["forecasts"][1:],
                                        proj["lower"][1:], proj["upper"][1:])])


# ==========================================================================
# Dispatcher
# ==========================================================================


def execute(strategy: str, analysis, profile, rows, forecast=None, anomaly_report=None,
            horizon=3, confidence=0.95) -> StrategyResult:
    """Run the strategy Stage 1 selected; NONE returns an empty, unexecuted result."""
    if strategy == PredictionStrategy.CATEGORY_TRAJECTORY.value:
        return category_trajectory(profile, rows, analysis, horizon, confidence)
    if strategy == PredictionStrategy.DISTRIBUTION_SHIFT.value:
        return distribution_shift(profile, rows, analysis, horizon, confidence, forecast)
    if strategy == PredictionStrategy.ANOMALY_PERSISTENCE.value:
        return anomaly_persistence(forecast, anomaly_report)
    if strategy == PredictionStrategy.TEMPORAL_FORECAST.value and profile.layout == "GROUPED":
        # A trend over several series: extend each one rather than the mixture.
        trajectory = category_trajectory(profile, rows, analysis, horizon, confidence)
        trajectory.requested = strategy
        return trajectory
    return StrategyResult(requested=strategy, executed_as=strategy,
                          executed=strategy == PredictionStrategy.TEMPORAL_FORECAST.value
                          and forecast is not None and forecast.generated)
