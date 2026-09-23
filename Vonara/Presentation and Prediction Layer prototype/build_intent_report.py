"""
Build the intent-classification dataset & weakness report.

Runs the response-intent classifier over all three corpora and writes one .xlsx
describing (a) every *kind* of natural-language query the component has been
tested against, and (b) every known weakness, including the ones that the
headline accuracy figure hides.

    python build_intent_report.py

Output: data_and_reports/intent_classification_report.xlsx

This is a companion to `build_review_workbook.py`, not a replacement. That file
answers "how did each input score"; this one answers "what kinds of question
exist, and where does the classifier break".
"""

import csv
import os
from collections import Counter, defaultdict
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import query_analyzer
import response_intent
from schemas import ALL_RESPONSE_INTENTS, NOT_A_DATA_REQUEST

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data_and_reports")
OUTPUT = os.path.join(DATA_DIR, "intent_classification_report.xlsx")

CORPORA = [
    ("Development", "response_intent_dataset.csv",
     "Tuned on. The rules were iterated against this corpus until it passed, so "
     "its score is a fit statistic and not a generalisation estimate."),
    ("Hold-out", "response_intent_holdout.csv",
     "Written after the rules were frozen, never tuned against. Same author, so "
     "it shares phrasing habits real users will not have."),
    ("Stress", "response_intent_stress.csv",
     "Deliberately hard: negation, multi-clause, idiom, jargon, non-native and "
     "conversational phrasing. This is where the prototype actually breaks."),
]

# ==========================================================================
# Styling
# ==========================================================================

NAVY = "1F3864"
BLUE = "2E5C8A"
GREY = "F2F2F2"
GREEN = "C6EFCE"
RED = "FFC7CE"
AMBER = "FFEB9C"

H1 = Font(bold=True, size=16, color="FFFFFF")
H2 = Font(bold=True, size=11, color="FFFFFF")
BOLD = Font(bold=True)
SMALL = Font(size=9, color="555555")
MONO = Font(name="Consolas", size=9)

FILL_H1 = PatternFill("solid", fgColor=NAVY)
FILL_H2 = PatternFill("solid", fgColor=BLUE)
FILL_ALT = PatternFill("solid", fgColor=GREY)
FILL_OK = PatternFill("solid", fgColor=GREEN)
FILL_BAD = PatternFill("solid", fgColor=RED)
FILL_WARN = PatternFill("solid", fgColor=AMBER)

WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")
CENTRE = Alignment(horizontal="center", vertical="top")

_thin = Side(style="thin", color="BFBFBF")
BORDER = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)


def title_row(ws, text, width):
    """Write a full-width banner across the top of a sheet."""
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=width)
    cell = ws.cell(row=1, column=1, value=text)
    cell.font = H1
    cell.fill = FILL_H1
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28


def header_row(ws, row, headers):
    for col, head in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=head)
        cell.font = H2
        cell.fill = FILL_H2
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = BORDER
    ws.row_dimensions[row].height = 26


def widths(ws, spec):
    for col, w in enumerate(spec, start=1):
        ws.column_dimensions[get_column_letter(col)].width = w


def body(ws, row, values, wrap_cols=(), alt=False):
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=value)
        cell.border = BORDER
        cell.alignment = WRAP if col in wrap_cols else TOP
        if alt:
            cell.fill = FILL_ALT
    return row + 1


# ==========================================================================
# Scoring
# ==========================================================================


def run_corpus(filename, corpus):
    """Classify every row of one corpus and return enriched records."""
    with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    records = []
    for row in rows:
        query = row["user_query"]
        analysis = query_analyzer.analyze(query, schema_meta=None, use_llm=False)
        result = response_intent.classify(query, analysis)

        expected = row["expected_intent"].strip()
        predicted = NOT_A_DATA_REQUEST if not result.is_data_request else result.intent

        records.append({
            "corpus": corpus,
            "id": row["id"],
            "user_query": query,
            "input_quality": row["input_quality"],
            "quality_note": row.get("quality_note", ""),
            "domain": row.get("domain", ""),
            "notes": row.get("notes", ""),
            "expected": expected,
            "predicted": predicted,
            "correct": predicted == expected,
            "confidence": round(float(result.confidence), 4),
            "source": result.source,
            "evidence_grade": result.evidence_grade,
            "runner_up": result.runner_up,
            "margin": round(float(result.margin), 4),
            "analytic_intent": analysis.primary_intent,
            "rationale": result.rationale,
        })
    return records


def rate(records):
    if not records:
        return 0.0
    return sum(1 for r in records if r["correct"]) / len(records)


