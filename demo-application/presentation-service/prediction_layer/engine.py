"""
Prediction layer: confidence-bounded temporal forecasts with grounded,
verified summaries, driven by the intent classification.

Runs the stage-2..8 prediction stages over one executed, PII-masked result:

  Stage 1  intent -> predictive strategy     prediction.map_intent_to_strategy
  Stage 2  data readiness classifier          prediction.assess_readiness
  Stage 3  model selection + benchmark guard  prediction.select_model
  Stage 4  confidence-bounded forecast        prediction.generate_forecast
  Stage 1b strategy execution                 strategies.execute
  Stage 5  dual-dimension anomaly detection   anomaly.detect_anomalies (IQR + Z-score)
  Stage 7  unified verified summary           summarization.summarize

Stage 6 (what-if simulation) is deliberately not run.

Modes:
  FORECAST      the classifier set prediction_needed
  ANOMALY_ONLY  intent ANOMALY_DETECTION without a forecast request: anomalies
                on the history, no forecast
"""

from typing import Optional

import anomaly as anomaly_mod
import input_adapter
import prediction as prediction_mod
import strategies
import summarization
from data_presentation.views import llm_summary_enabled
from profiler import log_step
from result_profiler import coerce_measures, extract_ordinal_series, profile_results
from schemas import PredictionStrategy, ReadinessVerdict

from .analysis import build_analysis
from .charts import build_prediction_chart

ANOMALY_INTENT = "ANOMALY_DETECTION"


def prediction_mode(intent: Optional[str], prediction_needed: bool) -> Optional[str]:
    """FORECAST, ANOMALY_ONLY, or None when the question asks for neither."""
    if prediction_needed:
        return "FORECAST"
    if intent == ANOMALY_INTENT:
        return "ANOMALY_ONLY"
    return None


def _series(rows, profile, target):
    """The one series stages 3-5 share: (values, labels, interpolated indices)."""
    if profile.layout == "SINGLE" and target:
        prepared = prediction_mod.prepare_series(rows, profile.temporal_column, target, profile.granularity)
        labels = [prediction_mod._format_label(d, profile.granularity) for d in prepared["dates"]]
        return prepared["values"], labels, set(prepared["filled_indices"])
    if profile.layout == "CROSS_SECTIONAL" and target and profile.dimension_columns:
        labels, values = extract_ordinal_series(rows, profile.dimension_columns[0], target)
        return values, labels, set()
    return [], [], set()


