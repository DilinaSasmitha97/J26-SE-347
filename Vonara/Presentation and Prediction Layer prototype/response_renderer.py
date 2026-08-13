"""
Response assembly: turning a response intent into the blocks a client renders.

`response_intent.py` decides the shape; this module builds it. The contract is
strict in one direction - the renderer may emit *only* the blocks the intent
declares in `schemas.RESPONSE_BLOCKS`, and it emits all of them. That is what
makes the taxonomy verifiable end to end: a test can assert that a
SINGLE_ANSWER response contains an ANSWER block and nothing else.

Every block is built from data that already exists in the envelope - the
profiled result set, the verified claims, the Vega-Lite spec. The renderer
computes no new statistics and narrates nothing, so it cannot introduce a
number that the summarization layer has not already verified.
"""

from schemas import RESPONSE_BLOCKS, ResponseBlock, ResponseIntent
from summarization import fmt

# A table block never ships an unbounded row set to the client; the full count
# is always reported so the UI can offer paging.
TABLE_ROW_LIMIT = 200

# A short summary is short by definition. MIXED_SUMMARY gets more room because
# its narrative has to carry the table and the chart alongside it.
SHORT_SUMMARY_SENTENCES = 3
MIXED_SUMMARY_SENTENCES = 6


def _humanize(name: str) -> str:
    return str(name).replace("_", " ").strip().title()


def _first_sentences(text: str, limit: int) -> str:
    """Truncate on sentence boundaries so no claim is ever cut mid-number."""
    if not text:
        return ""
    parts = [p.strip() for p in text.replace("\n", " ").split(". ") if p.strip()]
    if len(parts) <= limit:
        return text.strip()
    kept = ". ".join(parts[:limit]).rstrip(".")
    return f"{kept}."


def _pick_answer_cell(rows: list, profile, focus: str = "VALUE") -> tuple:
    """
    Choose the one cell that answers a scalar question.

    Which cell that is depends on what was asked, not on what the row contains.
    "which department spends the most" and "how much did the top department
    spend" return the same row - one label, one number - but the first is
    answered by the label and the second by the number. `focus` carries that
    distinction down from the classifier.

    Under ENTITY focus the label leads and the measure becomes the qualifier;
    under VALUE focus the reverse. Either way the other half still travels
    with the answer, so the figure is never shown without its subject and the
    subject is never shown without its evidence.
    """
    if not rows:
        return None, "", ""

    row = rows[0]
    if not isinstance(row, dict):
        return row, "value", ""

    measures = list(getattr(profile, "measure_columns", []) or [])
    dimensions = list(getattr(profile, "dimension_columns", []) or [])

    def _first_numeric():
        column = next((m for m in measures if m in row), None)
        if column is None:
            column = next(
                (k for k, v in row.items()
                 if isinstance(v, (int, float)) and not isinstance(v, bool)),
                None,
            )
        return column

    def _first_label():
        column = next((d for d in dimensions if d in row), None)
        if column is None:
            column = next(
                (k for k, v in row.items()
                 if not isinstance(v, (int, float, bool)) and v not in (None, "")),
                None,
            )
        return column

    if focus == "ENTITY":
        column = _first_label() or _first_numeric()
    else:
        column = _first_numeric() or _first_label()
    if column is None:
        column = next(iter(row), None)

    qualifier_column = ""
    for key, value in row.items():
        if key != column and value not in (None, ""):
            qualifier_column = key
            break

    return row.get(column), column, qualifier_column