# ==========================================================================
# The weakness inventory
# ==========================================================================
#
# Each entry is (area, severity, title, what happens, evidence, location,
# status). Severity is about consequence, not frequency: a weakness that
# silently reports a wrong number is worse than one that fails loudly.

WEAKNESSES = [
    ("Linguistics", "HIGH",
     "Negation is invisible to the classifier",
     "Marker scoring counts pattern hits with no notion of scope or polarity, so "
     "'give me a chart' and 'dont give me a chart' score identically. This is a "
     "limit of the representation, not a missing rule - no additional regex can "
     "fix it, because negation requires syntactic scope.",
     "'dont give me a chart just the totals' -> CHART (gold TABLE_CONTENT). "
     "'i dont need the full list only the top one' -> TABLE_CONTENT at 0.97 "
     "confidence (gold SINGLE_ANSWER).",
     "response_intent.py:_score_lexical (524)", "OPEN"),

    ("Linguistics", "HIGH",
     "Multi-clause requests collapse to a single modality",
     "R1 escalates to MIXED_SUMMARY only when two output formats are named "
     "explicitly. A second modality that is implied rather than named is missed, "
     "so compound questions lose half of what was asked for.",
     "'what is our MRR and how is it trending' -> SINGLE_ANSWER (gold "
     "MIXED_SUMMARY). 'pull the churn numbers then chart them by cohort' -> CHART "
     "(gold MIXED_SUMMARY).",
     "response_intent.py:_apply_precedence R1 (642)", "OPEN"),

    ("Linguistics", "MEDIUM",
     "Verbose and indirect phrasing dilutes the decisive marker",
     "Politeness padding and hedging add weak-tier hits that can outweigh the "
     "single decisive marker buried in the sentence.",
     "'can you kindly let me know the department that is spending most' -> "
     "TABLE_CONTENT (gold SINGLE_ANSWER).",
     "response_intent.py:RESPONSE_MARKERS (64)", "OPEN"),

    ("Linguistics", "MEDIUM",
     "Domain jargon and acronyms carry no marker weight",
     "Business abbreviations are the real signal in expert queries but appear in "
     "no lexicon tier, so classification falls back to a weak structural cue.",
     "'DSO by business unit please' -> TABLE_CONTENT (gold CHART); only the "
     "tier-1 'by <dimension>' pattern matched.",
     "response_intent.py:RESPONSE_MARKERS (64)", "OPEN"),

    ("Linguistics", "MEDIUM",
     "English-only by construction",
     "Markers, the repair vocabulary and the protected-token list are all "
     "English. Another language needs its own lexicon, not a translation.",
     "No non-English inputs are tested. The NON_NATIVE stress rows are English "
     "written by a non-native speaker, which is a different problem.",
     "response_intent.py (whole module)", "DOCUMENTED"),

    ("Measurement", "HIGH",
     "The confidence score is uncalibrated and does not track correctness",
     "'Confidence' is a hand-written arithmetic formula measuring separation "
     "between two marker scores. It was never calibrated against observed "
     "accuracy, yet it is used as a hard decision threshold in two places.",
     "Across 220 inputs: mean confidence 0.726 when WRONG vs 0.751 when CORRECT "
     "- effectively no separation. Highest confidence on a wrong answer is 0.97, "
     "the cap. Reliability is non-monotonic (0.6-0.7 bin scores 100%, 0.7-0.8 "
     "bin scores 88%).",
     "response_intent.py:_confidence (779)", "OPEN"),

    ("Measurement", "HIGH",
     "No baseline to compare against",
     "A 100% score is reported with nothing to anchor it. There is no "
     "majority-class, bag-of-words or LLM-only arm, so the contribution of the "
     "rule engine cannot be isolated.",
     "Majority class (TABLE_CONTENT) would score ~23% on the development "
     "corpus. No other arm has been run.",
     "evaluate_response_intent.py", "OPEN"),

    ("Measurement", "HIGH",
     "Single annotator, no inter-annotator agreement",
     "Response intent is a preference, not a verifiable fact - reasonable people "
     "disagree on whether 'sales by region' is a chart or a table. The gold "
     "labels were written by the same author as the rules, so accuracy partly "
     "measures self-consistency. No kappa is reported, so the achievable ceiling "
     "is unknown.",
     "All 220 labels are single-annotator. No agreement study exists.",
     "data_and_reports/*.csv", "OPEN"),

    ("Measurement", "MEDIUM",
     "Roughly 20 hand-tuned constants fitted to 125 examples",
     "Tier weights, the R1-R6 multipliers, the similarity threshold, the trust "
     "thresholds and the implicit limits were all set by hand against the "
     "development corpus. At that parameter-to-example ratio a perfect fit is "
     "close to guaranteed and carries little information.",
     "Weights 1-4; multipliers 1.5, 2.0, 3.5, 0.5, 0.4, 0.35, 0.3; thresholds "
     "0.75, 0.60, 0.55, 0.45; limits 5 and 1.",
     "response_intent.py (module constants)", "OPEN"),

    ("Measurement", "MEDIUM",
     "Stage C guardrails are never measured",
     "Every reported accuracy figure covers Stages A and B over text alone. "
     "Guardrails need real result sets, and no labelled (query, rows, correct "
     "shape) corpus exists - so a third of the architecture has unit tests but "
     "no accuracy number.",
     "test_response_intent.py covers guardrails functionally; the CSV benchmark "
     "cannot reach them.",
     "response_intent.py:apply_guardrails (938)", "DOCUMENTED"),

    ("Measurement", "MEDIUM",
     "Corpora are authored, not logged from users",
     "All 220 inputs were written by the project author. Real user phrasing, "
     "typo distribution and question mix will differ, so the field accuracy is "
     "unknown and will be lower.",
     "The stress corpus is the closest proxy and drops to 57.8%.",
     "data_and_reports/*.csv", "DOCUMENTED"),

    ("Hybrid engine", "HIGH",
     "The benchmark discards the LLM verdict entirely",
     "analyze() runs the full LLM arbitration and settles the answer, then the "
     "harness calls classify() a second time - which re-runs Stages A and B only "
     "and knows nothing about the model's vote. Every published figure is "
     "rules-only whether or not --llm was passed.",
     "evaluate_response_intent.py line 76 re-invokes response_intent.classify() "
     "on the analysis object rather than reading the settled verdict.",
     "evaluate_response_intent.py:76", "OPEN"),

    ("Hybrid engine", "HIGH",
     "The LLM override gate is effectively unreachable",
     "An override needs the rule confidence below 0.55, but the confidence "
     "formula floors at 0.30 and a single uncontested tier-1 marker already "
     "scores 0.78. Only near-ties can ever admit the model - and because the "
     "gate keys on marker separation rather than correctness, it locks the LLM "
     "out of exactly the negation cases it gets right.",
     "Only 7 of 125 development rows fall below 0.55, and 5 of those are "
     "greetings or gibberish. On 'i dont need the full list only the top one' "
     "the LLM answered correctly at 0.90 and was rejected because the wrong rule "
     "verdict scored 0.97.",
     "query_analyzer.py:1263-1268", "OPEN"),

    ("Hybrid engine", "MEDIUM",
     "Stage B pins confidence at exactly the override threshold",
     "The analytic-prior path sets confidence to max(confidence, 0.55) and the "
     "gate tests a strict less-than against 0.55, so the model can never "
     "override an analytic-prior verdict - precisely the case, where the user "
     "named no format at all, in which it is most likely to be right.",
     "0.55 < 0.55 is false, so the branch is unreachable for every "
     "ANALYTIC_PRIOR result.",
     "response_intent.py:888 with query_analyzer.py:1267", "OPEN"),

    ("Hybrid engine", "MEDIUM",
     "Agreement between the two engines is never recorded",
     "The arbitration block only runs when the verdicts differ, so a query where "
     "the lexicon and the model independently agree is indistinguishable in the "
     "output from one where no model ran. A concordance rate - a genuinely "
     "useful research statistic - is discarded on every request.",
     "'chart the summary of monthly revenue': rule CHART at 0.47, LLM CHART at "
     "0.90, reported as source=RULE confidence 0.47.",
     "query_analyzer.py:1263", "OPEN"),

    ("Hybrid engine", "MEDIUM",
     "The audit trail is not updated when the LLM wins",
     "An override replaces the intent, blocks, confidence and rationale but "
     "leaves evidence_grade, runner_up, margin, scores and matched_markers "
     "describing the rejected rule verdict. The evidence block then argues for a "
     "label the verdict no longer holds, and the benchmark stratifies accuracy "
     "by that stale grade.",
     "'show me the chart or maybe just the number': settled SINGLE_ANSWER via "
     "LLM, reported with evidence_grade DIRECT and runner_up SINGLE_ANSWER - the "
     "runner-up naming the winner.",
     "query_analyzer.py:1269-1280", "OPEN"),

    ("Taxonomy", "MEDIUM",
     "MIXED_SUMMARY is not disjoint from the other four classes",
     "It is the union of the others rather than a peer, so single-label "
     "classification is being forced onto classes that overlap. R5 damping and "
     "R1 escalation exist to patch that overlap with score arithmetic, and the "
     "boundary between 'a summary' and 'a report' stays a matter of degree.",
     "MIXED_SUMMARY carries the most precedence machinery of any class and "
     "accounts for 4 of the 19 stress failures.",
     "schemas.py:ResponseIntent, response_intent.py R1/R5", "OPEN"),

    ("Taxonomy", "LOW",
     "The fallback label is also the majority class",
     "A no-evidence fallback returns TABLE_CONTENT, which is the most common "
     "gold label, so fallbacks score correct by construction. This is already "
     "mitigated by evidence_grade, which separates DIRECT from FALLBACK hits, "
     "but the headline accuracy still benefits.",
     "TABLE_CONTENT is 29 of 125 development labels, the largest class.",
     "response_intent.py:DEFAULT_RESPONSE_INTENT", "MITIGATED"),

    ("Robustness", "MEDIUM",
     "The typo repair depends on a blacklist that grows by collision",
     "Repair rewrites near-miss tokens to format keywords, guarded by a manually "
     "maintained protected list. Every new domain word is a potential unguarded "
     "collision, and the list only grows after a collision is observed.",
     "'cost', 'last', 'cart', 'chat' and 26 others are protected because they "
     "collided with real keywords during development.",
     "response_intent.py:_PROTECTED_TOKENS (354)", "DOCUMENTED"),

    ("Robustness", "LOW",
     "is_data_request uses the markers as its own vocabulary",
     "The precondition accepts any input the classifier can score, which makes "
     "it partly circular: a well-formed non-data request that happens to use "
     "format words is accepted as a data request.",
     "'draw me a picture of a cat' is accepted as a data request with intent "
     "CHART, on the tier-3 'draw' marker.",
     "response_intent.py:is_data_request (466)", "OPEN"),

    ("Robustness", "LOW",
     "An LLM override can fire on a non-data request",
     "The early return for greetings and gibberish exits with confidence 0.10, "
     "and the arbitration gate does not check is_data_request - so a confident "
     "model vote can change the intent of an input the engine already decided "
     "was not a question about data.",
     "Reachable by construction; no corpus row currently triggers it because "
     "the model agrees on greetings.",
     "query_analyzer.py:1263 with response_intent.py:823", "OPEN"),

    ("Integration", "MEDIUM",
     "Schema binding is only tested against a three-table synthetic schema",
     "A production ERP has hundreds of tables with abbreviated, inconsistent "
     "names. Both fuzzy-binding accuracy and prompt token cost will degrade at "
     "that scale and neither has been measured.",
     "synthetic_data.SCHEMA_DDL defines expenses, sales and employees only.",
     "query_analyzer.py:parse_schema (239)", "OPEN"),
]

