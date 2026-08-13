"""
Benchmark harness for the response-intent classifier.

Reads the labelled corpus in `response_intent_dataset.csv`, runs the current
classifier over every input, and writes `response_intent_predictions.csv` -
one row per input recording what was expected, what the engine actually said,
and whether that was CORRECT or WRONG. That output file is the record of the
"existing state": re-run it after any lexicon change and diff the two to see
exactly which inputs moved.

The corpus deliberately contains inputs a real user would get wrong - typos,
one-word fragments, empty strings, keyboard mashes, prompt-injection attempts
and genuinely ambiguous phrasings - because a presentation layer has to return
*something* renderable for all of them. Accuracy is therefore reported broken
down by input quality, not just as a single headline number: a classifier that
scores 100% on well-formed input and collapses on typos is not shippable.

Usage:
    python evaluate_response_intent.py                 # rules only, offline
    python evaluate_response_intent.py --llm           # hybrid, needs a provider
    python evaluate_response_intent.py --errors-only   # print only the misses
"""

import argparse
import csv
import os
import sys
from collections import Counter, defaultdict

import query_analyzer
import response_intent
from schemas import ALL_RESPONSE_INTENTS, NOT_A_DATA_REQUEST

HERE = os.path.dirname(os.path.abspath(__file__))
# Corpora and generated reports live beside the code, not in it, so the module
# directory stays readable as the classifier itself.
DATA_DIR = os.path.join(HERE, "data_and_reports")
DATASET = os.path.join(DATA_DIR, "response_intent_dataset.csv")
PREDICTIONS = os.path.join(DATA_DIR, "response_intent_predictions.csv")

# Accuracy on well-formed input is the headline claim; the degraded-input
# figure is reported beside it so the two are never conflated.
TARGET_OVERALL = 0.85
TARGET_WELL_FORMED = 0.92

PREDICTION_FIELDS = [
    "id",
    "user_query",
    "input_quality",
    "expected_intent",
    "predicted_intent",
    "verdict",
    "confidence",
    "source",
    "evidence_grade",
    "runner_up",
    "margin",
    "expected_blocks",
    "predicted_blocks",
    "warnings",
    "rationale",
]


def load_dataset(path: str = DATASET) -> list:
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def predict(user_query: str, use_llm: bool = False):
    """
    Run the engine exactly as the pipeline would, minus the result set.

    The analytical analysis is computed first so Stage B has its prior - that
    is the real deployed path, and evaluating the lexicon in isolation would
    overstate the error rate on inputs that name no format at all.
    """
    analysis = query_analyzer.analyze(user_query, schema_meta=None, use_llm=use_llm)
    return response_intent.classify(user_query, analysis)


def score(rows: list, use_llm: bool = False) -> tuple:
    records = []
    for row in rows:
        expected = row["expected_intent"].strip()
        result = predict(row["user_query"], use_llm=use_llm)

        # Two kinds of gold label. NOT_A_DATA_REQUEST is scored against the
        # precondition, not the taxonomy: the question is whether the engine
        # recognised there was no data request, not which shape it fell back
        # to. Everything else is scored against the intent as before.
        if expected == NOT_A_DATA_REQUEST:
            predicted = (
                NOT_A_DATA_REQUEST if not result.is_data_request else result.intent
            )
        else:
            predicted = (
                NOT_A_DATA_REQUEST if not result.is_data_request else result.intent
            )
        correct = predicted == expected

        records.append(
            {
                "id": row["id"],
                "user_query": row["user_query"],
                "input_quality": row["input_quality"],
                "expected_intent": expected,
                "predicted_intent": predicted,
                "verdict": "CORRECT" if correct else "WRONG",
                "confidence": f"{result.confidence:.4f}",
                "source": result.source,
                "evidence_grade": (
                    "N/A" if not result.is_data_request else result.evidence_grade
                ),
                "runner_up": result.runner_up,
                "margin": f"{result.margin:.4f}",
                "expected_blocks": row["expected_blocks"],
                "predicted_blocks": "|".join(result.blocks),
                "warnings": ";".join(result.warnings),
                "rationale": result.rationale,
            }
        )
    return records


def write_predictions(records: list, path: str = PREDICTIONS) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PREDICTION_FIELDS)
        writer.writeheader()
        writer.writerows(records)


