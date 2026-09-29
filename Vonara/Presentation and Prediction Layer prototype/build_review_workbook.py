"""
Build the review workbook for the response-intent classifier.

Runs the classifier over all three corpora and writes one .xlsx with the
inputs, what the engine said, whether that was right, and - where it was
wrong - why. The failures are the point of the file, not an embarrassment to
be hidden: a reviewer needs to see where a stage-1 prototype breaks.

    python build_review_workbook.py

Output: response_intent_review.xlsx
"""

import csv
import os
from collections import Counter, defaultdict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import query_analyzer
import response_intent
from schemas import ALL_RESPONSE_INTENTS, NOT_A_DATA_REQUEST

HERE = os.path.dirname(os.path.abspath(__file__))
# Corpora and generated reports live beside the code, not in it, so the module
# directory stays readable as the classifier itself.
DATA_DIR = os.path.join(HERE, "data_and_reports")
OUTPUT = os.path.join(DATA_DIR, "response_intent_review.xlsx")

CORPORA = [
    ("Development", "response_intent_dataset.csv",
     "Tuned on. The rules were iterated against this until it passed, so its "
     "score is a fit statistic, not a generalisation estimate."),
    ("Hold-out", "response_intent_holdout.csv",
     "Written after the rules were frozen and never tuned against. Shares the "
     "same author's phrasing habits, so it is a weak generalisation test."),
    ("Stress", "response_intent_stress.csv",
     "Deliberately hard: negation, multi-clause questions, idioms, jargon, "
     "non-native phrasing, conversational fragments. Never tuned against. "
     "This is the sheet that shows where the prototype actually breaks."),
]

# --------------------------------------------------------------------------
# Diagnoses for the failures, written from the evidence trail in each result.
# Keyed by input id; grouped so the pattern is visible rather than 19 one-offs.
# --------------------------------------------------------------------------

FAILURE_CLASS = {
    "ST03": "Negation blindness",
    "ST04": "Negation blindness",
    "ST06": "Multi-clause question",
    "ST07": "Multi-clause question",
    "ST25": "Multi-clause question",
    "ST45": "Multi-clause question",
    "ST41": "Conjunction not recognised",
    "ST01": "Superlative expressed without a superlative word",
    "ST22": "Superlative expressed without a superlative word",
    "ST33": "Idiom not in lexicon",
    "ST35": "Idiom not in lexicon",
    "ST34": "Open interpretation request",
    "ST36": "Open interpretation request",
    "ST16": "Polar comparison question",
    "ST17": "Polar comparison question",
    "ST08": "Domain acronym unknown",
    "ST28": "Verb not in lexicon",
    "ST18": "Breakdown with no axis",
    "ST42": "Single-word exhaustive request",
}