WEAKNESS_HEADERS = ["#", "Area", "Severity", "Weakness", "What happens",
                    "Evidence", "Where in the code", "Status"]


# ==========================================================================
# Sheets
# ==========================================================================


def sheet_overview(wb, records, by_corpus):
    ws = wb.create_sheet("1. Overview")
    widths(ws, [34, 26, 82])
    title_row(ws, "Intent Classification - Query Types & Weakness Report", 3)

    r = 3
    ws.cell(row=r, column=1, value="Generated").font = BOLD
    ws.cell(row=r, column=2, value=str(date.today()))
    r += 1
    ws.cell(row=r, column=1, value="Engine").font = BOLD
    ws.cell(row=r, column=2, value="Deterministic (rule) mode, no LLM")
    ws.cell(row=r, column=3,
            value="Run offline so the figures are reproducible without an API key.").alignment = WRAP
    r += 2

    ws.cell(row=r, column=1, value="WHAT THIS COMPONENT DOES").font = Font(bold=True, size=12)
    r += 1
    for label, text in [
        ("Question answered",
         "Given a natural-language data request, what SHAPE should the reply take?"),
        ("Taxonomy (closed)",
         "SINGLE_ANSWER | SHORT_SUMMARY | TABLE_CONTENT | CHART | MIXED_SUMMARY"),
        ("Stage A - lexical",
         "Weighted marker evidence over five families, then precedence rules R1-R6. "
         "Fully deterministic."),
        ("Stage B - analytic prior",
         "When lexical evidence is weak, the analytical intent (RANKING, TREND_ANALYSIS, ...) "
         "supplies the shape."),
        ("Stage C - guardrails",
         "After SQL runs, the verdict is re-checked against the real result set. Fires only "
         "on evidence from the data."),
        ("Hybrid arbitration",
         "An LLM vote may override the lexicon, but only when it is confident AND the rule "
         "verdict was weak. See the Weaknesses sheet - this gate rarely opens."),
    ]:
        ws.cell(row=r, column=1, value=label).font = BOLD
        c = ws.cell(row=r, column=2, value=text)
        c.alignment = WRAP
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=3)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="HEADLINE RESULTS").font = Font(bold=True, size=12)
    r += 1
    header_row(ws, r, ["Corpus", "Accuracy", "What the number means"])
    r += 1
    for corpus, _, note in CORPORA:
        recs = by_corpus[corpus]
        cell_vals = [f"{corpus} ({len(recs)})", f"{rate(recs):.1%}", note]
        for col, v in enumerate(cell_vals, start=1):
            c = ws.cell(row=r, column=col, value=v)
            c.border = BORDER
            c.alignment = WRAP if col == 3 else TOP
            if col == 2:
                c.fill = FILL_OK if rate(recs) >= 0.85 else FILL_BAD
                c.font = BOLD
        r += 1

    total = rate(records)
    ws.cell(row=r, column=1, value=f"All corpora ({len(records)})").font = BOLD
    c = ws.cell(row=r, column=2, value=f"{total:.1%}")
    c.font = BOLD
    c.fill = FILL_WARN
    ws.cell(row=r, column=3,
            value="Pooled figure. Weighted towards the two authored corpora, so it "
                  "overstates expected field accuracy.").alignment = WRAP
    r += 2

    ws.cell(row=r, column=1, value="HOW TO READ THIS REPORT").font = Font(bold=True, size=12)
    r += 1
    for text in [
        "The headline is not 100%. The development and hold-out corpora saturate; the stress "
        "corpus, which is the only one written to be hard, scores 57.8%. The gap between those "
        "numbers is the finding, not an embarrassment.",
        "Sheet 2 lists every KIND of query the component has been tested against, with the "
        "accuracy achieved on each kind. This is the map of what is and is not handled.",
        "Sheet 5 is the full labelled dataset - all 220 inputs with their verdicts.",
        "Sheet 6 is the weakness inventory, ranked by consequence, each entry carrying the "
        "evidence and the code location that produces it.",
    ]:
        c = ws.cell(row=r, column=1, value="- " + text)
        c.alignment = WRAP
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=3)
        ws.row_dimensions[r].height = 30
        r += 1

    ws.freeze_panes = "A3"


