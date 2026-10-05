"""
Component 4 orchestrator.

Runs the four parts in order and returns one comprehensive JSON envelope:

    Part 1  Query Understanding      query_analyzer.analyze
    Part 2  Adaptive Visualization   visualization.build_chart
    Part 4  Prediction (Stages 1-6)  prediction / anomaly / whatif
    Part 3  Unified Summarization    summarization.summarize  (Stage 7)

Prediction runs BEFORE summarization because Stage 7 must narrate forecast and
anomaly claims alongside historical ones - that ordering is what makes the
summary "unified" across both temporal dimensions.

Two entry points:
    analyze_only(...)  - Part 1 alone, no result set required.
    run(...)           - the full pipeline over a masked result set.
"""

import hashlib
import json

import anomaly as anomaly_mod
import input_adapter
import prediction as prediction_mod
import query_analyzer
import response_intent as response_intent_mod
import response_renderer
import strategies
import summarization
import visualization
import whatif as whatif_mod
from profiler import Profiler, log_step
from result_profiler import coerce_measures, extract_series, profile_results
from schemas import PredictionStrategy, ReadinessVerdict, ResponseIntentResult

PIPELINE_VERSION = "1.0"

# Intent-informed cache. Two requests share a cache entry only when the query,
# the tenant and the result payload all match, so a cached presentation can
# never leak across a tenant boundary.
_CACHE = {}
CACHE_MAX_ENTRIES = 256