def run_prediction(result, intent: Optional[str], prediction_needed: bool, question: str = "",
                   confidence: float = 0.95) -> dict:
    mode = prediction_mode(intent, prediction_needed)
    if mode is None:
        raise ValueError("Neither a forecast nor anomaly detection was requested for this question.")

    adapted = input_adapter.adapt_result(result)
    analysis = build_analysis(intent, prediction_needed, question)
    profile = profile_results(adapted.rows, analysis=analysis)
    rows = coerce_measures(adapted.rows, profile)
    target = profile.measure_columns[0] if profile.measure_columns else None

    # ---- Stage 1: intent -> strategy ------------------------------------
    strategy = prediction_mod.map_intent_to_strategy(analysis)
    should_forecast = mode == "FORECAST" and strategy["strategy"] != PredictionStrategy.NONE.value

    readiness = prediction_mod.ReadinessReport()
    selection = prediction_mod.ModelSelection()
    forecast = prediction_mod.ForecastResult()
    anomaly_report = anomaly_mod.AnomalyReport()

    # ---- Stage 2: readiness ---------------------------------------------
    if should_forecast:
        readiness = prediction_mod.assess_readiness(
            profile, rows, target,
            input_info={"truncated": adapted.truncated, "row_count": adapted.row_count,
                        "rows_received": adapted.rows_received},
        )
    else:
        readiness.verdict = ReadinessVerdict.NOT_REQUESTED.value
        readiness.reason = ("No forecast was requested; anomalies are checked on the history."
                            if mode == "ANOMALY_ONLY"
                            else f"Intent '{analysis.primary_intent}' maps to no predictive strategy.")

    values, labels, filled = _series(rows, profile, target)

    # ---- Stages 3-4: model selection + forecast --------------------------
    if readiness.is_ready:
        selection = prediction_mod.select_model(analysis, readiness, values)
        forecast = prediction_mod.generate_forecast(
            analysis, profile, rows, readiness, selection, confidence=confidence, value_column=target)
    else:
        forecast.skipped_reason = readiness.reason

    # ---- Stage 5: dual-dimension anomaly detection -----------------------
    if values and analysis.primary_intent == "DETAIL_LOOKUP":
        anomaly_report.skipped_reason = ("The result is a list of records, not a series; anomalies are "
                                         "checked on values over time or across categories.")
    elif values:
        anomaly_report = anomaly_mod.detect_anomalies(
            values, labels, forecast=forecast, method="COMBINED", period=strategies._period(profile))
        # An interpolated period is not an observation and is never an anomaly.
        anomaly_report.historical_anomalies = [
            a for a in anomaly_report.historical_anomalies if a.index not in filled]
    elif profile.layout in ("GROUPED", "EVENTS"):
        anomaly_report.skipped_reason = (f"The result holds several series ({profile.layout.lower()} rows); "
                                         "anomalies are checked on a single series.")
    else:
        anomaly_report.skipped_reason = "No numeric series to check."

    # ---- Stage 1b: strategy execution ------------------------------------
    if should_forecast and readiness.verdict != ReadinessVerdict.TRUNCATED.value:
        strategy_result = strategies.execute(
            strategy["strategy"], analysis, profile, rows, forecast=forecast,
            anomaly_report=anomaly_report, horizon=analysis.horizon.value or 3, confidence=confidence)
    else:
        strategy_result = strategies.StrategyResult(requested=strategy["strategy"], skipped_reason=readiness.reason)
    if not forecast.generated:
        if strategy_result.executed:
            forecast.skipped_reason = ""  # the strategy delivered the prediction
        elif should_forecast and strategy_result.skipped_reason:
            forecast.skipped_reason = strategy_result.skipped_reason

    # ---- Chart: history + forecast + band + anomaly markers --------------
    chart, chart_reason = build_prediction_chart(rows, profile, forecast, anomaly_report, strategy_result)

    # ---- Stage 7: unified temporal summary (verified) ---------------------
    summary = summarization.summarize(
        profile, rows, analysis, forecast=forecast, anomaly_report=anomaly_report,
        scenario=None, strategy_result=strategy_result, readiness=readiness,
        use_llm=llm_summary_enabled())
    summary_block = summary.to_dict()
    summary_block.pop("rejected_narration", None)  # audit only, never shown

    anomalies = anomaly_report.to_dict()
    log_step(
        f"Prediction rendered | mode={mode} | intent={analysis.primary_intent} | strategy={strategy['strategy']}"
        f" | readiness={readiness.verdict} | model={forecast.model if forecast.generated else '-'}"
        f" | points={len(forecast.points)} | horizon={analysis.horizon.value} ({analysis.horizon.source})"
        f" | anomalies={len(anomalies['historical_anomalies'])} historical, "
        f"{len(anomalies['predictive_warnings'])} predicted | summary={summary_block['mode']}"
    )
    return {
        "status": "SUCCESS",
        "mode": mode,
        "intent": analysis.primary_intent,
        "horizon": {"value": analysis.horizon.value, "unit": analysis.horizon.unit,
                    "source": analysis.horizon.source},
        "strategy": strategy,
        "readiness": readiness.to_dict(),
        "model": selection.to_dict(),
        "forecast": forecast.to_dict(),
        "anomalies": anomalies,
        "strategy_result": strategy_result.to_dict(),
        "chart": {"spec": chart} if chart else None,
        "chart_reason": chart_reason,
        "summary": summary_block,
        "row_count": adapted.row_count,
    }