DIAGNOSIS = {
    "ST03": "'chart' scores 4 for CHART regardless of the 'dont' in front of it. "
            "The engine has no negation handling at all - it matches markers, "
            "not the polarity of the clause they sit in.",
    "ST04": "Same defect, opposite direction: 'full list' fires the TABLE markers "
            "and 'dont need' is invisible, so the asserted 'only the top one' loses.",
    "ST06": "Two questions joined: a scalar ('what is our MRR') and a trend "
            "('how is it trending'). R1 only escalates to MIXED when two output "
            "FORMATS are named. Neither clause names a format, so the first wins.",
    "ST07": "'pull the numbers THEN chart them' is sequential, not conjunctive. "
            "'then' is not in the conjunction list, so R1 never fires and the "
            "decisive 'chart' marker takes it alone.",
    "ST25": "A count question and an entity superlative joined by 'and'. Both are "
            "scalar-shaped, so neither triggers the multi-format rule.",
    "ST45": "'forecast X and explain Y' - 'explain' is a decisive SUMMARY marker "
            "and 'forecast' names no format, so R1 sees only one modality.",
    "ST41": "'but' is not in the conjunction list that R1 tests. 'summarise BUT "
            "keep the table too' names two formats and should have escalated.",
    "ST01": "The superlative is paraphrased - 'spending more than the others' "
            "contains no superlative token. With no lexical evidence the analytic "
            "prior decides, and RANKING maps to a table.",
    "ST22": "A long request whose decisive word is 'understand why'. The SUMMARY "
            "markers fire; nothing signals that a board briefing wants the "
            "supporting table and chart too.",
    "ST33": "'headline number' is a scalar idiom that is not in the lexicon. "
            "'number' alone is a weak TABLE cue, so it tips the wrong way.",
    "ST35": "'run the numbers' reads as a table request to a human and as a "
            "CHART cue to the engine, via the weak 'numbers' probe.",
    "ST34": "No format marker at all. Falls to the analytic prior, which returns "
            "the safe default (rows) rather than the interpretation asked for.",
    "ST36": "'anything I should worry about' is a risk-framing paraphrase; the "
            "SUMMARY tier-2 list covers 'anything unusual' but not this.",
    "ST16": "A polar question ('up or down') wants a one-line verbal answer. The "
            "engine sees a temporal comparison and reaches for a chart.",
    "ST17": "Same pattern. 'are we doing better' is a judgement request, but the "
            "how-doing pattern needs the 'doing/going/performing' verb form.",
    "ST08": "'DSO' is unknown, so only the 'by business unit' grouping registers - "
            "and that is a weak tier-1 cue, below the trust threshold.",
    "ST28": "'tabulate' is not in the TABLE lexicon. The 'monthly totals' cue "
            "then reads as a temporal series.",
    "ST18": "'break down' is treated as a CHART probe, which is right when a "
            "dimension follows ('break down BY region') and wrong when none does.",
    "ST42": "The MIXED tier-4 marker requires 'everything about/on/you have'. "
            "Bare 'everything' has no anchor, so it falls to the default.",
}

# --------------------------------------------------------------------------
# Styling
# --------------------------------------------------------------------------

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
TITLE_FONT = Font(bold=True, size=14, color="1F3864")
SUB_FONT = Font(bold=True, size=11, color="1F3864")
WRONG_FILL = PatternFill("solid", fgColor="FCE4E4")
CORRECT_FILL = PatternFill("solid", fgColor="EAF5EA")
WARN_FILL = PatternFill("solid", fgColor="FFF4E0")
THIN = Side(style="thin", color="D0D0D0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")


def style_header(ws, row: int, ncols: int) -> None:
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        cell.border = BORDER


def set_widths(ws, widths: dict) -> None:
    for col, width in widths.items():
        ws.column_dimensions[col].width = width


def write_paragraph(ws, row: int, text: str, bold=False, size=11, color="000000"):
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = Font(bold=bold, size=size, color=color)
    cell.alignment = Alignment(wrap_text=True, vertical="top")
    return row + 1


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def run_corpus(filename: str, corpus: str) -> list:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    records = []
    for row in rows:
        query = row["user_query"]
        analysis = query_analyzer.analyze(query, schema_meta=None, use_llm=False)
        result = response_intent.classify(query, analysis)
        expected = row["expected_intent"].strip()
        predicted = (NOT_A_DATA_REQUEST if not result.is_data_request
                     else result.intent)
        correct = predicted == expected

        records.append({
            "corpus": corpus,
            "id": row["id"],
            "query": query if query.strip() else "(empty input)",
            "quality": row["input_quality"],
            "quality_note": row.get("quality_note", ""),
            "domain": row.get("domain", ""),
            "expected": expected,
            "predicted": predicted,
            "verdict": "CORRECT" if correct else "WRONG",
            "confidence": round(result.confidence, 3),
            "source": result.source,
            "blocks": " + ".join(result.blocks),
            "focus": result.answer_focus,
            "grade": ("N/A" if not result.is_data_request
                      else result.evidence_grade),
            "runner_up": result.runner_up,
            "margin": round(result.margin, 3),
            "warnings": "; ".join(result.warnings),
            "rationale": result.rationale,
        })
    return records


