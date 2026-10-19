"""
Forecast and anomaly chart: the presentation layer's line (or bar) chart,
extended with the stage-8 Predictive Visualization Grammar Extension
(visualization.extend_with_forecast):

  R1 forecast mean    dashed continuation of the history
  R2 confidence band  shaded area between the lower and upper bounds
  R3 anomaly markers  points at historical anomalies and predicted breaches
  R5 per-category forecasts, coloured like their series

What-if (R4) is not used.
"""

from typing import Optional, Tuple

import visualization
from data_presentation import charts as base_charts

PERIOD_WORDS = {"HOUR": "hour", "DAY": "day", "WEEK": "week", "MONTH": "month",
                "QUARTER": "quarter", "YEAR": "year"}


def _with_meta(spec: dict, chart_type: str, x: str, y: str, color: str = "") -> dict:
    spec["_meta"] = {"chart_type": chart_type, "x_field": x, "y_field": y,
                     "color_field": color, "forecast_layered": False}
    return spec


def _base_chart(rows, profile) -> Tuple[Optional[dict], str]:
    """Line over time when there is a time axis, else bars over categories."""
    measure = base_charts.measure_column(profile)
    if profile.temporal_column:
        spec, reason, _ = base_charts.line_spec(rows, profile)
        if spec:
            color = spec["encoding"].get("color", {}).get("field", "")
            return _with_meta(spec, "line", profile.temporal_column, measure, color), ""
        return None, reason
    spec, reason, _ = base_charts.bar_spec(rows, profile)
    if spec:
        color = spec["encoding"].get("color", {}).get("field", "")
        return _with_meta(spec, "bar", spec["encoding"]["x"]["field"], measure, color), ""
    return None, reason


def build_prediction_chart(rows, profile, forecast, anomaly_report, strategy_result) -> Tuple[Optional[dict], str]:
    """Return (layered Vega-Lite spec, "") or (None, why there is no chart)."""
    has_forecast = forecast is not None and forecast.generated
    has_anomalies = anomaly_report is not None and anomaly_report.evaluated
    has_strategy = strategy_result is not None and strategy_result.executed
    if not (has_forecast or has_anomalies or has_strategy):
        return None, "There is no forecast or anomaly to draw."

    spec, reason = _base_chart(rows, profile)
    if spec is None:
        return None, reason

    measure = visualization._humanize(spec["_meta"]["y_field"])
    if has_forecast:
        unit = PERIOD_WORDS.get(forecast.granularity, "period")
        spec["title"] = f"{measure}: history and {forecast.horizon}-{unit} forecast"
    elif has_anomalies:
        spec["title"] = f"{measure}: anomalies"
    else:
        spec["title"] = f"{measure}: projection"

    layered = visualization.extend_with_forecast(
        spec,
        forecast=forecast if has_forecast else None,
        anomaly_report=anomaly_report if has_anomalies else None,
        scenario=None,
        strategy_result=strategy_result,
    )
    if not layered.get("_meta", {}).get("forecast_layered") and "layer" not in layered:
        return None, layered.get("_meta", {}).get("extension_skipped_reason", "The prediction could not be drawn.")
    return layered, ""