def sheet_query_types(wb, records):
    ws = wb.create_sheet("2. Query Types")
    widths(ws, [20, 9, 10, 11, 46, 52])
    title_row(ws, "Types of natural-language query the classifier has been tested on", 6)

    ws.cell(row=2, column=1,
            value="One row per input-quality category. 'Accuracy' is how often the engine "
                  "returned the labelled shape for that kind of phrasing.").alignment = WRAP
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=6)
    ws.row_dimensions[2].height = 28

    header_row(ws, 3, ["Query type", "Count", "Correct", "Accuracy",
                       "What this kind of query is", "Example (and what happened)"])

    groups = defaultdict(list)
    for rec in records:
        groups[rec["input_quality"]].append(rec)

    row = 4
    for quality in sorted(groups, key=lambda q: (rate(groups[q]), -len(groups[q]))):
        recs = groups[quality]
        acc = rate(recs)
        note = next((r["quality_note"] for r in recs if r["quality_note"]), "")

        # Prefer showing a failure - that is the informative case.
        pick = next((r for r in recs if not r["correct"]), recs[0])
        verdict = "OK" if pick["correct"] else f"MISS: expected {pick['expected']}, got {pick['predicted']}"
        example = f'"{pick["user_query"]}"  ->  {verdict}'

        vals = [quality, len(recs), sum(1 for r in recs if r["correct"]),
                f"{acc:.0%}", note, example]
        for col, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = BORDER
            c.alignment = WRAP if col in (5, 6) else (CENTRE if col in (2, 3, 4) else TOP)
            if col == 4:
                c.font = BOLD
                c.fill = FILL_OK if acc == 1.0 else (FILL_WARN if acc >= 0.5 else FILL_BAD)
        ws.row_dimensions[row].height = 30
        row += 1

    row += 1
    ws.cell(row=row, column=1,
            value="Reading: everything at 100% comes from the two authored corpora. Every "
                  "category below 100% is a stress category - these are the phenomena the "
                  "lexicon cannot currently represent.").alignment = WRAP
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    ws.row_dimensions[row].height = 30

    ws.freeze_panes = "A4"


