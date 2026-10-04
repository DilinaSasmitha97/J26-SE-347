"""
Evaluation harness for Component 4.

Runs the three metric families the TAF commits to, plus two supporting audits:

  1. Intent Classification Accuracy   - accuracy, per-class P/R/F1, confusion
  2. Prediction Accuracy              - out-of-sample RMSE / MAE / MAPE vs baselines
  3. Anomaly Detection Rate           - precision/recall/F1 vs STATIC threshold control
  4. Model Selection Agreement        - Stage 3 choice vs generating process
  5. Summary Grounding Rate           - fraction of claims that verify

Every number is produced from synthetic data with a fixed seed and, by default,
with LLM_PROVIDER unset - so results are reproducible on any machine.

Usage:
  python evaluate.py                # everything
  python evaluate.py intent         # one suite
  python evaluate.py --llm          # include hybrid-mode intent accuracy
  python evaluate.py --json out.json
"""

import json
import sys
from collections import defaultdict

import anomaly as anomaly_mod
import prediction as prediction_mod
import query_analyzer
import synthetic_data
from result_profiler import profile_results
from schemas import ALL_INTENTS

TESTSET_PATH = "intent_testset.json"
SEPARATOR = "=" * 78


# ==========================================================================
# 1. Intent classification accuracy
# ==========================================================================