# --------------------------------------------------------------------------
# Sheets
# --------------------------------------------------------------------------


def sheet_overview(wb, records: list) -> None:
    ws = wb.create_sheet("1. Overview")
    set_widths(ws, {"A": 108})
    r = 1
    r = write_paragraph(ws, r, "Response-Intent Classifier - Review Pack", True, 16, "1F3864")
    r = write_paragraph(ws, r, "Component 4, Part 5 - Presentation & Prediction Layer   |   "
                               "Wijethunge W M V (IT23256750)   |   J26-SE-347")
    r += 1

    r = write_paragraph(ws, r, "WHAT THIS COMPONENT DOES", True, 12, "1F3864")
    r = write_paragraph(ws, r,
        "Part 1 of the layer already classifies WHAT a question is about "
        "(TREND_ANALYSIS, RANKING, ...). This component answers a different "
        "question: what SHAPE should the reply take. The two are independent - "
        "\"what was our highest invoice\" (RANKING) and \"how many customers\" "
        "(KPI_SINGLE_VALUE) are different analytical intents that both want one "
        "number, while \"revenue by month\" and \"revenue by region\" are "
        "different analytical intents that both want a chart.")
    r += 1

    r = write_paragraph(ws, r, "THE FIVE RESPONSE INTENTS", True, 12, "1F3864")
    for line in [
        "SINGLE_ANSWER   one value or one record      -> ANSWER block",
        "SHORT_SUMMARY   a few sentences of prose     -> SUMMARY block",
        "TABLE_CONTENT   the dataset itself, as rows  -> TABLE block",
        "CHART           a visual reading of the data -> CHART block",
        "MIXED_SUMMARY   a full report                -> SUMMARY + TABLE + CHART",
    ]:
        cell = ws.cell(row=r, column=1, value="    " + line)
        cell.font = Font(name="Consolas", size=10)
        r += 1
    r = write_paragraph(ws, r,
        "The set is closed and has no UNKNOWN member: a presentation layer must "
        "always render something, so low confidence is carried in the score and "
        "a warning, never in an unrenderable label.")
    r += 1

    r = write_paragraph(ws, r, "HEADLINE RESULTS", True, 12, "1F3864")
    header_row = r
    ws.cell(row=r, column=1, value="Corpus")
    ws.cell(row=r, column=2, value="Inputs")
    ws.cell(row=r, column=3, value="Correct")
    ws.cell(row=r, column=4, value="Accuracy")
    ws.cell(row=r, column=5, value="What it measures")
    style_header(ws, r, 5)
    r += 1

    for name, _, note in CORPORA:
        subset = [x for x in records if x["corpus"] == name]
        hits = sum(1 for x in subset if x["verdict"] == "CORRECT")
        ws.cell(row=r, column=1, value=name).border = BORDER
        ws.cell(row=r, column=2, value=len(subset)).border = BORDER
        ws.cell(row=r, column=3, value=hits).border = BORDER
        acc = ws.cell(row=r, column=4, value=hits / len(subset) if subset else 0)
        acc.number_format = "0.0%"
        acc.border = BORDER
        note_cell = ws.cell(row=r, column=5, value=note)
        note_cell.alignment = WRAP
        note_cell.border = BORDER
        ws.row_dimensions[r].height = 46
        r += 1

    total = len(records)
    hits = sum(1 for x in records if x["verdict"] == "CORRECT")
    ws.cell(row=r, column=1, value="ALL").font = Font(bold=True)
    ws.cell(row=r, column=2, value=total).font = Font(bold=True)
    ws.cell(row=r, column=3, value=hits).font = Font(bold=True)
    c = ws.cell(row=r, column=4, value=hits / total)
    c.number_format = "0.0%"
    c.font = Font(bold=True)
    r += 2

    set_widths(ws, {"A": 42, "B": 9, "C": 9, "D": 11, "E": 62})

    r = write_paragraph(ws, r, "HOW THE CORRECT ANSWERS WERE REACHED", True, 12, "1F3864")
    r = write_paragraph(ws, r,
        "Not every correct answer is the same kind of success. The default "
        "shape is TABLE_CONTENT, which is also the most common gold label, so "
        "an input the engine understood nothing about can still land on the "
        "right answer. Those are counted separately here.")
    ws.cell(row=r, column=1, value="Evidence grade")
    ws.cell(row=r, column=2, value="Inputs")
    ws.cell(row=r, column=3, value="Correct")
    ws.cell(row=r, column=4, value="Accuracy")
    ws.cell(row=r, column=5, value="What it means")
    style_header(ws, r, 5)
    r += 1
    meanings = {
        "DIRECT": "Markers the user actually wrote decided it. Earned.",
        "INFERRED": "Lexicon inconclusive; the analytical intent decided it.",
        "FALLBACK": "No evidence at all - the default was returned. Luck, not skill.",
        "N/A": "Not a data request; scored against the precheck instead.",
    }
    for grade in ("DIRECT", "INFERRED", "FALLBACK", "N/A"):
        subset = [x for x in records if x["grade"] == grade]
        if not subset:
            continue
        hits = sum(1 for x in subset if x["verdict"] == "CORRECT")
        ws.cell(row=r, column=1, value=grade).border = BORDER
        ws.cell(row=r, column=2, value=len(subset)).border = BORDER
        ws.cell(row=r, column=3, value=hits).border = BORDER
        acc = ws.cell(row=r, column=4, value=hits / len(subset))
        acc.number_format = "0.0%"
        acc.border = BORDER
        note = ws.cell(row=r, column=5, value=meanings[grade])
        note.alignment = WRAP
        note.border = BORDER
        if grade == "FALLBACK":
            for c in range(1, 6):
                ws.cell(row=r, column=c).fill = WARN_FILL
        r += 1
    r += 1

    fallback = [x for x in records if x["grade"] == "FALLBACK"]
    fallback_hits = sum(1 for x in fallback if x["verdict"] == "CORRECT")
    earned_total = len(records) - len(fallback)
    earned_hits = hits_all = sum(1 for x in records if x["verdict"] == "CORRECT")
    earned_hits = hits_all - fallback_hits
    r = write_paragraph(ws, r,
        f"Headline accuracy is {hits_all}/{len(records)} = "
        f"{hits_all/len(records):.1%}. Excluding the {len(fallback)} inputs "
        f"decided with no evidence, the engine earned "
        f"{earned_hits}/{earned_total} = {earned_hits/earned_total:.1%}. "
        "The second figure is the defensible one.", True, 11, "C00000")
    r += 1

    r = write_paragraph(ws, r, "HOW TO READ THESE NUMBERS", True, 12, "C00000")
    r = write_paragraph(ws, r,
        "The Development score is NOT evidence of accuracy. The rules were "
        "iterated against that corpus until it passed - it started at 80.8% and "
        "the errors along the way are what produced the current rule set. A "
        "model scoring 100% on its own training data has demonstrated "
        "consistency, not skill.")
    r = write_paragraph(ws, r,
        "The Hold-out corpus was written after the rules were frozen, but by the "
        "same author, so it shares phrasing habits that real users will not. It "
        "is a weak generalisation test, not a strong one.")
    r = write_paragraph(ws, r,
        "The Stress corpus is the honest signal. It was built specifically to "
        "attack the design - negation, two questions in one sentence, idioms, "
        "domain acronyms, non-native phrasing - and was never tuned against. "
        "Its score is materially lower, and sheet 4 lists every failure with the "
        "reason. That gap between corpora is the real finding in this pack.")
    r += 1
    r = write_paragraph(ws, r,
        "No corpus here is real user data. None exists yet at this stage of the "
        "project. Replacing the hold-out set with logged queries and "
        "re-baselining is the first task once the system is in front of users, "
        "and the numbers will fall when that happens.")
    r += 1
    r = write_paragraph(ws, r,
        "A note on a correction made during review: an earlier version of this "
        "pack labelled non-data inputs - \"hello\", \"qwertyuiop\", empty "
        "strings - with the fallback intent. The engine returned the fallback, "
        "so they scored CORRECT by construction and tested nothing. They are "
        "now labelled NOT_A_DATA_REQUEST and scored against a real precheck, "
        "which is why they can now be got wrong.")
    r += 1

    r = write_paragraph(ws, r, "SHEETS IN THIS WORKBOOK", True, 12, "1F3864")
    for line in [
        "2. All Results        every input, what the engine said, and why",
        "3. Failures           only the wrong answers, each with a diagnosis",
        "4. Failure Patterns   the failures grouped into root causes",
        "5. Metrics            precision / recall / F1 per intent, per corpus",
        "6. Confusion Matrix   what gets mistaken for what",
        "7. Worked Example     one question traced through the whole pipeline",
    ]:
        cell = ws.cell(row=r, column=1, value="    " + line)
        cell.font = Font(name="Consolas", size=10)
        r += 1

    ws.sheet_view.showGridLines = False