def _display(value) -> tuple:
    """Render one cell the same way everywhere, and say what kind it is."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return fmt(float(value)), "number"
    return ("-" if value in (None, "") else str(value)), "text"


def build_answer_block(rows: list, profile, analysis, focus: str = "VALUE") -> dict:
    """The one headline cell, its label, and the qualifier that scopes it."""
    value, column, qualifier_column = _pick_answer_cell(rows, profile, focus)
    row = rows[0] if rows and isinstance(rows[0], dict) else {}

    display, value_type = _display(value)
    qualifier_value = row.get(qualifier_column) if qualifier_column else None
    qualifier_display, _ = _display(qualifier_value)

    label = _humanize(column) if column else "Answer"

    # The aggregation only qualifies a number. Prefixing an entity name with
    # "Sum of" would describe the wrong half of the row.
    if value_type == "number" and analysis is not None and getattr(analysis, "metrics", None):
        aggregation = getattr(analysis.metrics[0], "aggregation", "")
        if aggregation and aggregation not in ("NONE", ""):
            label = f"{aggregation.title()} of {label}"

    return {
        "block": ResponseBlock.ANSWER.value,
        "label": label,
        "value": value,
        "display_value": display,
        "value_type": value_type,
        "focus": focus,
        # The other half of the row: the evidence for an ENTITY answer, the
        # subject of a VALUE one. Rendered, so a client can print it directly.
        "qualifier": qualifier_display if qualifier_column else "",
        "qualifier_label": _humanize(qualifier_column) if qualifier_column else "",
        "qualifier_column": qualifier_column,
        "source_column": column or "",
        "supporting_row": row,
    }


def build_summary_block(summary, max_sentences: int) -> dict:
    """Verified prose only - the text comes straight from the claim engine."""
    text = getattr(summary, "text", "") if summary is not None else ""
    claims = getattr(summary, "claims", []) if summary is not None else []
    verification = getattr(summary, "verification", {}) if summary is not None else {}

    return {
        "block": ResponseBlock.SUMMARY.value,
        "text": _first_sentences(text, max_sentences),
        "full_text": text,
        "mode": getattr(summary, "mode", "DETERMINISTIC") if summary is not None else "NONE",
        "claim_count": len(claims),
        "verified": bool(verification.get("passed", True)) if verification else True,
    }


def _is_ordered_by(rows: list, column: str, descending: bool) -> bool:
    """Is the result actually sorted on `column` in the stated direction?"""
    if not column or len(rows) < 2:
        return False
    values = []
    for row in rows:
        value = row.get(column) if isinstance(row, dict) else None
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        values.append(value)
    pairs = zip(values, values[1:])
    return all(a >= b for a, b in pairs) if descending else all(a <= b for a, b in pairs)


def build_table_block(rows: list, profile, row_limit: int = TABLE_ROW_LIMIT,
                      analysis=None) -> dict:
    """
    Column definitions plus a bounded row window.

    Two different bounds can apply, and they mean different things:

      * `row_limit` is a *transport* bound - the client is not shipped 10,000
        rows in one payload. `row_count` always reports the true total.
      * an INFERRED limit is a *semantic* bound - "which departments spend the
        most" asked for a top slice, and returning all 30 does not answer it.

    The semantic bound is applied only when the result can be *proved* sorted
    on the ordering column. Trimming an unordered result to five rows would
    present an arbitrary five as "the most", which is worse than showing
    everything; in that case the rows are left intact and the unapplied bound
    is reported so the caller can push the ORDER BY into the SQL instead.
    """
    columns = []
    for column in getattr(profile, "columns", []) or []:
        columns.append(
            {
                "name": column.name,
                "label": _humanize(column.name),
                "role": column.role,
                "type": column.inferred_type,
                "align": "right" if column.inferred_type == "number" else "left",
                "null_count": column.null_count,
            }
        )

    if not columns and rows and isinstance(rows[0], dict):
        columns = [
            {"name": k, "label": _humanize(k), "role": "UNSUPPORTED",
             "type": "string", "align": "left", "null_count": 0}
            for k in rows[0]
        ]

    source_rows = rows
    semantic_limit = 0
    limit_applied = False
    limit_note = ""

    if analysis is not None and getattr(analysis, "limit_source", "NONE") == "INFERRED":
        semantic_limit = int(getattr(analysis, "limit", 0) or 0)

    if semantic_limit and len(rows) > semantic_limit:
        ordering = str(getattr(analysis, "ordering", "") or "")
        order_column = ordering.split()[0] if ordering else ""
        descending = ordering.upper().endswith("DESC")

        if _is_ordered_by(rows, order_column, descending):
            source_rows = rows[:semantic_limit]
            limit_applied = True
            limit_note = (
                f"Showing the top {semantic_limit} by '{order_column}'. "
                f"The question implied a bound but did not state one; "
                f"{len(rows)} rows matched in total."
            )
        else:
            limit_note = (
                f"An implied bound of {semantic_limit} was not applied: the "
                f"result is not ordered by "
                f"'{order_column or 'any known measure'}', so no subset can be "
                f"claimed to be the top {semantic_limit}."
            )

    window = source_rows[:row_limit]
    return {
        "block": ResponseBlock.TABLE.value,
        "columns": columns,
        "rows": window,
        # The true total always, whichever bound trimmed the window.
        "row_count": len(rows),
        "rows_returned": len(window),
        "truncated": len(rows) > len(window),
        "implied_limit": semantic_limit,
        "implied_limit_applied": limit_applied,
        "limit_note": limit_note,
    }


def build_chart_block(chart_spec: dict) -> dict:
    """The Vega-Lite spec produced by Part 2, with its selection metadata."""
    meta = (chart_spec or {}).get("_meta", {}) if isinstance(chart_spec, dict) else {}
    return {
        "block": ResponseBlock.CHART.value,
        "chart_type": meta.get("chart_type", "table"),
        "rationale": meta.get("rationale", ""),
        "spec": chart_spec or {},
    }


def render(
    response_result,
    analysis=None,
    profile=None,
    rows=None,
    chart_spec=None,
    summary=None,
) -> dict:
    """
    Assemble the response payload for a decided intent.

    Args:
        response_result: the `ResponseIntentResult` after guardrails.
        analysis:        `QueryAnalysis` from Part 1.
        profile:         `ResultProfile` of the executed rows.
        rows:            the masked result set.
        chart_spec:      the Vega-Lite spec from Part 2.
        summary:         the `SummaryResult` from Part 3.

    Returns:
        A dict with the intent, the ordered block names, and one populated
        entry per block. Blocks the intent did not request are absent, not
        empty - a client can branch on presence alone.
    """
    rows = rows or []
    intent = ResponseIntent(response_result.intent)

    # The guardrails may have removed a block (a mixed report over unplottable
    # data), so the emitted list is theirs, not the taxonomy default.
    declared = [b.value for b in RESPONSE_BLOCKS[intent]]
    emitted = list(response_result.blocks) or declared

    max_sentences = (
        MIXED_SUMMARY_SENTENCES if intent is ResponseIntent.MIXED_SUMMARY
        else SHORT_SUMMARY_SENTENCES
    )

    blocks = {}
    for name in emitted:
        if name == ResponseBlock.ANSWER.value:
            blocks["answer"] = build_answer_block(
                rows, profile, analysis,
                focus=getattr(response_result, "answer_focus", "VALUE"),
            )
        elif name == ResponseBlock.SUMMARY.value:
            blocks["summary"] = build_summary_block(summary, max_sentences)
        elif name == ResponseBlock.TABLE.value:
            blocks["table"] = build_table_block(rows, profile, analysis=analysis)
        elif name == ResponseBlock.CHART.value:
            blocks["chart"] = build_chart_block(chart_spec)

    payload = {
        "response_intent": response_result.to_dict(),
        "blocks_emitted": emitted,
        "blocks_declared": declared,
        **blocks,
    }
    return payload
