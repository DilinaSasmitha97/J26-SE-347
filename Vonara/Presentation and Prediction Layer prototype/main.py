"""
CLI demonstration harness for Component 4.

Usage
-----
  python main.py analyze  "<question>"        Part 1 only: the comprehensive JSON
  python main.py demo     [scenario_name]     Full pipeline over synthetic data
  python main.py scenarios                    List available demo scenarios
  python main.py full     "<question>"        Full pipeline over a default series
  python main.py showcase                     Run four contrasting cases end to end

Add --json to print the raw envelope, --llm to enable hybrid understanding.
"""

import json
import sys

import pipeline
import synthetic_data


def _print_analysis(envelope: dict) -> None:
    a = envelope["analysis"]
    print("\n" + "=" * 78)
    print("PART 1 - QUERY UNDERSTANDING")
    print("=" * 78)
    print(f"  Query        : {a['query_understanding']['user_query']}")
    print(f"  Normalized   : {a['query_understanding']['normalized_query']}")
    print()
    intent = a["intent"]
    print(f"  Intent       : {intent['primary_intent']}  "
          f"(confidence {intent['confidence']:.2f}, source {intent['intent_source']})")
    if intent["secondary_intents"]:
        print(f"  Secondary    : {', '.join(intent['secondary_intents'])}")
    print(f"  Rationale    : {intent['rationale']}")
    print()
    ri = a["response_intent"]
    print(f"  Response     : {ri['intent']}  "
          f"(confidence {ri['confidence']:.2f}, source {ri['source']})")
    print(f"  Blocks       : {' + '.join(ri['blocks']) or '-'}")
    print(f"  Reason       : {ri['rationale']}")
    print()
    pr = a["prediction_request"]
    print(f"  Prediction   : {pr['prediction_required']}  (trigger {pr['prediction_trigger']})")
    if pr["horizon"]["value"]:
        print(f"  Horizon      : {pr['horizon']['value']} {pr['horizon']['unit']} "
              f"[{pr['horizon']['source']}]")
    if pr["what_if"]["present"]:
        wi = pr["what_if"]
        print(f"  What-if      : {wi['direction']} {wi['magnitude_pct']}% "
              f"on '{wi['parameter'] or 'primary metric'}'")
    print()
    sb = a["schema_binding"]
    tables = ", ".join(f"{t['table']}({t['role']},{t['confidence']:.2f})"
                       for t in sb["affected_tables"]) or "-"
    print(f"  Tables       : {tables}")
    cols = ", ".join(f"{c['column']}:{c['role']}" for c in sb["affected_columns"][:8]) or "-"
    print(f"  Columns      : {cols}")
    if sb["unresolved_terms"]:
        print(f"  Unresolved   : {', '.join(sb['unresolved_terms'])}")
    print()
    sr = a["semantic_roles"]
    metrics = ", ".join(f"{m['aggregation']}({m['column']})" for m in sr["metrics"]) or "-"
    print(f"  Metrics      : {metrics}")
    print(f"  Dimensions   : {', '.join(sr['dimensions']) or '-'}")
    print(f"  Time axis    : {sr['temporal_field'] or '-'} ({sr['temporal_granularity']})")
    if sr["limit"]:
        print(f"  Limit        : {sr['limit']}")
    print()
    vh = a["visualization_hint"]
    print(f"  Chart hint   : {vh['recommended_chart']}  (alts: {', '.join(vh['alternatives']) or '-'})")
    print(f"  Reason       : {vh['rationale']}")
    if a["governance"]["pii_columns_referenced"]:
        print(f"  PII flagged  : {', '.join(a['governance']['pii_columns_referenced'])}")
    if a["warnings"]:
        print(f"  WARNINGS     : {', '.join(a['warnings'])}")
    md = a["metadata"]
    print(f"\n  Mode {md['mode']} | model {md['model']} | tokens {md['total_tokens']} "
          f"| {md['execution_time_ms']} ms")