def sheet_all_results(wb, records: list) -> None:
    ws = wb.create_sheet("2. All Results")
    headers = ["Corpus", "ID", "User Input", "Input Quality", "Expected",
               "Predicted", "Verdict", "Evidence Grade", "Confidence",
               "Decided By", "Blocks Emitted", "Runner-Up", "Margin",
               "Warnings", "Why"]
    ws.append(headers)
    style_header(ws, 1, len(headers))

    for rec in records:
        ws.append([
            rec["corpus"], rec["id"], rec["query"], rec["quality"],
            rec["expected"], rec["predicted"], rec["verdict"], rec["grade"],
            rec["confidence"], rec["source"], rec["blocks"], rec["runner_up"],
            rec["margin"], rec["warnings"], rec["rationale"],
        ])
        row = ws.max_row
        fill = CORRECT_FILL if rec["verdict"] == "CORRECT" else WRONG_FILL
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=row, column=c)
            cell.border = BORDER
            cell.alignment = TOP
            if c in (7,):
                cell.fill = fill
                cell.font = Font(bold=rec["verdict"] == "WRONG",
                                 color="C00000" if rec["verdict"] == "WRONG" else "1E6B1E")
        ws.cell(row=row, column=3).alignment = WRAP
        ws.cell(row=row, column=15).alignment = WRAP
        ws.cell(row=row, column=9).number_format = "0.00"
        ws.cell(row=row, column=13).number_format = "0.00"
        if rec["grade"] == "FALLBACK":
            ws.cell(row=row, column=8).fill = WARN_FILL

    set_widths(ws, {"A": 13, "B": 8, "C": 52, "D": 15, "E": 19, "F": 19,
                    "G": 10, "H": 14, "I": 11, "J": 15, "K": 24, "L": 15,
                    "M": 8, "N": 30, "O": 60})
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{ws.max_row}"