def sheet_domains(wb, records):
    ws = wb.create_sheet("3. Query Domains")
    widths(ws, [22, 10, 10, 12, 60])
    title_row(ws, "Business domains covered by the test corpora", 5)
    header_row(ws, 2, ["Domain", "Count", "Correct", "Accuracy", "Example query"])

    groups = defaultdict(list)
    for rec in records:
        groups[rec["domain"] or "(unlabelled)"].append(rec)

    row = 3
    for domain in sorted(groups, key=lambda d: -len(groups[d])):
        recs = groups[domain]
        acc = rate(recs)
        pick = next((r for r in recs if not r["correct"]), recs[0])
        vals = [domain, len(recs), sum(1 for r in recs if r["correct"]),
                f"{acc:.0%}", pick["user_query"]]
        for col, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = BORDER
            c.alignment = WRAP if col == 5 else (CENTRE if col in (2, 3, 4) else TOP)
            if col == 4:
                c.fill = FILL_OK if acc == 1.0 else (FILL_WARN if acc >= 0.5 else FILL_BAD)
        row += 1

    row += 1
    ws.cell(row=row, column=1,
            value="Domain coverage is uneven - finance dominates. A domain with two or three "
                  "rows supports no accuracy claim of its own.").alignment = WRAP
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    ws.freeze_panes = "A3"