def _print_pipeline(envelope: dict) -> None:
    _print_analysis(envelope)

    rp = envelope["result_profile"]
    print("\n" + "=" * 78)
    print("RESULT PROFILE")
    print("=" * 78)
    print(f"  {rp['row_count']} rows x {rp['column_count']} columns | "
          f"time axis '{rp['temporal_column'] or '-'}' ({rp['granularity']}) | "
          f"time series: {rp['is_time_series']}")
    print(f"  Measures: {rp['measure_columns']}  Dimensions: {rp['dimension_columns']}")

    resp = envelope.get("response")
    if resp:
        ri = resp["response_intent"]
        print("\n" + "=" * 78)
        print("PART 5 - RESPONSE SHAPING")
        print("=" * 78)
        print(f"  Response     : {ri['intent']}  (confidence {ri['confidence']:.2f}, "
              f"source {ri['source']})")
        print(f"  Blocks       : {' + '.join(resp['blocks_emitted']) or '-'}")
        if ri["original_intent"] != ri["intent"] or ri["guardrails_applied"]:
            print(f"  Pre-execution: {ri['original_intent']}")
            for rule in ri["guardrails_applied"]:
                print(f"  GUARDRAIL    : {rule}")
        if "answer" in resp:
            ans = resp["answer"]
            qualifier = f" ({ans['qualifier']})" if ans["qualifier"] else ""
            print(f"  Answer       : {ans['label']} = {ans['display_value']}{qualifier}")
        if "summary" in resp:
            print(f"  Summary      : {resp['summary']['text'][:200]}")
        if "table" in resp:
            tb = resp["table"]
            print(f"  Table        : {tb['rows_returned']} of {tb['row_count']} rows, "
                  f"{len(tb['columns'])} columns"
                  + (" (truncated)" if tb["truncated"] else ""))
        if "chart" in resp:
            print(f"  Chart        : {resp['chart']['chart_type']}")

    viz = envelope["visualization"]
    meta = viz["_meta"]
    print("\n" + "=" * 78)
    print("PART 2 - ADAPTIVE VISUALIZATION")
    print("=" * 78)
    print(f"  Chart        : {meta['chart_type']}")
    print(f"  Reason       : {meta['selection_reason']}")
    if meta.get("adapted_from_intent_default"):
        print(f"  ADAPTED      : overrode intent default "
              f"'{meta['adapted_from_intent_default']}' based on result shape")
    print(f"  Encoding     : x={meta.get('x_field') or '-'}  y={meta.get('y_field') or '-'}"
          f"  color={meta.get('color_field') or '-'}")
    if meta.get("forecast_layered"):
        print(f"  Extension    : {', '.join(meta['extension_rules_applied'])}")
        print(f"  Layers       : {meta['layer_count']}")
    elif meta.get("extension_skipped_reason"):
        print(f"  Extension    : skipped - {meta['extension_skipped_reason']}")

    pred = envelope["prediction"]
    print("\n" + "=" * 78)
    print("PART 4 - PREDICTION LAYER")
    print("=" * 78)
    s1 = pred["stage_1_strategy"]
    print(f"  Stage 1 strategy   : {s1['strategy']}")
    print(f"                       {s1['rationale']}")
    s2 = pred["stage_2_readiness"]
    print(f"  Stage 2 readiness  : {s2['verdict']} ({s2['n_points']} points)")
    for check in s2["checks"]:
        print(f"                       - {check}")
    if not s2["is_ready"]:
        print(f"                       {s2['reason']}")
    s3 = pred["stage_3_model_selection"]
    if s3["model"] != "NONE":
        print(f"  Stage 3 model      : {s3['model']}")
        print(f"                       {s3['reason']}")
        sig = s3["signals"]
        print(f"                       signals: R2={sig.get('trend_r2')} "
              f"CV={sig.get('coefficient_of_variation')} "
              f"seasonalACF={sig.get('seasonal_acf')} "
              f"ADFp={sig.get('adf_p_value')}")
    s4 = pred["stage_4_forecast"]
    if s4["generated"]:
        print(f"  Stage 4 forecast   : {s4['horizon']} periods, "
              f"{int(s4['confidence_level']*100)}% intervals "
              f"(in-sample MAPE {s4['in_sample_mape']}%)")
        for p in s4["points"]:
            print(f"      {p['label']:>10} : {p['predicted']:>12,.2f}  "
                  f"[{p['lower_bound']:>12,.2f} .. {p['upper_bound']:>12,.2f}]")
    elif s4["skipped_reason"]:
        print(f"  Stage 4 forecast   : skipped - {s4['skipped_reason']}")
    s5 = pred["stage_5_anomaly"]
    if s5["evaluated"]:
        print(f"  Stage 5 anomalies  : {len(s5['historical_anomalies'])} historical, "
              f"{len(s5['predictive_warnings'])} predicted "
              f"[regime {s5['volatility_regime']}, band "
              f"{s5['lower_threshold']:,.1f} .. {s5['upper_threshold']:,.1f}]")
        for a in s5["historical_anomalies"]:
            print(f"      HIST  {a['label']:>10} : {a['value']:>12,.2f} "
                  f"{a['direction']} {a['severity']} (z={a['z_score']})")
        for a in s5["predictive_warnings"]:
            print(f"      PRED  {a['label']:>10} : {a['value']:>12,.2f} "
                  f"{a['direction']} {a['severity']} (z={a['z_score']})")
    else:
        print(f"  Stage 5 anomalies  : skipped - {s5['skipped_reason']}")
    s6 = pred["stage_6_scenario"]
    if s6["simulated"]:
        print(f"  Stage 6 what-if    : {s6['spec']['direction']} "
              f"{s6['spec']['magnitude_pct']}% -> total moves "
              f"{s6['baseline_total']:,.2f} -> {s6['scenario_total']:,.2f} "
              f"({s6['total_delta_pct']:+.1f}%)")
        for d in s6["deltas"]:
            print(f"      {d['label']:>10} : {d['baseline']:>12,.2f} -> "
                  f"{d['scenario']:>12,.2f} ({d['delta_pct']:+.1f}%)")
    elif s6["skipped_reason"]:
        print(f"  Stage 6 what-if    : {s6['skipped_reason']}")

    summ = envelope["summary"]
    print("\n" + "=" * 78)
    print("PART 3 / STAGE 7 - UNIFIED TEMPORAL SUMMARY")
    print("=" * 78)
    print(f"  Mode: {summ['mode']} | {summ['claim_count']} verified claims | "
          f"verification passed: {summ['verification'].get('passed')}")
    print()
    for line in summ["text"].split("\n"):
        print(f"  {line}")
    print()
    print("  Claim trace:")
    for c in summ["claims"]:
        print(f"    [{c['claim_id']:<6}] {c['dimension']:<10} {c['kind']:<22} "
              f"value={c['value']:<14,.4f} <- {c['derivation']}")

    if envelope["warnings"]:
        print(f"\n  PIPELINE WARNINGS: {', '.join(envelope['warnings'])}")

    prof = envelope["profiling"]
    print("\n" + "=" * 78)
    print(f"TIMING - total {prof['total_execution_ms']} ms")
    print("=" * 78)
    for stage, ms in prof["stage_breakdown_ms"].items():
        print(f"  {stage:<34} {ms:>8.2f} ms")


