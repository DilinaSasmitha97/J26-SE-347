"""
What-if scenario-parser benchmark (Stage 4).

Scores the two routes a scenario reaches whatif.simulate by, on the labelled
phrasings in whatif_testset.json:

  CLAUSE route    whatif.parse_scenario(text) - text typed into the simulate
                  box (pipeline `scenario_text`, POST /api/v4/simulate)
  QUESTION route  query_analyzer.analyze(question) -> whatif.scenario_from_analysis
                  - a what-if asked inside the question itself (QUESTION cases only)

A case is correct when the parse matches on every labelled field: valid, and for
valid cases direction, magnitude and apply mode. The error that matters most is
a WRONG SIMULATION - simulating a scenario that should have been refused, or
simulating the opposite direction - because the user then sees a confident,
wrong chart. A refusal of a valid scenario is a safer failure, reported apart.

DEV cases were used to design the Stage 4 parser; TEST cases are reported once
with the frozen code. All cases were written by the component author before the
parser change, so this measures coverage of known phrasing types, not of real
user language.

Run:  python evaluate_whatif.py               (current code)
      python evaluate_whatif.py --baseline    (save as the pre-change baseline)
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "none")

import profiler  # noqa: E402
import query_analyzer  # noqa: E402
import synthetic_data  # noqa: E402
import whatif  # noqa: E402

profiler.VERBOSE = False

HERE = Path(__file__).resolve().parent
TESTSET = HERE / "whatif_testset.json"
REPORT_MD = HERE / "data_and_reports" / "whatif_benchmark.md"
REPORT_JSON = HERE / "data_and_reports" / "whatif_benchmark_results.json"
BASELINE_JSON = HERE / "data_and_reports" / "whatif_benchmark_baseline_stage3.json"


def _parse_clause(case: dict):
    return whatif.parse_scenario(case["text"])


def _parse_question(case: dict, schema: dict):
    analysis = query_analyzer.analyze(case["text"], schema, use_llm=False)
    return whatif.scenario_from_analysis(analysis)


def score(case: dict, spec) -> dict:
    out = {"text": case["text"], "split": case["split"], "tag": case["tag"],
           "expected": {k: case.get(k) for k in ("valid", "direction", "magnitude", "mode")},
           "got": {"valid": spec.valid, "direction": spec.direction,
                   "magnitude": spec.magnitude_pct, "mode": spec.apply_mode,
                   "note": spec.parse_note}}
    if not case["valid"]:
        out["correct"] = not spec.valid
        out["error"] = "" if out["correct"] else "SIMULATED_INVALID"
    elif not spec.valid:
        out["correct"], out["error"] = False, "REFUSED_VALID"
    elif spec.direction != case["direction"]:
        out["correct"], out["error"] = False, "WRONG_DIRECTION"
    elif abs(spec.magnitude_pct - case["magnitude"]) > 1e-9:
        out["correct"], out["error"] = False, "WRONG_MAGNITUDE"
    elif spec.apply_mode != case["mode"]:
        out["correct"], out["error"] = False, "WRONG_MODE"
    else:
        out["correct"], out["error"] = True, ""
    return out


def summarise(scored: list) -> dict:
    n = len(scored)
    errors = {}
    for s in scored:
        if s["error"]:
            errors[s["error"]] = errors.get(s["error"], 0) + 1
    by_tag = {}
    for s in scored:
        t = by_tag.setdefault(s["tag"], [0, 0])
        t[0] += s["correct"]
        t[1] += 1
    wrong_sim = errors.get("SIMULATED_INVALID", 0) + errors.get("WRONG_DIRECTION", 0) \
        + errors.get("WRONG_MAGNITUDE", 0)
    return {"cases": n, "correct": sum(s["correct"] for s in scored),
            "accuracy": sum(s["correct"] for s in scored) / n if n else None,
            "wrong_simulations": wrong_sim, "errors": errors,
            "by_tag": {t: {"correct": c, "cases": k} for t, (c, k) in sorted(by_tag.items())}}


def run() -> dict:
    cases = json.loads(TESTSET.read_text(encoding="utf-8"))["cases"]
    schema = synthetic_data.benchmark_suite()[0]["schema"]
    results = {}
    for split in ("DEV", "TEST"):
        split_cases = [c for c in cases if c["split"] == split]
        clause = [score(c, _parse_clause(c)) for c in split_cases]
        question = [score(c, _parse_question(c, schema))
                    for c in split_cases if c["form"] == "QUESTION"]
        results[split] = {
            "CLAUSE": {**summarise(clause), "detail": clause},
            "QUESTION": {**summarise(question), "detail": question},
        }
    return results


def _pct(v):
    return "-" if v is None else f"{100 * v:.1f}%"


def main() -> int:
    baseline_mode = "--baseline" in sys.argv
    results = run()
    if baseline_mode:
        BASELINE_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Baseline written: {BASELINE_JSON.name}")
    baseline = (json.loads(BASELINE_JSON.read_text(encoding="utf-8"))
                if BASELINE_JSON.exists() and not baseline_mode else None)

    md = ["# What-if parser benchmark (Stage 4)", "",
          "Generated by `evaluate_whatif.py`. Do not edit by hand. Cases: "
          "`whatif_testset.json` (written before the Stage 4 change; DEV for design, "
          "TEST reported once). A *wrong simulation* is a refused-case simulated, or a "
          "wrong direction or magnitude simulated.", ""]
    head = "| Split | Route | Cases | " + ("Stage 3 correct | Stage 3 wrong sims | " if baseline else "") \
        + "Correct | Wrong simulations | Errors |"
    md += [head, "|" + "---|" * (head.count("|") - 1)]
    for split in ("DEV", "TEST"):
        for route in ("CLAUSE", "QUESTION"):
            r = results[split][route]
            row = f"| {split} | {route} | {r['cases']} | "
            if baseline:
                b = baseline[split][route]
                row += f"{b['correct']} ({_pct(b['accuracy'])}) | {b['wrong_simulations']} | "
            row += (f"**{r['correct']} ({_pct(r['accuracy'])})** | {r['wrong_simulations']} | "
                    f"{r['errors'] or '-'} |")
            md.append(row)
    md += ["", "## Correct by phrasing type (QUESTION route, DEV + TEST)", "",
           "| Type | " + ("Stage 3 | " if baseline else "") + "Now |",
           "|---|" + ("---|" if baseline else "") + "---|"]
    tags = sorted({t for s in ("DEV", "TEST") for t in results[s]["QUESTION"]["by_tag"]})

    def tag_cell(res, tag):
        c = k = 0
        for s in ("DEV", "TEST"):
            t = res[s]["QUESTION"]["by_tag"].get(tag)
            if t:
                c, k = c + t["correct"], k + t["cases"]
        return f"{c}/{k}"

    for tag in tags:
        md.append(f"| {tag} | " + (f"{tag_cell(baseline, tag)} | " if baseline else "")
                  + f"{tag_cell(results, tag)} |")
    md += ["", "## Remaining errors", ""]
    any_err = False
    for split in ("DEV", "TEST"):
        for route in ("CLAUSE", "QUESTION"):
            for d in results[split][route]["detail"]:
                if not d["correct"]:
                    any_err = True
                    g = d["got"]
                    md.append(f"- {split} {route} `{d['text']}`: {d['error']} "
                              f"(got valid={g['valid']} {g['direction']} {g['magnitude']} "
                              f"{g['mode']}; note: {g['note']})")
    if not any_err:
        md.append("- none")
    text = "\n".join(md) + "\n"
    print(text)
    if not baseline_mode:
        REPORT_MD.write_text(text, encoding="utf-8")
        REPORT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