def sheet_failures(wb, records: list) -> None:
    ws = wb.create_sheet("3. Failures")
    failures = [x for x in records if x["verdict"] == "WRONG"]

    ws.append([f"{len(failures)} of {len(records)} inputs were classified wrongly. "
               "Each is diagnosed below."])
    ws.cell(row=1, column=1).font = TITLE_FONT
    ws.append([])

    headers = ["Corpus", "ID", "User Input", "Input Quality", "Expected",
               "Predicted", "Confidence", "Failure Class", "Diagnosis"]
    ws.append(headers)
    style_header(ws, 3, len(headers))

    for rec in failures:
        ws.append([
            rec["corpus"], rec["id"], rec["query"], rec["quality"],
            rec["expected"], rec["predicted"], rec["confidence"],
            FAILURE_CLASS.get(rec["id"], "Uncategorised"),
            DIAGNOSIS.get(rec["id"], "See the rationale column on sheet 2."),
        ])
        row = ws.max_row
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=row, column=c)
            cell.border = BORDER
            cell.alignment = TOP
        ws.cell(row=row, column=3).alignment = WRAP
        ws.cell(row=row, column=9).alignment = WRAP
        ws.cell(row=row, column=7).number_format = "0.00"
        # A confident wrong answer is the dangerous kind; flag it.
        if rec["confidence"] >= 0.80:
            ws.cell(row=row, column=7).fill = WRONG_FILL
            ws.cell(row=row, column=7).font = Font(bold=True, color="C00000")
        ws.row_dimensions[row].height = 46

    set_widths(ws, {"A": 13, "B": 8, "C": 46, "D": 15, "E": 16, "F": 16,
                    "G": 11, "H": 34, "I": 76})
    ws.freeze_panes = "C4"

    row = ws.max_row + 2
    ws.cell(row=row, column=1,
            value="A confidence >= 0.80 on a wrong answer is highlighted: an error "
                  "the engine flagged as uncertain is a degraded answer the UI can "
                  "hedge, but an error it was confident about is simply wrong. The "
                  "second kind is what matters.").font = Font(italic=True, color="C00000")
    ws.cell(row=row, column=1).alignment = WRAP
    ws.row_dimensions[row].height = 46