def cmd_analyze(query: str, use_llm: bool, as_json: bool) -> None:
    envelope = pipeline.analyze_only(
        query, synthetic_data.SCHEMA_DDL,
        security_context={"tenant_id": "tenant_a_123", "user_role": "FINANCE_VIEWER"},
        use_llm=use_llm,
    )
    if as_json:
        print(json.dumps(envelope, indent=2, default=str))
    else:
        _print_analysis(envelope)


def cmd_demo(name: str, use_llm: bool, as_json: bool) -> None:
    suite = synthetic_data.benchmark_suite()
    scenario = next((s for s in suite if s["name"] == name), None) if name else suite[0]
    if scenario is None:
        print(f"Unknown scenario '{name}'. Available:")
        for s in suite:
            print(f"  {s['name']}")
        return

    print(f"\n### SCENARIO: {scenario['name']}")
    print(f"### {scenario['description']}")
    print(f"### Ground truth: n={scenario['ground_truth']['n_periods']}, "
          f"trend={scenario['ground_truth']['has_trend']}, "
          f"seasonal={scenario['ground_truth']['has_seasonality']}, "
          f"noise={scenario['ground_truth']['noise_pct']}, "
          f"injected anomalies at {scenario['ground_truth']['anomaly_indices']}")
    print(f"### Expected model: {scenario['expected_model']}")

    envelope = pipeline.run(
        scenario["query"],
        rows=scenario["rows"],
        schema_meta=scenario["schema"],
        security_context={"tenant_id": "tenant_a_123", "user_role": "FINANCE_VIEWER"},
        use_llm=use_llm,
    )
    if as_json:
        print(json.dumps(envelope, indent=2, default=str))
    else:
        _print_pipeline(envelope)
        selected = envelope["prediction"]["stage_3_model_selection"]["model"]
        verdict = "MATCH" if selected == scenario["expected_model"] else "DIVERGED"
        print(f"\n>>> Model selection vs ground truth: {selected} "
              f"(expected {scenario['expected_model']}) - {verdict}")


