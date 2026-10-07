"""
Independent intent benchmark on Spider dev questions (Stage 5).

Every earlier intent test set (intent_testset.json, the response-intent
corpora) was written by this component's author, so 100 % on them shows the
rules fit the author's phrasing. Spider's questions were written by other
people for a different purpose. Labels come from each question's gold SQL by
the fixed rules in benchmark_data/prepare_spider_intent.py, frozen before the
classifier was run (see that file).

Scored per split (DEV may be used to change the classifier, TEST is reported
once with the frozen code):

  shape accuracy      response intent is in the SQL-acceptable set
  intent accuracy     analytical intent is in the SQL-acceptable set
  TRUNCATION          SINGLE_ANSWER predicted for a question whose SQL returns
                      many rows (the shape is wrong)
  LIMIT_1_REQUESTED   ...and the analysis also asks Member 1 for LIMIT 1, so
                      the user silently loses rows - the costliest error. From
                      Stage 5 LIMIT 1 is only inferred where a superlative
                      orders the rows; otherwise guardrail G1 sees the extra
                      rows after execution and shows them as a table.
  ONE_AS_MANY         a list/chart predicted for a one-figure question: a
                      verbose answer, not a lost one
  PROSE               SHORT_SUMMARY or MIXED_SUMMARY predicted - Spider never
                      asks for prose
  intent UNKNOWN      the analyzer found no intent at all

Run:  python evaluate_spider_intent.py               (current code)
      python evaluate_spider_intent.py --baseline    (save as the pre-change baseline)
      python evaluate_spider_intent.py --llm N       (also the hybrid LLM path on N
                                                      TEST questions; sends them to the
                                                      provider in .env)
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

USE_LLM = "--llm" in sys.argv
if not USE_LLM:
    os.environ["LLM_PROVIDER"] = "none"

import profiler  # noqa: E402
import query_analyzer  # noqa: E402

profiler.VERBOSE = False

HERE = Path(__file__).resolve().parent
DATA = HERE / "benchmark_data" / "spider_dev_intent.json"
REPORT_MD = HERE / "data_and_reports" / "spider_intent_benchmark.md"
REPORT_JSON = HERE / "data_and_reports" / "spider_intent_benchmark_results.json"
BASELINE_JSON = HERE / "data_and_reports" / "spider_intent_benchmark_baseline_stage4.json"


def classify(question: str, use_llm: bool = False) -> tuple:
    a = query_analyzer.analyze(question, None, use_llm=use_llm)
    return a.response_intent, a.primary_intent, a.limit


def score(cases: list, use_llm: bool = False) -> dict:
    n = len(cases)
    shape_ok = intent_ok = 0
    errors = Counter()
    by_rule = defaultdict(lambda: [0, 0])
    confusion = defaultdict(Counter)
    detail = []
    for c in cases:
        shape, intent, limit = classify(c["question"], use_llm)
        s_ok, i_ok = shape in c["shape"], intent in c["intent"]
        shape_ok += s_ok
        intent_ok += i_ok
        by_rule[c["rule"]][0] += s_ok
        by_rule[c["rule"]][1] += 1
        confusion[c["rule"]][shape] += 1
        if shape == "SINGLE_ANSWER" and "SINGLE_ANSWER" not in c["shape"]:
            errors["TRUNCATION"] += 1
            if limit == 1:
                errors["LIMIT_1_REQUESTED"] += 1
        if c["rows"] == "ONE" and shape in ("TABLE_CONTENT", "CHART"):
            errors["ONE_AS_MANY"] += 1
        if shape in ("SHORT_SUMMARY", "MIXED_SUMMARY"):
            errors["PROSE"] += 1
        if intent == "UNKNOWN":
            errors["INTENT_UNKNOWN"] += 1
        if not (s_ok and i_ok):
            detail.append({"id": c["id"], "question": c["question"], "rule": c["rule"],
                           "shape": shape, "shape_ok": s_ok, "intent": intent, "intent_ok": i_ok,
                           "acceptable_shape": c["shape"], "acceptable_intent": c["intent"]})
    many = sum(1 for c in cases if "SINGLE_ANSWER" not in c["shape"])
    return {"cases": n, "shape_accuracy": shape_ok / n, "intent_accuracy": intent_ok / n,
            "shape_correct": shape_ok, "intent_correct": intent_ok,
            "truncation_rate": errors["TRUNCATION"] / many if many else None,
            "limit_1_rate": errors["LIMIT_1_REQUESTED"] / many if many else None,
            "multi_row_questions": many,
            "errors": dict(errors),
            "shape_by_rule": {r: {"correct": a, "cases": b} for r, (a, b) in sorted(by_rule.items())},
            "predicted_shape_by_rule": {r: dict(v) for r, v in confusion.items()},
            "failures": detail}


def _pct(v):
    return "-" if v is None else f"{100 * v:.1f}%"


def main() -> int:
    baseline_mode = "--baseline" in sys.argv
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cases = data["cases"]
    results = {}
    for split in ("DEV", "TEST"):
        results[split] = score([c for c in cases if c["split"] == split])
    if USE_LLM:
        n = int(sys.argv[sys.argv.index("--llm") + 1])
        test = [c for c in cases if c["split"] == "TEST"][:n]
        results["TEST_RULES_SAMPLE"] = score(test)
        results["TEST_HYBRID_SAMPLE"] = score(test, use_llm=True)
    if baseline_mode:
        BASELINE_JSON.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"Baseline written: {BASELINE_JSON.name}")
    base = (json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
            if BASELINE_JSON.exists() and not baseline_mode else None)

    md = ["# Independent intent benchmark — Spider dev (Stage 5)", "",
          "Generated by `evaluate_spider_intent.py`. Do not edit by hand. Questions written "
          "by Spider's annotators (Yu et al., 2018); labels derived from gold SQL by "
          "`benchmark_data/prepare_spider_intent.py`, frozen before the classifier ran. "
          "Split by database; DEV for changes, TEST reported once.", "",
          "| Split | Questions | "
          + ("Stage 4 shape | Stage 4 intent | Stage 4 multi-row as one (LIMIT 1 requested) | "
             if base else "")
          + "Shape accuracy | Intent accuracy | Multi-row read as one | "
            "...with LIMIT 1 requested (rows lost) | Other errors |",
          "|---|---|" + ("---|---|---|" if base else "") + "---|---|---|---|---|"]
    for split in ("DEV", "TEST"):
        r = results[split]
        row = f"| {split} | {r['cases']} | "
        if base:
            b = base[split]
            row += (f"{_pct(b['shape_accuracy'])} | {_pct(b['intent_accuracy'])} | "
                    f"{_pct(b['truncation_rate'])} ({_pct(b.get('limit_1_rate'))}) | ")
        md.append(row + f"**{_pct(r['shape_accuracy'])}** | **{_pct(r['intent_accuracy'])}** | "
                  f"{_pct(r['truncation_rate'])} ({r['errors'].get('TRUNCATION', 0)} of "
                  f"{r['multi_row_questions']}) | **{_pct(r['limit_1_rate'])}** | {r['errors']} |")
    md += ["", "## Response shape by SQL rule (TEST)", "",
           "| SQL rule | Questions | " + ("Stage 4 | " if base else "") + "Correct | Predicted shapes |",
           "|---|---|" + ("---|" if base else "") + "---|---|"]
    t = results["TEST"]
    for rule, v in t["shape_by_rule"].items():
        row = f"| {rule} | {v['cases']} | "
        if base:
            bv = base["TEST"]["shape_by_rule"].get(rule)
            row += f"{bv['correct']}/{bv['cases']} | " if bv else "- | "
        md.append(row + f"{v['correct']}/{v['cases']} | {t['predicted_shape_by_rule'][rule]} |")
    if USE_LLM:
        rs, hy = results["TEST_RULES_SAMPLE"], results["TEST_HYBRID_SAMPLE"]
        md += ["", f"## Rules vs hybrid LLM path (first {rs['cases']} TEST questions)", "",
               "| Path | Shape | Intent | Truncation |", "|---|---|---|---|",
               f"| Rules only | {_pct(rs['shape_accuracy'])} | {_pct(rs['intent_accuracy'])} | "
               f"{_pct(rs['truncation_rate'])} |",
               f"| Hybrid (rules + LLM) | {_pct(hy['shape_accuracy'])} | "
               f"{_pct(hy['intent_accuracy'])} | {_pct(hy['truncation_rate'])} |"]
    text = "\n".join(md) + "\n"
    print(text)
    if not baseline_mode:
        REPORT_MD.write_text(text, encoding="utf-8")
        REPORT_JSON.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