def sheet_patterns(wb, records: list) -> None:
    ws = wb.create_sheet("4. Failure Patterns")
    failures = [x for x in records if x["verdict"] == "WRONG"]
    grouped = defaultdict(list)
    for rec in failures:
        grouped[FAILURE_CLASS.get(rec["id"], "Uncategorised")].append(rec)

    ws.append(["Root causes, grouped. Nineteen individual failures reduce to "
               "nine underlying gaps."])
    ws.cell(row=1, column=1).font = TITLE_FONT
    ws.append([])

    headers = ["Failure Class", "Count", "Example Inputs", "What is missing", "Fixable?"]
    ws.append(headers)
    style_header(ws, 3, len(headers))

    remedies = {
        "Negation blindness":
            ("A polarity check. Markers are matched without regard to any "
             "negation governing them.", "Yes - scope negation over the clause a marker sits in."),
        "Multi-clause question":
            ("Clause splitting. R1 escalates to MIXED only when two output "
             "FORMATS are named, not when two QUESTIONS are asked.",
             "Yes - split on conjunctions and classify each clause."),
        "Conjunction not recognised":
            ("'but' and 'then' are absent from the conjunction list R1 tests.",
             "Yes - one-line lexicon change."),
        "Superlative expressed without a superlative word":
            ("Paraphrase coverage - 'spending more than the others' carries no "
             "superlative token.", "Partly - the LLM path handles paraphrase better than the lexicon."),
        "Idiom not in lexicon":
            ("'headline number', 'run the numbers' are conventional business "
             "idioms that no marker covers.", "Yes - but idioms are open-ended; the lexicon will always lag."),
        "Open interpretation request":
            ("A category for 'tell me what you see' requests that name no "
             "format and no metric.", "Partly - needs an interpretation-request marker family."),
        "Polar comparison question":
            ("Yes/no framing ('is revenue up or down') that wants a verbal "
             "judgement, not a plot.", "Yes - add a polar-question detector."),
        "Domain acronym unknown":
            ("A metric vocabulary. DSO, NPS, MRR carry the analytical intent "
             "but are opaque to the lexicon.", "Yes - bind acronyms via the schema rather than the lexicon."),
        "Verb not in lexicon":
            ("'tabulate' is a plain table request that no marker covers.",
             "Yes - lexicon addition."),
        "Breakdown with no axis":
            ("'break down' is read as a CHART cue, which is right only when a "
             "dimension follows it.", "Yes - require a following dimension for the chart reading."),
        "Single-word exhaustive request":
            ("Bare 'everything' has no anchoring noun for the MIXED marker.",
             "Yes - lexicon addition."),
    }

    for name, group in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        missing, fixable = remedies.get(name, ("", ""))
        ws.append([
            name, len(group),
            "  |  ".join(f"{g['id']}: {g['query'][:46]}" for g in group[:3]),
            missing, fixable,
        ])
        row = ws.max_row
        for c in range(1, len(headers) + 1):
            cell = ws.cell(row=row, column=c)
            cell.border = BORDER
            cell.alignment = WRAP
        ws.row_dimensions[row].height = 58

    set_widths(ws, {"A": 40, "B": 8, "C": 56, "D": 60, "E": 50})
    ws.freeze_panes = "A4"


