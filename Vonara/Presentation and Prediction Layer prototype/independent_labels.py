"""
Independent labels for the readiness classifier (Stage 8).

All 90 cases in evaluate_readiness.py were labelled by the author of the rules,
so 90/90 shows the rules are implemented as intended, not that a person would
agree with them. This script produces a labelling kit for someone else (a
teammate or the supervisor) and scores their judgements against the classifier.

  python independent_labels.py build
      Writes data_and_reports/independent_labelling/:
        cases.csv         34 result sets (2 of each case type, new seeds), with
                          no expected answer
        labels.csv        the sheet the labeller fills in: one row per case
        INSTRUCTIONS.md   what to judge, in plain terms; no thresholds given

  python independent_labels.py score
      Reads the filled labels.csv and reports agreement between the person and
      the classifier (overall, per case type, Cohen's kappa), and where the
      person disagrees with the generator's intended label.

The cases are regenerated from a fixed seed, so the answer key never sits in
the folder the labeller works from.
"""

import csv
import json
import os
import random
import sys
from collections import Counter
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "none")

import evaluate_readiness as er  # noqa: E402
import prediction  # noqa: E402
import profiler  # noqa: E402
from result_profiler import profile_results  # noqa: E402

profiler.VERBOSE = False
HERE = Path(__file__).resolve().parent
KIT = HERE / "data_and_reports" / "independent_labelling"
SEED = 3030                     # different from the benchmark's, so the cases are new
PER_TYPE = 2
DECISIONS = ("FORECAST", "FORECAST_WITH_CAUTION", "NO_FORECAST")
TO_DECISION = {er.READY: "FORECAST", er.WARN: "FORECAST_WITH_CAUTION",
               er.NOT_READY: "NO_FORECAST"}

INSTRUCTIONS = """# Labelling forecast readiness

Thank you for helping. You are giving an **independent** judgement, so please
do not look at the code or the reports first.

## The situation

A business user asked a question, for example "show monthly expenses and
forecast the next 3 months", and the database returned the result set below.
Before showing a forecast, the system must decide whether this data can
support one.

## What to decide, for each case in `cases.csv`

Fill in the `your_decision` column of `labels.csv` with exactly one of:

| Decision | Meaning |
| --- | --- |
| `FORECAST` | The data is fine; show the forecast. |
| `FORECAST_WITH_CAUTION` | Show the forecast, but warn the user about something specific. |
| `NO_FORECAST` | Do not forecast; any forecast from this data would mislead. |

Use your own judgement about what a careful analyst would do. Add a few words
in `your_reason` (for example "too few points", "gaps", "looks like noise").

## Reading a case

Each row of `cases.csv` is one result set:

- `columns`: the columns returned.
- `rows`: the data, one row per line inside the cell, values separated by `;`.
  Empty values are shown as `NULL`.
- `note`: anything else the system knows about the result (for example that
  the database cut it at a row limit). Empty for most cases.

Plotting a case in Excel or Google Sheets often helps.

There are 34 cases; most take under a minute. Please work alone and do not
change `case_id`. When done, send `labels.csv` back.
"""


def _cases() -> list:
    master = random.Random(SEED)
    out = []
    for name, expected, code, build in er.CASES:
        if code == "MULTI_SERIES":
            # Grouped data is not refused, it is routed to per-category
            # forecasts; asking a person "forecast or not?" about it is unfair.
            continue
        for k in range(PER_TYPE):
            rng = random.Random(master.randint(1, 10**9))
            built = build(rng)
            rows, info = built if isinstance(built, tuple) else (built, None)
            out.append({"type": name, "expected": expected, "rows": rows, "info": info})
    order = random.Random(SEED + 1)
    order.shuffle(out)                       # case types are not grouped together
    for i, case in enumerate(out, start=1):
        case["case_id"] = f"C{i:02d}"
    return out


def _cell(v) -> str:
    return "NULL" if v is None else str(v)


def build() -> int:
    KIT.mkdir(parents=True, exist_ok=True)
    cases = _cases()
    with (KIT / "cases.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["case_id", "columns", "row_count", "rows", "note"])
        for c in cases:
            columns = list(c["rows"][0]) if c["rows"] else []
            lines = "\n".join("; ".join(_cell(r.get(col)) for col in columns) for r in c["rows"])
            note = ""
            if c["info"] and c["info"].get("truncated"):
                note = (f"The database cut this result at its row limit: only "
                        f"{c['info']['rows_received']} of {c['info']['row_count']} rows arrived.")
            writer.writerow([c["case_id"], ", ".join(columns), len(c["rows"]), lines, note])
    with (KIT / "labels.csv").open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["case_id", "your_decision", "your_reason"])
        for c in cases:
            writer.writerow([c["case_id"], "", ""])
    (KIT / "INSTRUCTIONS.md").write_text(INSTRUCTIONS, encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {KIT}")
    return 0


def _kappa(pairs: list) -> float:
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(ca[d] * cb[d] for d in DECISIONS) / (n * n)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def score() -> int:
    path = KIT / "labels.csv"
    with path.open(encoding="utf-8", newline="") as fh:
        labels = {r["case_id"]: (r["your_decision"].strip().upper(), r.get("your_reason", ""))
                  for r in csv.DictReader(fh)}
    labelled = {k: v for k, v in labels.items() if v[0] in DECISIONS}
    if not labelled:
        print(f"No decisions in {path} yet ({len(labels)} rows, all empty or invalid).")
        return 1
    rows, pairs_classifier, pairs_generator = [], [], []
    for c in _cases():
        if c["case_id"] not in labelled:
            continue
        person, reason = labelled[c["case_id"]]
        report = prediction.assess_readiness(profile_results(c["rows"]), c["rows"],
                                             input_info=c["info"])
        system = TO_DECISION[report.decision]
        intended = TO_DECISION[c["expected"]]
        pairs_classifier.append((person, system))
        pairs_generator.append((person, intended))
        rows.append({"case_id": c["case_id"], "type": c["type"], "person": person,
                     "classifier": system, "intended": intended, "person_reason": reason,
                     "classifier_reasons": report.reason_codes})
    n = len(rows)
    agree = sum(r["person"] == r["classifier"] for r in rows)
    agree_binary = sum((r["person"] == "NO_FORECAST") == (r["classifier"] == "NO_FORECAST")
                       for r in rows)
    result = {"labelled": n, "of": len(labels),
              "agreement_three_level": agree / n,
              "agreement_forecast_or_not": agree_binary / n,
              "cohens_kappa": _kappa(pairs_classifier),
              "person_vs_intended_label": sum(a == b for a, b in pairs_generator) / n,
              "disagreements": [r for r in rows if r["person"] != r["classifier"]]}
    (KIT / "agreement_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Labelled {n} of {len(labels)} cases.")
    print(f"Person vs classifier: {agree}/{n} three-level ({result['agreement_three_level']:.0%}), "
          f"{agree_binary}/{n} forecast-or-not, Cohen's kappa {result['cohens_kappa']:.2f}")
    print(f"Person vs the generator's intended label: {result['person_vs_intended_label']:.0%}")
    for r in result["disagreements"]:
        print(f"  {r['case_id']} ({r['type']}): person {r['person']}, classifier "
              f"{r['classifier']} {r['classifier_reasons']} - \"{r['person_reason']}\"")
    print(f"Written: {KIT / 'agreement_results.json'}")
    return 0


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "build":
        sys.exit(build())
    if command == "score":
        sys.exit(score())
    print("usage: python independent_labels.py build | score")
    sys.exit(2)