def sheet_intent_breakdown(wb, records):
    ws = wb.create_sheet("4. Per-Intent Metrics")
    widths(ws, [22, 10, 12, 11, 9, 9, 62])
    title_row(ws, "Per-intent precision, recall and F1 (one-vs-rest, all 220 inputs)", 7)
    header_row(ws, 2, ["Response intent", "Support", "Precision", "Recall", "F1",
                       "Missed", "Most common confusion"])

    labels = list(ALL_RESPONSE_INTENTS) + [NOT_A_DATA_REQUEST]
    row = 3
    f1s = []
    for label in labels:
        tp = sum(1 for r in records if r["expected"] == label and r["predicted"] == label)
        fp = sum(1 for r in records if r["expected"] != label and r["predicted"] == label)
        fn = sum(1 for r in records if r["expected"] == label and r["predicted"] != label)
        support = tp + fn
        if not support:
            continue
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / support
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        f1s.append(f1)

        confused = Counter(r["predicted"] for r in records
                           if r["expected"] == label and r["predicted"] != label)
        top = confused.most_common(1)
        confusion = f"{top[0][0]} ({top[0][1]}x)" if top else "-"

        vals = [label, support, f"{precision:.0%}", f"{recall:.0%}", f"{f1:.2f}", fn, confusion]
        for col, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = BORDER
            c.alignment = CENTRE if col in (2, 3, 4, 5, 6) else TOP
            if col == 5:
                c.fill = FILL_OK if f1 >= 0.9 else (FILL_WARN if f1 >= 0.75 else FILL_BAD)
        row += 1

    ws.cell(row=row, column=1, value="Macro-F1").font = BOLD
    c = ws.cell(row=row, column=5, value=f"{sum(f1s)/len(f1s):.2f}")
    c.font = BOLD
    c.fill = FILL_WARN
    ws.freeze_panes = "A3"


def sheet_dataset(wb, records):
    ws = wb.create_sheet("5. Full Dataset")
    widths(ws, [10, 13, 52, 15, 17, 17, 9, 11, 10, 13, 34])
    title_row(ws, "Complete labelled dataset - 220 natural-language queries", 11)
    header_row(ws, 2, ["ID", "Corpus", "User query", "Query type", "Expected",
                       "Predicted", "Verdict", "Confidence", "Source",
                       "Evidence grade", "Analytical intent"])

    row = 3
    for rec in records:
        vals = [rec["id"], rec["corpus"], rec["user_query"], rec["input_quality"],
                rec["expected"], rec["predicted"],
                "CORRECT" if rec["correct"] else "WRONG",
                rec["confidence"], rec["source"], rec["evidence_grade"],
                rec["analytic_intent"]]
        for col, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = BORDER
            c.alignment = WRAP if col == 3 else TOP
            if col == 7:
                c.fill = FILL_OK if rec["correct"] else FILL_BAD
                c.font = BOLD
        row += 1

    ws.auto_filter.ref = f"A2:K{row - 1}"
    ws.freeze_panes = "C3"