def sheet_metrics(wb, records: list) -> None:
    ws = wb.create_sheet("5. Metrics")
    row = 1
    for corpus_name, _, _ in CORPORA + [("ALL CORPORA COMBINED", "", "")]:
        subset = ([x for x in records if x["corpus"] == corpus_name]
                  if corpus_name != "ALL CORPORA COMBINED" else records)
        if not subset:
            continue
        ws.cell(row=row, column=1, value=corpus_name).font = SUB_FONT
        row += 1
        ws.cell(row=row, column=1, value="Intent")
        ws.cell(row=row, column=2, value="Support")
        ws.cell(row=row, column=3, value="Precision")
        ws.cell(row=row, column=4, value="Recall")
        ws.cell(row=row, column=5, value="F1")
        style_header(ws, row, 5)
        row += 1

        f1s = []
        for label in ALL_RESPONSE_INTENTS + [NOT_A_DATA_REQUEST]:
            tp = sum(1 for x in subset if x["predicted"] == label and x["expected"] == label)
            fp = sum(1 for x in subset if x["predicted"] == label and x["expected"] != label)
            fn = sum(1 for x in subset if x["predicted"] != label and x["expected"] == label)
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
            f1s.append(f1)
            ws.cell(row=row, column=1, value=label).border = BORDER
            ws.cell(row=row, column=2, value=tp + fn).border = BORDER
            for col, val in ((3, precision), (4, recall), (5, f1)):
                cell = ws.cell(row=row, column=col, value=val)
                cell.number_format = "0.0%" if col < 5 else "0.00"
                cell.border = BORDER
                if val < 0.7:
                    cell.fill = WRONG_FILL
                elif val < 0.9:
                    cell.fill = WARN_FILL
            row += 1
        ws.cell(row=row, column=1, value="macro avg").font = Font(bold=True)
        c = ws.cell(row=row, column=5, value=sum(f1s) / len(f1s))
        c.number_format = "0.00"
        c.font = Font(bold=True)
        row += 3

    set_widths(ws, {"A": 34, "B": 10, "C": 12, "D": 11, "E": 9})


def sheet_confusion(wb, records: list) -> None:
    ws = wb.create_sheet("6. Confusion Matrix")
    row = 1
    for corpus_name in [c[0] for c in CORPORA] + ["ALL CORPORA COMBINED"]:
        subset = ([x for x in records if x["corpus"] == corpus_name]
                  if corpus_name != "ALL CORPORA COMBINED" else records)
        if not subset:
            continue
        ws.cell(row=row, column=1, value=f"{corpus_name}   "
                                         "(rows = expected, columns = predicted)").font = SUB_FONT
        row += 1
        ws.cell(row=row, column=1, value="")
        for i, label in enumerate(ALL_RESPONSE_INTENTS + [NOT_A_DATA_REQUEST]):
            ws.cell(row=row, column=2 + i, value=label)
        style_header(ws, row, len(ALL_RESPONSE_INTENTS) + 2)
        row += 1

        matrix = defaultdict(Counter)
        for rec in subset:
            matrix[rec["expected"]][rec["predicted"]] += 1

        for expected in ALL_RESPONSE_INTENTS + [NOT_A_DATA_REQUEST]:
            cell = ws.cell(row=row, column=1, value=expected)
            cell.font = Font(bold=True)
            cell.border = BORDER
            for i, predicted in enumerate(ALL_RESPONSE_INTENTS + [NOT_A_DATA_REQUEST]):
                count = matrix[expected][predicted]
                c = ws.cell(row=row, column=2 + i, value=count or None)
                c.border = BORDER
                c.alignment = Alignment(horizontal="center")
                if count and expected == predicted:
                    c.fill = CORRECT_FILL
                elif count:
                    c.fill = WRONG_FILL
                    c.font = Font(color="C00000", bold=True)
            row += 1
        row += 2

    set_widths(ws, {"A": 22, "B": 16, "C": 16, "D": 16, "E": 16, "F": 16, "G": 20})