def _cache_key(user_query: str, rows: list, tenant_id: str, options: dict) -> str:
    payload = json.dumps(
        {
            "q": (user_query or "").strip().lower(),
            "t": tenant_id or "",
            "r": rows,
            "o": {k: options.get(k) for k in sorted(options)},
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def clear_cache() -> None:
    _CACHE.clear()


def analyze_only(
    user_query: str,
    schema_meta=None,
    security_context: dict = None,
    use_llm: bool = True,
) -> dict:
    """
    Part 1 in isolation: understand the request without executing it.

    This is the endpoint Members 1 and 3 call *before* SQL generation, to learn
    the intent, the affected tables and whether a prediction will be wanted.
    """
    profiler = Profiler("analyze_only")
    with profiler.stage("Query Understanding", "Part 1: Query Understanding"):
        analysis = query_analyzer.analyze(
            user_query, schema_meta, security_context, use_llm, profiler
        )
    return {
        "status": "SUCCESS",
        "pipeline_version": PIPELINE_VERSION,
        "analysis": analysis.to_dict(),
        "profiling": profiler.report(),
    }


def run(
    user_query: str,
    rows: list = None,
    schema_meta=None,
    schema_types: dict = None,
    security_context: dict = None,
    use_llm: bool = True,
    use_llm_summary: bool = False,
    confidence_level: float = 0.95,
    horizon: int = None,
    scenario_text: str = "",
    value_column: str = None,
    enable_cache: bool = True,
) -> dict:
    """
    Execute the full presentation & prediction pipeline.

    Args:
        user_query:       the original natural-language question.
        rows:             masked result set from Member 2 - either its
                          columnar {columns, rows, masking} result or a list
                          of row dicts; see input_adapter.py.
        schema_meta:      DDL or dict schema, for Part 1 binding.
        schema_types:     optional {column: sql_type} hints for the result set.
        security_context: tenant/role context from Member 3.
        use_llm:          enable hybrid query understanding.
        use_llm_summary:  enable verified LLM narration (still gated).
        horizon:          override the forecast horizon in periods.
        scenario_text:    an explicit what-if clause; when empty, any what-if
                          detected in `user_query` is used instead.
        value_column:     force which measure to forecast.

    Returns:
        The comprehensive response envelope (JSON-serialisable).
    """
    adapted = input_adapter.adapt_result(rows)
    rows = adapted.rows
    security_context = security_context or {}
    options = {
        "use_llm": use_llm,
        "use_llm_summary": use_llm_summary,
        "confidence_level": confidence_level,
        "horizon": horizon,
        "scenario_text": scenario_text,
        "value_column": value_column,
    }

    key = _cache_key(user_query, rows, security_context.get("tenant_id", ""), options)
    if enable_cache and key in _CACHE:
        cached = json.loads(json.dumps(_CACHE[key]))
        cached["cache"] = {"hit": True, "key": key[:16]}
        log_step("Cache hit - returning stored presentation.")
        return cached

    profiler = Profiler("component4")
    warnings = list(adapted.warnings)

    # ---- Part 1: Query Understanding ----------------------------------
    with profiler.stage("Query Understanding", "Part 1: Query Understanding"):
        analysis = query_analyzer.analyze(
            user_query, schema_meta, security_context, use_llm, profiler
        )

    # ---- Result profiling ---------------------------------------------
    with profiler.stage("Result Profiling", "Result Profiling"):
        profile = profile_results(rows, schema_types, analysis)
        rows = coerce_measures(rows, profile)
    warnings.extend(profile.warnings)

    # ---- Part 4 Stage 1: intent -> strategy ----------------------------
    with profiler.stage("Stage 1 Intent Mapping", "Part 4: Prediction"):
        strategy = prediction_mod.map_intent_to_strategy(analysis)

    readiness = prediction_mod.ReadinessReport()
    selection = prediction_mod.ModelSelection()
    forecast = prediction_mod.ForecastResult()
    anomaly_report = anomaly_mod.AnomalyReport()
    scenario = whatif_mod.ScenarioResult()

    strategy_active = strategy["strategy"] != PredictionStrategy.NONE.value
    should_predict = analysis.prediction_required and strategy_active

    target_measure = value_column or (
        profile.measure_columns[0] if profile.measure_columns else None
    )

    # ---- Part 4 Stage 2: readiness -------------------------------------
    if should_predict:
        with profiler.stage("Stage 2 Readiness", "Part 4: Prediction"):
            readiness = prediction_mod.assess_readiness(profile, rows, target_measure)
    else:
        # Distinguish "we never asked" from "we asked and the data said no" -
        # reporting NOT_TEMPORAL for an unrequested forecast would misattribute
        # the outcome to the data.
        readiness.verdict = ReadinessVerdict.NOT_REQUESTED.value
        readiness.reason = (
            "No forecast was requested for this query."
            if not analysis.prediction_required
            else f"Intent '{analysis.primary_intent}' maps to no predictive strategy."
        )
        readiness.checks.append(f"readiness gates not evaluated: {readiness.reason}")

    series_values = []
    series_labels = []
    # Single-series stages only run on a SINGLE layout: a grouped or raw-row
    # result interleaves several series, and anything computed on the mixture
    # (a forecast, an anomaly band) describes no real quantity.
    filled_indices = set()
    if profile.layout == "SINGLE" and target_measure:
        # The same regular series the forecast sees (small gaps interpolated),
        # so model selection, forecast and anomaly bands share one time axis.
        prepared = prediction_mod.prepare_series(
            rows, profile.temporal_column, target_measure, profile.granularity)
        dates, series_values = prepared["dates"], prepared["values"]
        filled_indices = set(prepared["filled_indices"])
        series_labels = [
            prediction_mod._format_label(d, profile.granularity) for d in dates
        ]
    elif profile.layout == "CROSS_SECTIONAL" and target_measure:
        from result_profiler import extract_ordinal_series

        axis = profile.dimension_columns[0] if profile.dimension_columns else ""
        if axis:
            series_labels, series_values = extract_ordinal_series(rows, axis, target_measure)

    # ---- Part 4 Stages 3-4: model selection + forecast ------------------
    if readiness.is_ready:
        with profiler.stage("Stage 3 Model Selection", "Part 4: Prediction"):
            selection = prediction_mod.select_model(analysis, readiness, series_values)
        with profiler.stage("Stage 4 Forecast", "Part 4: Prediction"):
            forecast = prediction_mod.generate_forecast(
                analysis, profile, rows, readiness, selection,
                horizon=horizon, confidence=confidence_level,
                value_column=target_measure,
            )
    else:
        forecast.skipped_reason = readiness.reason

    # ---- Part 4 Stage 5: dual-dimension anomaly detection ---------------
    with profiler.stage("Stage 5 Anomaly Detection", "Part 4: Prediction"):
        if series_values:
            anomaly_report = anomaly_mod.detect_anomalies(
                series_values, series_labels, forecast=forecast,
                period=strategies._period(profile),
            )
            # An interpolated point is not an observation and can never be
            # reported as an anomaly.
            anomaly_report.historical_anomalies = [
                a for a in anomaly_report.historical_anomalies
                if a.index not in filled_indices
            ]
        elif profile.layout in ("GROUPED", "EVENTS"):
            anomaly_report.skipped_reason = (
                f"The result holds several series ({profile.layout.lower()} rows); "
                "anomaly bands are only computed on a single series."
            )
        else:
            anomaly_report.skipped_reason = "No numeric series available."

    # ---- Part 4 Stage 1 (execution): the strategy-specific prediction ----
    with profiler.stage("Stage 1 Strategy Execution", "Part 4: Prediction"):
        if should_predict:
            strategy_result = strategies.execute(
                strategy["strategy"], analysis, profile, rows, forecast=forecast,
                anomaly_report=anomaly_report, horizon=horizon or analysis.horizon.value or 3,
                confidence=confidence_level,
            )
        else:
            strategy_result = strategies.StrategyResult(
                requested=strategy["strategy"], skipped_reason=readiness.reason)
        if not forecast.generated:
            if strategy_result.executed:
                # The strategy delivered the prediction (e.g. one forecast per
                # region); a "no forecast was produced" claim would contradict it.
                forecast.skipped_reason = ""
            elif should_predict and strategy_result.skipped_reason:
                # The strategy's reason is the more specific one for the user.
                forecast.skipped_reason = strategy_result.skipped_reason

    # ---- Part 4 Stage 6: what-if simulation -----------------------------
    with profiler.stage("Stage 6 What-If", "Part 4: Prediction"):
        spec = None
        if scenario_text:
            spec = whatif_mod.parse_scenario(scenario_text, target_measure or "")
        elif analysis.what_if.present:
            spec = whatif_mod.scenario_from_analysis(analysis)
        if spec is not None:
            scenario = whatif_mod.simulate(
                forecast, spec=spec, historical_values=series_values
            )
            if not scenario.simulated and scenario.skipped_reason:
                warnings.append(f"WHAT_IF_SKIPPED: {scenario.skipped_reason}")
        else:
            scenario.skipped_reason = "No what-if scenario supplied."

    # ---- Part 5a: response shape, settled against the real result set ----
    # Runs before visualization so the chart is only built when something will
    # render it. Guardrails never *promote* a shape to CHART - they only move
    # away from it when the data cannot support one - so deciding here cannot
    # leave a later stage wanting a spec that was never made.
    with profiler.stage("Response Shaping", "Part 5: Response Shaping"):
        decided = ResponseIntentResult(
            intent=analysis.response_intent,
            confidence=analysis.response_intent_confidence,
            source=analysis.response_intent_source,
            rationale=analysis.response_intent_rationale,
            blocks=list(analysis.response_blocks),
            answer_focus=analysis.answer_focus,
            is_data_request=analysis.is_data_request,
            not_a_request_reason=analysis.not_a_request_reason,
            evidence_grade=analysis.response_evidence_grade,
            scores=(analysis.response_intent_evidence or {}).get("scores", {}),
            matched_markers=(analysis.response_intent_evidence or {}).get(
                "matched_markers", {}
            ),
            runner_up=(analysis.response_intent_evidence or {}).get("runner_up", ""),
            margin=(analysis.response_intent_evidence or {}).get("margin", 0.0),
            # Carry the classifier's own warnings so the response block is
            # self-contained; they also reach the envelope via `analysis`.
            warnings=[
                w for w in analysis.warnings
                if w in ("NOT_A_DATA_REQUEST", "LOW_CONFIDENCE_RESPONSE_INTENT",
                         "NO_LEXICAL_EVIDENCE")
            ],
        )
        decided = response_intent_mod.apply_guardrails(decided, profile, rows)

    # ---- Part 2: adaptive visualization + grammar extension -------------
    with profiler.stage("Visualization", "Part 2: Visualization"):
        if "CHART" in decided.blocks:
            base_spec = visualization.build_chart(analysis, profile, rows)
            chart_spec = visualization.extend_with_forecast(
                base_spec,
                forecast=forecast if forecast.generated else None,
                anomaly_report=anomaly_report if anomaly_report.evaluated else None,
                scenario=scenario if scenario.simulated else None,
                strategy_result=strategy_result,
            )
        else:
            # The key stays in the envelope so the contract does not change
            # shape between requests; `chart_type` of "none" is the signal.
            chart_spec = {
                "_meta": {
                    "chart_type": "none",
                    "selection_reason": (
                        f"No chart built: response intent {decided.intent} "
                        f"emits {' + '.join(decided.blocks)}."
                    ),
                    "rationale": "",
                    "skipped": True,
                }
            }
            log_step(
                f"Chart construction skipped - {decided.intent} needs no chart.",
                level="DEBUG",
            )

    # ---- Part 3 / Stage 7: unified temporal summarization ---------------
    with profiler.stage("Unified Summarization", "Part 3: Summarization"):
        summary = summarization.summarize(
            profile, rows, analysis,
            forecast=forecast if forecast.generated else forecast,
            anomaly_report=anomaly_report,
            scenario=scenario if scenario.simulated else None,
            strategy_result=strategy_result,
            readiness=readiness,
            # Claims are always computed - they are cheap, deterministic, and
            # the envelope's `summary` key is part of the existing contract.
            # Only the paid LLM narration is gated, and only when no SUMMARY
            # block will be rendered from it.
            use_llm=use_llm_summary and "SUMMARY" in decided.blocks,
            profiler=profiler,
        )

    # ---- Part 5b: assemble the blocks the decided shape declares ---------
    with profiler.stage("Response Assembly", "Part 5: Response Shaping"):
        response_payload = response_renderer.render(
            decided,
            analysis=analysis,
            profile=profile,
            rows=rows,
            chart_spec=chart_spec,
            summary=summary,
            forecast=forecast,
            readiness=readiness,
            scenario=scenario if scenario.simulated else None,
            strategy_result=strategy_result,
        )

    warnings.extend(summary.warnings)
    for w in decided.warnings:
        if w not in warnings:
            warnings.append(w)
    for w in analysis.warnings:
        if w not in warnings:
            warnings.append(w)

    response = {
        "status": "SUCCESS",
        "pipeline_version": PIPELINE_VERSION,
        "input": adapted.to_dict(),
        "analysis": analysis.to_dict(),
        "result_profile": profile.to_dict(),
        "response": response_payload,
        "visualization": chart_spec,
        "prediction": {
            "stage_1_strategy": strategy,
            "stage_1_strategy_result": strategy_result.to_dict(),
            "stage_2_readiness": readiness.to_dict(),
            "stage_3_model_selection": selection.to_dict(),
            "stage_4_forecast": forecast.to_dict(),
            "stage_5_anomaly": anomaly_report.to_dict(),
            "stage_6_scenario": scenario.to_dict(),
        },
        "summary": summary.to_dict(),
        "warnings": warnings,
        "cache": {"hit": False, "key": key[:16]},
        "profiling": profiler.report(),
    }

    if enable_cache:
        if len(_CACHE) >= CACHE_MAX_ENTRIES:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = json.loads(json.dumps(response, default=str))

    log_step(
        f"Pipeline complete | intent={analysis.primary_intent} "
        f"response={decided.intent} blocks={'+'.join(decided.blocks)} "
        f"chart={chart_spec['_meta']['chart_type']} "
        f"forecast={'yes' if forecast.generated else 'no'} "
        f"claims={len(summary.claims)} in {profiler.total_ms:.0f} ms"
    )
    return response