def sheet_failures(wb, records):
    ws = wb.create_sheet("6. Failures")
    failures = [r for r in records if not r["correct"]]

    widths(ws, [10, 48, 15, 17, 17, 10, 58])
    title_row(ws, f"Every misclassification - {len(failures)} of {len(records)} inputs", 7)
    ws.cell(row=2, column=1,
            value="All failures are in the stress corpus. Grouped by the phenomenon that "
                  "caused them, these are the four patterns in the Weaknesses sheet.").alignment = WRAP
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=7)
    header_row(ws, 3, ["ID", "User query", "Query type", "Expected", "Predicted",
                       "Confidence", "Why it failed"])

    row = 4
    for rec in sorted(failures, key=lambda r: (r["input_quality"], r["id"])):
        vals = [rec["id"], rec["user_query"], rec["input_quality"], rec["expected"],
                rec["predicted"], rec["confidence"], rec["notes"] or rec["quality_note"]]
        for col, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = BORDER
            c.alignment = WRAP if col in (2, 7) else TOP
            if col == 6 and float(rec["confidence"]) >= 0.8:
                c.fill = FILL_BAD
                c.font = BOLD
        ws.row_dimensions[row].height = 28
        row += 1

    row += 1
    high = [r for r in failures if float(r["confidence"]) >= 0.8]
    ws.cell(row=row, column=1,
            value=f"{len(high)} of {len(failures)} failures were returned with confidence >= 0.80. "
                  "A wrong answer the engine flagged as uncertain is a degraded answer; a wrong "
                  "answer it was confident about is the kind that reaches a user unchallenged.").alignment = WRAP
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=7)
    ws.row_dimensions[row].height = 30
    ws.freeze_panes = "A4"


def sheet_weaknesses(wb):
    ws = wb.create_sheet("7. Weaknesses")
    widths(ws, [5, 15, 11, 40, 62, 62, 34, 13])
    title_row(ws, "Known weaknesses of the intent-classification component", 8)
    ws.cell(row=2, column=1,
            value="Ranked by consequence, not frequency. Status OPEN = no mitigation in the "
                  "code today; DOCUMENTED = a known and accepted limit of this stage; "
                  "MITIGATED = partly addressed but still affects the headline figure.").alignment = WRAP
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=8)
    ws.row_dimensions[2].height = 28
    header_row(ws, 3, WEAKNESS_HEADERS)

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    row = 4
    for i, w in enumerate(sorted(WEAKNESSES, key=lambda x: order[x[1]]), start=1):
        area, severity, title, what, evidence, where, status = w
        vals = [i, area, severity, title, what, evidence, where, status]
        for col, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = BORDER
            c.alignment = WRAP if col in (4, 5, 6, 7) else TOP
            if col == 3:
                c.font = BOLD
                c.fill = {"HIGH": FILL_BAD, "MEDIUM": FILL_WARN, "LOW": FILL_ALT}[severity]
            if col == 7:
                c.font = MONO
        ws.row_dimensions[row].height = 62
        row += 1

    ws.auto_filter.ref = f"A3:H{row - 1}"
    ws.freeze_panes = "D4"