def sheet_worked_example(wb) -> None:
    ws = wb.create_sheet("7. Worked Example")
    set_widths(ws, {"A": 30, "B": 86})
    r = 1
    r = write_paragraph(ws, r, "One question traced end to end", True, 14, "1F3864")
    r = write_paragraph(ws, r,
        "Two questions that differ by one letter take different paths and "
        "produce different outputs. This is the behaviour the taxonomy exists "
        "to produce.")
    r += 1

    for query in ["which department spends the most",
                  "which departments spend the most"]:
        analysis = query_analyzer.analyze(query, schema_meta={
            "expenses": {"department": "VARCHAR", "spend": "DECIMAL"}}, use_llm=False)
        result = response_intent.classify(query, analysis)

        ws.cell(row=r, column=1, value=f'"{query}"').font = SUB_FONT
        r += 1
        pairs = [
            ("Analytical intent", f"{analysis.primary_intent} "
                                  f"(confidence {analysis.intent_confidence:.2f})"),
            ("Response intent", f"{result.intent} "
                                f"(confidence {result.confidence:.2f}, via {result.source})"),
            ("Blocks emitted", " + ".join(result.blocks)),
            ("Answer focus", result.answer_focus),
            ("Row limit", f"{analysis.limit}  [{analysis.limit_source}]"),
            ("Ordering", analysis.ordering or "(none - direction not inferable)"),
            ("Chart hint", analysis.recommended_chart),
            ("Deciding rule", result.rationale),
        ]
        for key, value in pairs:
            ws.cell(row=r, column=1, value=key).font = Font(bold=True, size=10)
            cell = ws.cell(row=r, column=2, value=value)
            cell.alignment = WRAP
            cell.font = Font(name="Consolas", size=9)
            ws.cell(row=r, column=1).border = BORDER
            cell.border = BORDER
            r += 1
        r += 1

    r = write_paragraph(ws, r,
        "The singular form returns one department name with LIMIT 1 and no "
        "chart. The plural form is a ranking, so it returns rows with an "
        "inferred LIMIT 5 - inferred, because the user named no number, and "
        "flagged as such so the interface can offer to widen it.", False, 10)
    ws.sheet_view.showGridLines = False


# --------------------------------------------------------------------------


def main() -> None:
    records = []
    for name, filename, _ in CORPORA:
        records.extend(run_corpus(filename, name))

    wb = Workbook()
    wb.remove(wb.active)
    sheet_overview(wb, records)
    sheet_all_results(wb, records)
    sheet_failures(wb, records)
    sheet_patterns(wb, records)
    sheet_metrics(wb, records)
    sheet_confusion(wb, records)
    sheet_worked_example(wb)
    wb.save(OUTPUT)

    total = len(records)
    wrong = sum(1 for x in records if x["verdict"] == "WRONG")
    print(f"Wrote {OUTPUT}")
    print(f"  {total} inputs across {len(CORPORA)} corpora")
    print(f"  {total - wrong} correct, {wrong} wrong ({(total-wrong)/total:.1%})")
    for name, _, _ in CORPORA:
        subset = [x for x in records if x["corpus"] == name]
        hits = sum(1 for x in subset if x["verdict"] == "CORRECT")
        print(f"  {name:14} {hits:3}/{len(subset):<3} = {hits/len(subset):.1%}")


if __name__ == "__main__":
    main()