def per_class_metrics(records: list) -> dict:
    """Precision, recall and F1 per intent, computed one-vs-rest."""
    metrics = {}
    for label in ALL_RESPONSE_INTENTS + [NOT_A_DATA_REQUEST]:
        tp = sum(
            1 for r in records
            if r["predicted_intent"] == label and r["expected_intent"] == label
        )
        fp = sum(
            1 for r in records
            if r["predicted_intent"] == label and r["expected_intent"] != label
        )
        fn = sum(
            1 for r in records
            if r["predicted_intent"] != label and r["expected_intent"] == label
        )
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        metrics[label] = {
            "support": tp + fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return metrics


def confusion(records: list) -> dict:
    matrix = defaultdict(Counter)
    for r in records:
        matrix[r["expected_intent"]][r["predicted_intent"]] += 1
    return matrix


def _bar(value: float, width: int = 20) -> str:
    filled = int(round(value * width))
    return "#" * filled + "." * (width - filled)


def report(records: list, errors_only: bool = False) -> bool:
    total = len(records)
    correct = sum(1 for r in records if r["verdict"] == "CORRECT")
    accuracy = correct / total if total else 0.0

    by_quality = defaultdict(lambda: [0, 0])
    for r in records:
        bucket = by_quality[r["input_quality"]]
        bucket[1] += 1
        if r["verdict"] == "CORRECT":
            bucket[0] += 1

    well = by_quality.get("WELL_FORMED", [0, 0])
    well_acc = well[0] / well[1] if well[1] else 0.0
    degraded_hit = sum(v[0] for k, v in by_quality.items() if k != "WELL_FORMED")
    degraded_total = sum(v[1] for k, v in by_quality.items() if k != "WELL_FORMED")
    degraded_acc = degraded_hit / degraded_total if degraded_total else 0.0

    print()
    print("=" * 78)
    print("RESPONSE-INTENT CLASSIFIER  -  BENCHMARK")
    print("=" * 78)
    print(f"Corpus              : {total} labelled inputs")
    print(f"Overall accuracy    : {correct}/{total} = {accuracy:.1%}  [{_bar(accuracy)}]")
    print(f"Well-formed input   : {well[0]}/{well[1]} = {well_acc:.1%}  [{_bar(well_acc)}]")
    print(f"Degraded input      : {degraded_hit}/{degraded_total} = {degraded_acc:.1%}"
          f"  [{_bar(degraded_acc)}]")

    # ---- earned vs unearned -------------------------------------------
    # The default shape is TABLE_CONTENT, which is also the most common gold
    # label, so an input the lexicon understood nothing about can still land
    # on the right answer. Counting that beside a marker-driven hit overstates
    # what the engine can actually do, so the two are reported apart.
    data_requests = [r for r in records if r["evidence_grade"] != "N/A"]
    by_grade = defaultdict(lambda: [0, 0])
    for r in data_requests:
        bucket = by_grade[r["evidence_grade"]]
        bucket[1] += 1
        if r["verdict"] == "CORRECT":
            bucket[0] += 1

    fallback_hits = by_grade["FALLBACK"][0]
    earned = correct - fallback_hits
    earned_total = total - by_grade["FALLBACK"][1]
    earned_acc = earned / earned_total if earned_total else 0.0

    print()
    print("-" * 78)
    print("HOW THE CORRECT ANSWERS WERE REACHED")
    print("-" * 78)
    print(f"{'grade':<12}{'correct':>9}{'of':>5}{'total':>7}{'accuracy':>11}   meaning")
    meanings = {
        "DIRECT": "markers the user actually wrote decided it",
        "INFERRED": "lexicon inconclusive; analytical intent decided",
        "FALLBACK": "no evidence at all; the default was returned",
    }
    for grade in ("DIRECT", "INFERRED", "FALLBACK"):
        hit, count = by_grade[grade]
        if not count:
            continue
        rate = hit / count
        print(f"{grade:<12}{hit:>9}{'/':>5}{count:>7}{rate:>10.1%}   {meanings[grade]}")

    print()
    print(f"Headline accuracy      : {correct}/{total} = {accuracy:.1%}")
    print(f"Excluding fallback hits: {earned}/{earned_total} = {earned_acc:.1%}"
          f"   <- what the engine actually earned")
    if fallback_hits:
        print(f"  {fallback_hits} correct answer(s) came from the default with no "
              f"evidence behind them.")
        print("  The default is TABLE_CONTENT, which is also the most common gold")
        print("  label, so those are luck rather than skill and are excluded above.")

    print()
    print("-" * 78)
    print("PER-CLASS METRICS")
    print("-" * 78)
    print(f"{'intent':<16}{'support':>9}{'precision':>12}{'recall':>10}{'f1':>8}")
    metrics = per_class_metrics(records)
    for label, m in metrics.items():
        print(
            f"{label:<16}{m['support']:>9}{m['precision']:>12.1%}"
            f"{m['recall']:>10.1%}{m['f1']:>8.2f}"
        )
    macro_f1 = sum(m["f1"] for m in metrics.values()) / len(metrics)
    print(f"{'macro avg':<16}{total:>9}{'':>12}{'':>10}{macro_f1:>8.2f}")

    print()
    print("-" * 78)
    print("ACCURACY BY INPUT QUALITY")
    print("-" * 78)
    for quality in sorted(by_quality, key=lambda q: -by_quality[q][1]):
        hit, count = by_quality[quality]
        rate = hit / count if count else 0.0
        print(f"{quality:<16}{hit:>4}/{count:<4} {rate:>7.1%}  [{_bar(rate, 16)}]")

    print()
    print("-" * 78)
    print("CONFUSION MATRIX  (rows = expected, columns = predicted)")
    print("-" * 78)
    labels = ALL_RESPONSE_INTENTS + [NOT_A_DATA_REQUEST]
    short = {label: label[:6] for label in labels}
    print(f"{'':<16}" + "".join(f"{short[c]:>9}" for c in labels))
    matrix = confusion(records)
    for expected in labels:
        cells = "".join(
            f"{matrix[expected][pred] or '.':>9}" for pred in labels
        )
        print(f"{expected:<16}{cells}")

    misses = [r for r in records if r["verdict"] == "WRONG"]
    print()
    print("-" * 78)
    print(f"MISCLASSIFICATIONS  ({len(misses)})")
    print("-" * 78)
    if not misses:
        print("None.")
    for r in misses:
        query = r["user_query"] if r["user_query"].strip() else "(empty)"
        print(f"  {r['id']} [{r['input_quality']}] {query!r}")
        print(f"       expected {r['expected_intent']} -> got {r['predicted_intent']} "
              f"(conf {float(r['confidence']):.2f}, via {r['source']})")

    low_conf = [r for r in records if float(r["confidence"]) < 0.45]
    low_conf_wrong = [r for r in low_conf if r["verdict"] == "WRONG"]
    print()
    print("-" * 78)
    print("CALIBRATION")
    print("-" * 78)
    print(f"Flagged low confidence (<0.45) : {len(low_conf)}")
    print(f"  ... of which actually wrong  : {len(low_conf_wrong)}")
    if misses:
        caught = len(low_conf_wrong) / len(misses)
        print(f"  ... share of all errors that were flagged : {caught:.1%}")
    print("An error the engine flagged is a degraded answer; an error it was")
    print("confident about is a wrong answer. The second kind is what matters.")

    passed = accuracy >= TARGET_OVERALL and well_acc >= TARGET_WELL_FORMED
    print()
    print("=" * 78)
    print(
        f"GATE  overall >= {TARGET_OVERALL:.0%} and well-formed >= "
        f"{TARGET_WELL_FORMED:.0%}  ->  {'PASS' if passed else 'FAIL'}"
    )
    print("=" * 78)
    print(f"\nPer-input results written to {os.path.basename(PREDICTIONS)}")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", action="store_true",
                        help="enable the hybrid path (requires a configured provider)")
    parser.add_argument("--errors-only", action="store_true",
                        help="suppress the tables and print only misclassifications")
    parser.add_argument("--dataset", default=DATASET, help="path to the labelled CSV")
    args = parser.parse_args()

    rows = load_dataset(args.dataset)
    records = score(rows, use_llm=args.llm)

    # Derive the output name from the input so a hold-out run never overwrites
    # the development run's record of the existing state.
    global PREDICTIONS
    stem = os.path.splitext(os.path.basename(args.dataset))[0]
    PREDICTIONS = os.path.join(os.path.dirname(os.path.abspath(args.dataset)),
                               f"{stem}_predictions.csv")
    write_predictions(records, PREDICTIONS)
    passed = report(records, errors_only=args.errors_only)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