def evaluate_intent(use_llm: bool = False, split: str = "test") -> dict:
    with open(TESTSET_PATH, "r", encoding="utf-8") as fh:
        testset = json.load(fh)

    cases = [c for c in testset["cases"] if split == "all" or c.get("split") == split]
    schema = synthetic_data.SCHEMA_DDL

    correct = 0
    pred_correct = 0
    table_correct = 0
    warning_correct = 0
    warning_total = 0
    confusion = defaultdict(lambda: defaultdict(int))
    failures = []

    for case in cases:
        analysis = query_analyzer.analyze(
            case["query"], schema,
            security_context={"tenant_id": "tenant_a_123"},
            use_llm=use_llm,
        )
        gold = case["intent"]
        got = analysis.primary_intent
        confusion[gold][got] += 1

        if got == gold:
            correct += 1
        else:
            failures.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "expected": gold,
                    "got": got,
                    "confidence": analysis.intent_confidence,
                    "rationale": analysis.intent_rationale,
                }
            )

        if analysis.prediction_required == case.get("prediction_required", False):
            pred_correct += 1

        bound = {t.table for t in analysis.affected_tables}
        if set(case.get("tables", [])) <= bound:
            table_correct += 1

        if case.get("expect_warning"):
            warning_total += 1
            if case["expect_warning"] in analysis.warnings:
                warning_correct += 1

    n = len(cases)

    # Per-class precision / recall / F1 from the confusion matrix.
    per_class = {}
    for intent in ALL_INTENTS:
        tp = confusion[intent][intent]
        fn = sum(v for k, v in confusion[intent].items() if k != intent)
        fp = sum(
            confusion[g][intent] for g in confusion if g != intent
        )
        support = tp + fn
        if support == 0 and tp + fp == 0:
            continue
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_class[intent] = {
            "support": support,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    macro_f1 = (
        sum(v["f1"] for v in per_class.values()) / len(per_class) if per_class else 0.0
    )

    return {
        "mode": "HYBRID" if use_llm else "RULE_ONLY",
        "split": split,
        "n_cases": n,
        "intent_accuracy": round(correct / n, 4) if n else 0.0,
        "macro_f1": round(macro_f1, 4),
        "prediction_flag_accuracy": round(pred_correct / n, 4) if n else 0.0,
        "table_binding_recall": round(table_correct / n, 4) if n else 0.0,
        "security_warning_recall": (
            round(warning_correct / warning_total, 4) if warning_total else None
        ),
        "per_class": per_class,
        "failures": failures,
        "confusion": {g: dict(p) for g, p in confusion.items()},
    }


# ==========================================================================
# 2. Prediction accuracy (out-of-sample)
# ==========================================================================

# Naive baselines every forecasting paper must beat to claim anything.
BASELINE_MODELS = ["WEIGHTED_MOVING_AVERAGE", "LINEAR_REGRESSION", "EXPONENTIAL_SMOOTHING"]


def evaluate_prediction(holdout: int = 3) -> dict:
    suite = synthetic_data.benchmark_suite()
    rows_out = []
    selected_totals = {"rmse": 0.0, "mae": 0.0, "mape": 0.0, "n": 0, "mape_values": []}
    baseline_totals = {
        m: {"rmse": 0.0, "mae": 0.0, "mape": 0.0, "n": 0, "mape_values": []}
        for m in BASELINE_MODELS
    }

    for scenario in suite:
        analysis = query_analyzer.analyze(
            scenario["query"], scenario["schema"], use_llm=False
        )
        profile = profile_results(scenario["rows"], analysis=analysis)
        readiness = prediction_mod.assess_readiness(profile, scenario["rows"])

        if not readiness.is_ready:
            rows_out.append(
                {
                    "scenario": scenario["name"],
                    "skipped": True,
                    "verdict": readiness.verdict,
                    "reason": readiness.reason,
                }
            )
            continue

        from result_profiler import extract_series

        _, values = extract_series(
            scenario["rows"], profile.temporal_column, profile.measure_columns[0]
        )
        selection = prediction_mod.select_model(analysis, readiness, values)
        rule_choice = prediction_mod.select_model(analysis, readiness, values, guard=False).model
        period = selection.seasonal_period

        chosen = prediction_mod.backtest(values, selection.model, holdout, period)
        entry = {
            "scenario": scenario["name"],
            "skipped": False,
            "n_points": len(values),
            "selected_model": selection.model,
            "expected_model": scenario["expected_model"],
            # The rules are judged against the generating process; the guard may
            # then overrule a correct rule on a short noisy history, which is
            # measured in evaluate_forecasting.py rather than counted as a miss.
            "rule_model": rule_choice,
            "selection_match": rule_choice == scenario["expected_model"],
            "guard_override": selection.model != rule_choice,
            "selected": chosen,
            "baselines": {},
        }

        if chosen.get("ok"):
            selected_totals["rmse"] += chosen["rmse"]
            selected_totals["mae"] += chosen["mae"]
            selected_totals["mape"] += chosen["mape"]
            selected_totals["mape_values"].append(chosen["mape"])
            selected_totals["n"] += 1

        for model in BASELINE_MODELS:
            b = prediction_mod.backtest(values, model, holdout, period)
            entry["baselines"][model] = b
            if b.get("ok"):
                baseline_totals[model]["rmse"] += b["rmse"]
                baseline_totals[model]["mae"] += b["mae"]
                baseline_totals[model]["mape"] += b["mape"]
                baseline_totals[model]["mape_values"].append(b["mape"])
                baseline_totals[model]["n"] += 1

        rows_out.append(entry)

    def summarise(totals):
        n = totals["n"]
        if not n:
            return None
        mapes = sorted(totals["mape_values"])
        median_mape = (
            mapes[len(mapes) // 2]
            if len(mapes) % 2
            else (mapes[len(mapes) // 2 - 1] + mapes[len(mapes) // 2]) / 2
        )
        return {
            "rmse": round(totals["rmse"] / n, 4),
            "mae": round(totals["mae"] / n, 4),
            "mape": round(totals["mape"] / n, 4),
            # The mean MAPE is dominated by any single unforecastable series, so
            # the median is reported alongside it rather than instead of it.
            "median_mape": round(median_mape, 4),
            "scenarios": n,
        }

    mean_of = summarise

    evaluated = [r for r in rows_out if not r["skipped"]]
    matches = sum(1 for r in evaluated if r["selection_match"])

    return {
        "holdout_periods": holdout,
        "scenarios_total": len(suite),
        "scenarios_forecast": len(evaluated),
        "scenarios_skipped": len(rows_out) - len(evaluated),
        "model_selection_agreement": (
            round(matches / len(evaluated), 4) if evaluated else 0.0
        ),
        "guard_overrides": sum(1 for r in evaluated if r["guard_override"]),
        "selected_model_mean": mean_of(selected_totals),
        "fixed_baseline_means": {m: mean_of(t) for m, t in baseline_totals.items()},
        "per_scenario": rows_out,
    }


# ==========================================================================
# 3. Anomaly detection rate (adaptive vs static control)
# ==========================================================================


def _score_detection(detected_indices: set, truth_indices: set, n: int) -> dict:
    tp = len(detected_indices & truth_indices)
    fp = len(detected_indices - truth_indices)
    fn = len(truth_indices - detected_indices)
    tn = n - tp - fp - fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) else 0.0,
    }


def evaluate_anomaly() -> dict:
    """
    Compare the adaptive detector against the textbook static 1.5*IQR control.

    Cases span trending, seasonal, flat and volatile processes so the comparison
    is not won on a single favourable shape.
    """
    cases = [
        ("trend_3_anomalies", dict(n_periods=30, level=12000, trend=300, noise_pct=0.05,
                                   anomaly_indices=[8, 17, 25], seed=201)),
        ("flat_2_anomalies", dict(n_periods=24, level=8000, trend=0, noise_pct=0.06,
                                  anomaly_indices=[7, 19], seed=202)),
        ("seasonal_2_anomalies", dict(n_periods=36, level=20000, trend=80,
                                      seasonal_amplitude=0.25, noise_pct=0.05,
                                      anomaly_indices=[11, 29], seed=203)),
        ("volatile_3_anomalies", dict(n_periods=30, level=5000, trend=50, noise_pct=0.25,
                                      anomaly_indices=[6, 15, 24], anomaly_magnitude=4.0,
                                      seed=204)),
        ("steep_trend_2_anomalies", dict(n_periods=28, level=4000, trend=600,
                                         noise_pct=0.04, anomaly_indices=[10, 21],
                                         seed=205)),
        ("clean_no_anomalies", dict(n_periods=24, level=15000, trend=200,
                                    noise_pct=0.05, anomaly_indices=[], seed=206)),
    ]

    per_case = []
    adaptive_tot = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    static_tot = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    for name, params in cases:
        rows, truth = synthetic_data.generate_timeseries(**params)
        values = [r["amount"] for r in rows]
        labels = [r["invoice_date"] for r in rows]
        gold = set(truth["anomaly_indices"])
        n = len(values)

        adaptive = anomaly_mod.detect_anomalies(values, labels)
        static = anomaly_mod.detect_anomalies(values, labels, static_baseline=True)

        adaptive_idx = {a.index for a in adaptive.historical_anomalies}
        static_idx = {a.index for a in static.historical_anomalies}

        a_score = _score_detection(adaptive_idx, gold, n)
        s_score = _score_detection(static_idx, gold, n)

        for key in adaptive_tot:
            adaptive_tot[key] += a_score[key]
            static_tot[key] += s_score[key]

        per_case.append(
            {
                "case": name,
                "n_points": n,
                "injected": sorted(gold),
                "adaptive": {
                    **a_score,
                    "detected": sorted(adaptive_idx),
                    "detrended": adaptive.detrended,
                    "regime": adaptive.volatility_regime,
                },
                "static": {**s_score, "detected": sorted(static_idx)},
            }
        )

    def micro(t):
        precision = t["tp"] / (t["tp"] + t["fp"]) if (t["tp"] + t["fp"]) else 0.0
        recall = t["tp"] / (t["tp"] + t["fn"]) if (t["tp"] + t["fn"]) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        fpr = t["fp"] / (t["fp"] + t["tn"]) if (t["fp"] + t["tn"]) else 0.0
        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "false_positive_rate": round(fpr, 4),
            **t,
        }

    return {
        "cases": len(cases),
        "adaptive_micro": micro(adaptive_tot),
        "static_micro": micro(static_tot),
        "per_case": per_case,
    }


# ==========================================================================
# 4. Summary grounding rate
# ==========================================================================


def evaluate_grounding() -> dict:
    """
    Verify that every number in every generated summary traces to a claim.

    In deterministic mode this should be 100% by construction; the suite exists
    to catch regressions where a renderer starts formatting a value differently
    from the claim it came from.
    """
    suite = synthetic_data.benchmark_suite()
    results = []
    total_numbers = 0
    total_verified = 0

    for scenario in suite:
        from pipeline import run

        envelope = run(
            scenario["query"], rows=scenario["rows"], schema_meta=scenario["schema"],
            use_llm=False, use_llm_summary=False, enable_cache=False,
        )
        summary = envelope["summary"]
        v = summary["verification"]
        total_numbers += v.get("numbers_in_summary", 0)
        total_verified += v.get("verified", 0)
        results.append(
            {
                "scenario": scenario["name"],
                "claims": summary["claim_count"],
                "numbers": v.get("numbers_in_summary", 0),
                "verified": v.get("verified", 0),
                "passed": v.get("passed"),
                "unverified": v.get("unverified_values", []),
            }
        )

    return {
        "scenarios": len(results),
        "total_numbers": total_numbers,
        "total_verified": total_verified,
        "grounding_rate": round(total_verified / total_numbers, 4) if total_numbers else 0.0,
        "scenarios_fully_grounded": sum(1 for r in results if r["passed"]),
        "per_scenario": results,
    }


# ==========================================================================
# Reporting
# ==========================================================================


def print_intent(report: dict) -> None:
    print(f"\n{SEPARATOR}\n1. INTENT CLASSIFICATION ACCURACY  [{report['mode']}, split={report['split']}]\n{SEPARATOR}")
    print(f"  Cases                     : {report['n_cases']}")
    print(f"  Intent accuracy           : {report['intent_accuracy']:.1%}")
    print(f"  Macro F1                  : {report['macro_f1']:.4f}")
    print(f"  Prediction-flag accuracy  : {report['prediction_flag_accuracy']:.1%}")
    print(f"  Table-binding recall      : {report['table_binding_recall']:.1%}")
    if report["security_warning_recall"] is not None:
        print(f"  Security-warning recall   : {report['security_warning_recall']:.1%}")
    print(f"\n  {'Intent':<22}{'Support':>8}{'Prec':>8}{'Recall':>8}{'F1':>8}")
    for intent, m in sorted(report["per_class"].items()):
        print(f"  {intent:<22}{m['support']:>8}{m['precision']:>8.2f}"
              f"{m['recall']:>8.2f}{m['f1']:>8.2f}")
    if report["failures"]:
        print(f"\n  Misclassifications ({len(report['failures'])}):")
        for f in report["failures"]:
            print(f"    [{f['id']}] expected {f['expected']:<20} got {f['got']:<20} "
                  f"(conf {f['confidence']:.2f})")
            print(f"           \"{f['query'][:66]}\"")


def print_prediction(report: dict) -> None:
    print(f"\n{SEPARATOR}\n2. PREDICTION ACCURACY  (out-of-sample, {report['holdout_periods']}-period holdout)\n{SEPARATOR}")
    print(f"  Scenarios forecast        : {report['scenarios_forecast']} / {report['scenarios_total']} "
          f"({report['scenarios_skipped']} correctly skipped by the readiness gate)")
    print(f"  Rule-selection agreement  : {report['model_selection_agreement']:.1%}  "
          f"(rules vs generating process; benchmark guard overrode "
          f"{report['guard_overrides']} of {report['scenarios_forecast']})")
    print("  NOTE: superseded as the source of forecasting claims by the rolling-origin")
    print("        benchmark in evaluate_forecasting.py "
          "(see data_and_reports/forecast_benchmark.md).")

    sel = report["selected_model_mean"]
    if sel:
        print(f"\n  {'Strategy':<34}{'RMSE':>12}{'MAE':>12}{'meanMAPE':>11}{'medMAPE':>10}")
        print(f"  {'ADAPTIVE (dual-signal choice)':<34}{sel['rmse']:>12,.2f}"
              f"{sel['mae']:>12,.2f}{sel['mape']:>10.2f}%{sel['median_mape']:>9.2f}%")
        for model, m in report["fixed_baseline_means"].items():
            if m:
                print(f"  {'fixed: ' + model:<34}{m['rmse']:>12,.2f}"
                      f"{m['mae']:>12,.2f}{m['mape']:>10.2f}%{m['median_mape']:>9.2f}%")
        print(f"\n  Means cover the {sel['scenarios']} scenarios long enough to backtest.")
        print("  One unforecastable series dominates the mean MAPE, so the median is")
        print("  reported beside it rather than in place of it.")

    print(f"\n  {'Scenario':<26}{'n':>4} {'selected':<25}{'expected':<25}{'MAPE':>8}")
    for r in report["per_scenario"]:
        if r["skipped"]:
            print(f"  {r['scenario']:<26}{'-':>4}  SKIPPED: {r['verdict']}")
            continue
        mark = "OK " if r["selection_match"] else "DIFF"
        if r["selected"].get("ok"):
            mape = f"{r['selected']['mape']:>7.2f}%"
        else:
            # Too short to hold out 3 periods - report that, never a fake 0%.
            mape = f"{'n/a':>8}"
        print(f"  {r['scenario']:<26}{r['n_points']:>4} {r['selected_model']:<25}"
              f"{r['expected_model']:<25}{mape} {mark}")


def print_anomaly(report: dict) -> None:
    print(f"\n{SEPARATOR}\n3. ANOMALY DETECTION RATE  (adaptive vs static control)\n{SEPARATOR}")
    a, s = report["adaptive_micro"], report["static_micro"]
    print(f"  {'Method':<22}{'Prec':>8}{'Recall':>8}{'F1':>8}{'FPR':>8}{'TP':>6}{'FP':>6}{'FN':>6}")
    print(f"  {'ADAPTIVE':<22}{a['precision']:>8.2f}{a['recall']:>8.2f}{a['f1']:>8.2f}"
          f"{a['false_positive_rate']:>8.3f}{a['tp']:>6}{a['fp']:>6}{a['fn']:>6}")
    print(f"  {'STATIC (control)':<22}{s['precision']:>8.2f}{s['recall']:>8.2f}{s['f1']:>8.2f}"
          f"{s['false_positive_rate']:>8.3f}{s['tp']:>6}{s['fp']:>6}{s['fn']:>6}")
    delta = a["recall"] - s["recall"]
    print(f"\n  Recall improvement over static control: {delta:+.1%}")
    def cell(score, injected):
        # With nothing injected, recall is undefined; what matters is whether
        # the detector stayed quiet, so report the false-positive count instead.
        if not injected:
            return "no FP" if score["fp"] == 0 else f"{score['fp']} FALSE POS"
        return f"R={score['recall']:.2f} P={score['precision']:.2f}"

    print(f"\n  {'Case':<26}{'inj':>4}  {'adaptive':<20}{'static':<18}{'space':<10}")
    for c in report["per_case"]:
        injected = len(c["injected"])
        space = "residual" if c["adaptive"]["detrended"] else "raw level"
        print(f"  {c['case']:<26}{injected:>4}  "
              f"{cell(c['adaptive'], injected):<20}"
              f"{cell(c['static'], injected):<18}{space:<10}")


def print_grounding(report: dict) -> None:
    print(f"\n{SEPARATOR}\n4. SUMMARY GROUNDING RATE  (Stage 7 verification)\n{SEPARATOR}")
    print(f"  Scenarios                 : {report['scenarios']}")
    print(f"  Numbers in summaries      : {report['total_numbers']}")
    print(f"  Traceable to a claim      : {report['total_verified']}")
    print(f"  Grounding rate            : {report['grounding_rate']:.2%}")
    print(f"  Fully grounded summaries  : {report['scenarios_fully_grounded']} / {report['scenarios']}")
    bad = [r for r in report["per_scenario"] if not r["passed"]]
    if bad:
        print("\n  Ungrounded numbers detected:")
        for r in bad:
            print(f"    {r['scenario']}: {r['unverified']}")


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    use_llm = "--llm" in flags
    json_out = None
    for f in flags:
        if f.startswith("--json"):
            parts = f.split("=", 1)
            json_out = parts[1] if len(parts) > 1 else "evaluation_results.json"

    suite = args[0].lower() if args else "all"
    results = {}

    print(f"\n{SEPARATOR}")
    print("COMPONENT 4 - PRESENTATION & PREDICTION LAYER : EVALUATION")
    print("Wijethunge W M V (IT23256750) | Project J26-SE-347")
    print(SEPARATOR)

    if suite in ("all", "intent"):
        results["intent"] = evaluate_intent(use_llm=False, split="test")
        print_intent(results["intent"])
        if use_llm:
            results["intent_hybrid"] = evaluate_intent(use_llm=True, split="test")
            print_intent(results["intent_hybrid"])

    if suite in ("all", "prediction"):
        results["prediction"] = evaluate_prediction()
        print_prediction(results["prediction"])

    if suite in ("all", "anomaly"):
        results["anomaly"] = evaluate_anomaly()
        print_anomaly(results["anomaly"])

    if suite in ("all", "grounding"):
        results["grounding"] = evaluate_grounding()
        print_grounding(results["grounding"])

    print(f"\n{SEPARATOR}\n")

    if json_out:
        with open(json_out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=2, default=str)
        print(f"Full results written to {json_out}\n")


if __name__ == "__main__":
    main()