def cmd_full(query: str, use_llm: bool, as_json: bool) -> None:
    rows, truth = synthetic_data.generate_timeseries(
        n_periods=24, level=3500, trend=140, noise_pct=0.06,
        anomaly_indices=[9, 18], anomaly_magnitude=3.0, seed=42,
    )
    envelope = pipeline.run(
        query, rows=rows, schema_meta=synthetic_data.SCHEMA_DDL,
        security_context={"tenant_id": "tenant_a_123", "user_role": "FINANCE_VIEWER"},
        use_llm=use_llm,
    )
    if as_json:
        print(json.dumps(envelope, indent=2, default=str))
    else:
        print(f"\n### Synthetic series: 24 months, anomalies injected at "
              f"{truth['anomaly_indices']}")
        _print_pipeline(envelope)


def cmd_showcase(use_llm: bool) -> None:
    """Four contrasting cases, to show adaptivity in one screen."""
    cases = [
        ("Trend + explicit forecast",
         "Show my monthly software expenses and predict the next 3 months",
         synthetic_data.generate_timeseries(
             n_periods=24, level=3500, trend=140, noise_pct=0.05, seed=42)[0]),
        ("Ranking over categories (no forecast possible)",
         "Which are the top 5 categories by total amount",
         synthetic_data.generate_categorical(5, "category", "total_amount")),
        ("Anomaly detection, dual dimension",
         "Are there unusual spikes in my monthly spend and will they continue",
         synthetic_data.generate_timeseries(
             n_periods=30, level=12000, trend=300, noise_pct=0.05,
             anomaly_indices=[8, 17, 25], seed=106)[0]),
        ("What-if scenario",
         "Show monthly expenses, predict 3 months, what if I reduce spending by 20%",
         synthetic_data.generate_timeseries(
             n_periods=24, level=5000, trend=180, noise_pct=0.05, seed=108)[0]),
    ]

    for title, query, rows in cases:
        print("\n\n" + "#" * 78)
        print(f"# {title}")
        print("#" * 78)
        envelope = pipeline.run(
            query, rows=rows, schema_meta=synthetic_data.SCHEMA_DDL,
            security_context={"tenant_id": "tenant_a_123"},
            use_llm=use_llm,
        )
        a = envelope["analysis"]
        pred = envelope["prediction"]
        meta = envelope["visualization"]["_meta"]
        print(f"  intent      : {a['intent']['primary_intent']} "
              f"({a['intent']['confidence']:.2f})")
        print(f"  prediction  : {a['prediction_request']['prediction_required']} "
              f"/ strategy {pred['stage_1_strategy']['strategy']}")
        print(f"  readiness   : {pred['stage_2_readiness']['verdict']}")
        print(f"  model       : {pred['stage_3_model_selection']['model']}")
        print(f"  chart       : {meta['chart_type']} "
              f"(layers: {meta.get('layer_count', 1)})")
        print(f"  anomalies   : {len(pred['stage_5_anomaly']['historical_anomalies'])} hist / "
              f"{len(pred['stage_5_anomaly']['predictive_warnings'])} pred")
        print(f"  claims      : {envelope['summary']['claim_count']} "
              f"(verified: {envelope['summary']['verification'].get('passed')})")
        print(f"\n  {envelope['summary']['text'][:400]}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    use_llm = "--llm" in flags
    as_json = "--json" in flags

    if not args:
        print(__doc__)
        return

    command = args[0].lower()

    if command == "analyze":
        if len(args) < 2:
            print("Usage: python main.py analyze \"<question>\"")
            return
        cmd_analyze(" ".join(args[1:]), use_llm, as_json)

    elif command == "demo":
        cmd_demo(args[1] if len(args) > 1 else "", use_llm, as_json)

    elif command == "scenarios":
        print("Available demo scenarios:\n")
        for s in synthetic_data.benchmark_suite():
            print(f"  {s['name']:<26} {s['description']}")
            print(f"  {'':<26} expects {s['expected_model']}\n")

    elif command == "full":
        if len(args) < 2:
            print("Usage: python main.py full \"<question>\"")
            return
        cmd_full(" ".join(args[1:]), use_llm, as_json)

    elif command == "showcase":
        cmd_showcase(use_llm)

    else:
        print(__doc__)


if __name__ == "__main__":
    main()