def sheet_calibration(wb, records):
    ws = wb.create_sheet("8. Confidence Check")
    widths(ws, [18, 10, 12, 14, 76])
    title_row(ws, "Is the confidence score meaningful? - empirical check", 5)
    ws.cell(row=2, column=1,
            value="Confidence is a hand-written formula: 0.30 + 0.45*margin + 0.25*saturation, "
                  "capped at 0.97. It measures separation between the top two marker scores. "
                  "A calibrated score would rise monotonically and match its own bin.").alignment = WRAP
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=5)
    ws.row_dimensions[2].height = 30
    header_row(ws, 3, ["Confidence bin", "Inputs", "Correct", "Actual accuracy", "Reading"])

    bins = defaultdict(list)
    for rec in records:
        b = min(int(float(rec["confidence"]) * 10) / 10, 0.9)
        bins[b].append(rec)

    row = 4
    for b in sorted(bins):
        recs = bins[b]
        acc = rate(recs)
        expected_mid = b + 0.05
        if acc >= expected_mid + 0.15:
            reading = "Under-confident - the engine was right far more often than it claimed"
        elif acc <= expected_mid - 0.15:
            reading = "Over-confident - the engine claimed more certainty than it earned"
        else:
            reading = "Roughly aligned with the claimed confidence"
        vals = [f"{b:.1f} - {b + 0.1:.1f}", len(recs), sum(1 for r in recs if r["correct"]),
                f"{acc:.0%}", reading]
        for col, v in enumerate(vals, start=1):
            c = ws.cell(row=row, column=col, value=v)
            c.border = BORDER
            c.alignment = WRAP if col == 5 else (CENTRE if col in (2, 3, 4) else TOP)
        row += 1

    row += 2
    ws.cell(row=row, column=1, value="THE KEY TEST - does confidence separate right from wrong?").font = Font(bold=True, size=12)
    row += 1
    wrong = [float(r["confidence"]) for r in records if not r["correct"]]
    right = [float(r["confidence"]) for r in records if r["correct"]]
    for label, value, note in [
        ("Mean confidence when WRONG", f"{sum(wrong)/len(wrong):.3f}", f"across {len(wrong)} failures"),
        ("Mean confidence when CORRECT", f"{sum(right)/len(right):.3f}", f"across {len(right)} successes"),
        ("Separation", f"{sum(right)/len(right) - sum(wrong)/len(wrong):.3f}",
         "A usable confidence score would show a large positive gap here. This one does not."),
        ("Highest confidence on a WRONG answer", f"{max(wrong):.2f}",
         "The formula's own ceiling is 0.97 - the engine was maximally confident and wrong."),
    ]:
        ws.cell(row=row, column=1, value=label).font = BOLD
        c = ws.cell(row=row, column=2, value=value)
        c.font = BOLD
        c.fill = FILL_BAD
        c.alignment = CENTRE
        n = ws.cell(row=row, column=3, value=note)
        n.alignment = WRAP
        ws.merge_cells(start_row=row, start_column=3, end_row=row, end_column=5)
        row += 1

    row += 1
    ws.cell(row=row, column=1,
            value="Consequence: this uncalibrated number is the sole gate deciding whether the "
                  "LLM may correct the rule engine (it may only do so when confidence < 0.55). "
                  "Gating on a signal that does not track correctness is why the model is "
                  "locked out of the negation cases it answers correctly.").alignment = WRAP
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=5)
    ws.row_dimensions[row].height = 44


def sheet_confusion(wb, records):
    ws = wb.create_sheet("9. Confusion Matrix")
    labels = list(ALL_RESPONSE_INTENTS) + [NOT_A_DATA_REQUEST]
    widths(ws, [22] + [17] * len(labels))
    title_row(ws, "Confusion matrix - rows are expected, columns are predicted", len(labels) + 1)

    header_row(ws, 2, ["Expected \\ Predicted"] + labels)
    row = 3
    for expected in labels:
        ws.cell(row=row, column=1, value=expected).font = BOLD
        ws.cell(row=row, column=1).border = BORDER
        for col, predicted in enumerate(labels, start=2):
            n = sum(1 for r in records
                    if r["expected"] == expected and r["predicted"] == predicted)
            c = ws.cell(row=row, column=col, value=n or "")
            c.border = BORDER
            c.alignment = CENTRE
            if n and expected == predicted:
                c.fill = FILL_OK
                c.font = BOLD
            elif n:
                c.fill = FILL_BAD
        row += 1

    row += 1
    ws.cell(row=row, column=1,
            value="Off-diagonal cells are the errors. Every one of them comes from the stress "
                  "corpus; the development and hold-out corpora produce a clean diagonal.").alignment = WRAP
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=len(labels) + 1)
    ws.freeze_panes = "B3"


# ==========================================================================
# Entry point
# ==========================================================================


def main():
    print("Classifying all corpora (deterministic mode)...")
    records = []
    by_corpus = {}
    for corpus, filename, _ in CORPORA:
        recs = run_corpus(filename, corpus)
        by_corpus[corpus] = recs
        records.extend(recs)
        print(f"  {corpus:<14} {sum(1 for r in recs if r['correct'])}/{len(recs)} "
              f"= {rate(recs):.1%}")

    wb = Workbook()
    wb.remove(wb.active)

    sheet_overview(wb, records, by_corpus)
    sheet_query_types(wb, records)
    sheet_domains(wb, records)
    sheet_intent_breakdown(wb, records)
    sheet_dataset(wb, records)
    sheet_failures(wb, records)
    sheet_weaknesses(wb)
    sheet_calibration(wb, records)
    sheet_confusion(wb, records)

    wb.save(OUTPUT)
    print(f"\nWrote {OUTPUT}")
    print(f"  {len(records)} inputs, {sum(1 for r in records if r['correct'])} correct "
          f"({rate(records):.1%})")
    print(f"  {len(WEAKNESSES)} weaknesses catalogued across "
          f"{len(set(w[0] for w in WEAKNESSES))} areas")


if __name__ == "__main__":
    main()
