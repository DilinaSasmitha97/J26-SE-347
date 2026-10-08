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

import re
from types import SimpleNamespace

from schemas import RESPONSE_BLOCKS, ResponseBlock, ResponseIntent
from summarization import fmt, verify_summary

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


# When the user explicitly asked for a forecast, a length-bounded summary picks
# claims in this order instead of keeping its first N sentences. Historical
# claims always come first in the full text, so plain truncation would keep
# "the query returned 24 rows" and drop the forecast the user asked for.
# One claim per kind; the chosen claims are then put back in narrative order.
_FORECAST_FIRST = (
    "FORECAST_PATH",        # the projection itself
    "STRATEGY_HEADLINE",    # the strategy's answer (who leads, share shift, persistence)
    "READINESS_CAUTION",    # a forecast shown with warnings must show them too
    "SKIPPED",              # ...or why there is none
    "PREDICTED_BREACH",     # a projected threshold crossing
    "SCENARIO_TOTAL",       # the what-if outcome
    "FORECAST_VS_HISTORY",  # where the projection sits against the past
    "MEAN",
    "CHANGE",
    "TOTAL",
)
# Per-period forecast sentences are already covered by FORECAST_PATH, and
# per-category ones by the strategy headline.
_NEVER_FILL = {"FORECAST", "ROW_COUNT", "TRAJECTORY_CATEGORY", "SHARE_CATEGORY"}


def select_forecast_claims(claims: list, limit: int) -> list:
    """Choose up to `limit` claims, forecast-related first, in narrative order."""
    chosen = []
    for kind in _FORECAST_FIRST:
        if len(chosen) >= limit:
            break
        match = next((c for c in claims if c.kind == kind), None)
        if match is not None:
            chosen.append(match)
    for c in claims:
        if len(chosen) >= limit:
            break
        if all(c is not x for x in chosen) and c.kind not in _NEVER_FILL:
            chosen.append(c)
    position = {id(c): i for i, c in enumerate(claims)}
    return sorted(chosen, key=lambda c: position[id(c)])


def build_summary_block(summary, max_sentences: int, forecast_requested: bool = False) -> dict:
    """Verified prose only - the text comes straight from the claim engine."""
    text = getattr(summary, "text", "") if summary is not None else ""
    claims = getattr(summary, "claims", []) if summary is not None else []
    verification = getattr(summary, "verification", {}) if summary is not None else {}
    mode = getattr(summary, "mode", "DETERMINISTIC") if summary is not None else "NONE"

    shown = _first_sentences(text, max_sentences)
    selection = "LEADING_SENTENCES"
    if forecast_requested and claims:
        chosen = select_forecast_claims(claims, max_sentences)
        if chosen:
            # Built from claim texts, so it is deterministic even when the full
            # text was LLM-narrated; re-verified because it is a new rendering.
            shown = " ".join(c.text for c in chosen)
            verification = verify_summary(shown, claims)
            selection = "FORECAST_PRIORITY"
            mode = "DETERMINISTIC"

    return {
        "block": ResponseBlock.SUMMARY.value,
        "text": shown,
        "full_text": text,
        "mode": mode,
        "sentence_selection": selection,
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


# ==========================================================================
# Forecast delivery
# ==========================================================================
#
# Rule: when the user explicitly asked for a prediction, the response carries
# either the forecast or the reason there is none - whatever shape it takes.
# The chart already layers the forecast (visualization.extend_with_forecast);
# the helpers below give the table, the answer and a notice the same ability.
# All numbers come from the forecast output or from verified claims.

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}")


def _period_cell(point, sample):
    """Render a forecast period the way the result set renders its own periods."""
    if isinstance(sample, int) and not isinstance(sample, bool) and point.label.isdigit():
        return int(point.label)
    text = "" if sample is None else str(sample)
    if _DATE_RE.match(text):
        return point.timestamp[:10]
    if _DATETIME_RE.match(text):
        return point.timestamp.replace("T", " ")[:19]
    return point.label


def extend_table_with_forecast(table: dict, forecast, scenario=None) -> bool:
    """
    Append the forecast periods to a table block as rows marked FORECAST.

    Only possible when the table contains both the time axis and the measure
    that was forecast; otherwise the table is left unchanged and False is
    returned, so the caller knows the notice must carry the forecast instead.
    """
    names = [c["name"] for c in table.get("columns", [])]
    time_col, value_col = forecast.time_column, forecast.value_column
    if not forecast.points or time_col not in names or value_col not in names:
        return False

    sample = next((r.get(time_col) for r in reversed(table["rows"])
                   if r.get(time_col) is not None), None)
    simulated = {}
    if scenario is not None and getattr(scenario, "simulated", False):
        simulated = {p["period_index"]: p["predicted"] for p in scenario.scenario_points}

    extra = {"row_type": "ACTUAL", "lower_bound": None, "upper_bound": None}
    if simulated:
        extra["scenario"] = None
    actual_rows = [{**row, **extra} for row in table["rows"]]

    forecast_rows = []
    for p in forecast.points:
        row = {name: None for name in names}
        row[time_col] = _period_cell(p, sample)
        row[value_col] = round(p.predicted, 2)
        row.update(row_type="FORECAST", lower_bound=round(p.lower_bound, 2),
                   upper_bound=round(p.upper_bound, 2))
        if simulated:
            row["scenario"] = round(simulated.get(p.period_index, p.predicted), 2)
        forecast_rows.append(row)

    table["rows"] = actual_rows + forecast_rows
    number = {"type": "number", "align": "right", "role": "MEASURE"}
    table["columns"] = table["columns"] + [
        {"name": "row_type", "label": "Row Type", "role": "DIMENSION",
         "type": "string", "align": "left", "null_count": 0},
        {"name": "lower_bound", "label": "Lower Bound", **number, "null_count": len(actual_rows)},
        {"name": "upper_bound", "label": "Upper Bound", **number, "null_count": len(actual_rows)},
    ]
    if simulated:
        table["columns"].append(
            {"name": "scenario", "label": "Scenario", **number, "null_count": len(actual_rows)})
    table["forecast_rows"] = len(forecast_rows)
    table["forecast_confidence_level"] = forecast.confidence_level
    return True


def build_forecast_answer_block(forecast, analysis) -> dict:
    """
    A scalar question about the future is answered by the forecast.

    "What will expenses be next month" -> the first projected period, with its
    interval. When the user stated a multi-period horizon ("over the next 3
    months") the answer is the projected total, which is claim F3; no interval
    is given for it, because summing per-period bounds is not a valid interval.
    """
    points = forecast.points
    horizon = getattr(analysis, "horizon", None)
    wants_total = (
        horizon is not None and getattr(horizon, "source", "") == "EXPLICIT"
        and int(getattr(horizon, "value", 0) or 0) > 1 and len(points) > 1
    )
    measure = _humanize(forecast.value_column)
    if wants_total:
        value = sum(p.predicted for p in points)
        label = f"Projected Total {measure}"
        qualifier = f"{points[0].label} to {points[-1].label}"
        interval = None
    else:
        p = points[0]
        value = p.predicted
        label = f"Projected {measure}"
        qualifier = p.label
        interval = {"lower": p.lower_bound, "upper": p.upper_bound,
                    "confidence_level": forecast.confidence_level,
                    "display": f"{fmt(p.lower_bound)} to {fmt(p.upper_bound)}"}
    return {
        "block": ResponseBlock.ANSWER.value,
        "label": label,
        "value": round(value, 4),
        "display_value": fmt(value),
        "value_type": "number",
        "focus": "VALUE",
        "qualifier": qualifier,
        "qualifier_label": "Forecast Period",
        "qualifier_column": forecast.time_column,
        "source_column": forecast.value_column,
        "supporting_row": {},
        "is_forecast": True,
        "interval": interval,
        "model": forecast.model,
    }


def build_refused_answer_block(reason: str) -> dict:
    """The future value was asked for and cannot be produced: say so, and why."""
    return {
        "block": ResponseBlock.ANSWER.value,
        "label": "Forecast",
        "value": None,
        "display_value": "No forecast available",
        "value_type": "text",
        "focus": "VALUE",
        "qualifier": reason,
        "qualifier_label": "Reason",
        "qualifier_column": "",
        "source_column": "",
        "supporting_row": {},
        "is_forecast": True,
        "interval": None,
        "model": "NONE",
    }


def extend_table_with_category_forecasts(table: dict, strategy_result) -> bool:
    """Append per-category forecast rows (one per category and period) to a table."""
    d = strategy_result.details or {}
    names = [c["name"] for c in table.get("columns", [])]
    group, measure = d.get("group_column"), d.get("measure")
    time_col = next((c["name"] for c in table.get("columns", []) if c.get("role") == "TEMPORAL"), "")
    cats = d.get("categories") or d.get("categories_forecast") or []
    if not cats or group not in names or measure not in names or not time_col:
        return False
    sample = next((r.get(time_col) for r in reversed(table["rows"])
                   if r.get(time_col) is not None), None)
    extra = {"row_type": "ACTUAL", "lower_bound": None, "upper_bound": None}
    actual_rows = [{**row, **extra} for row in table["rows"]]
    forecast_rows = []
    for c in cats:
        for p in c["points"]:
            point = SimpleNamespace(label=p["label"], timestamp=p["timestamp"] or p["label"])
            row = {name: None for name in names}
            row.update({time_col: _period_cell(point, sample), group: c["category"],
                        measure: round(p["predicted"], 2), "row_type": "FORECAST",
                        "lower_bound": round(p["lower"], 2), "upper_bound": round(p["upper"], 2)})
            forecast_rows.append(row)
    table["rows"] = actual_rows + forecast_rows
    number = {"type": "number", "align": "right", "role": "MEASURE"}
    table["columns"] = table["columns"] + [
        {"name": "row_type", "label": "Row Type", "role": "DIMENSION",
         "type": "string", "align": "left", "null_count": 0},
        {"name": "lower_bound", "label": "Lower Bound", **number, "null_count": len(actual_rows)},
        {"name": "upper_bound", "label": "Upper Bound", **number, "null_count": len(actual_rows)},
    ]
    table["forecast_rows"] = len(forecast_rows)
    return True


def build_strategy_answer_block(strategy_result, summary) -> dict:
    """A scalar question answered by a strategy, e.g. 'which region will lead?'."""
    d = strategy_result.details or {}
    headline = next((c.text for c in getattr(summary, "claims", []) or []
                     if c.kind == "STRATEGY_HEADLINE"), "")
    if strategy_result.executed_as == "CATEGORY_TRAJECTORY":
        lead = d["projected_leader"]
        return {
            "block": ResponseBlock.ANSWER.value,
            "label": f"Projected leader ({_humanize(d['group_column'])})",
            "value": lead["category"],
            "display_value": lead["category"],
            "value_type": "text",
            "focus": "ENTITY",
            "qualifier": f"{fmt(lead['value'])} in {lead['label']}",
            "qualifier_label": f"Projected {_humanize(d['measure'])}",
            "qualifier_column": d["measure"],
            "source_column": d["group_column"],
            "supporting_row": {},
            "is_forecast": True,
            "interval": None,
            "model": "PER_CATEGORY",
            "statement": headline,
        }
    return {
        "block": ResponseBlock.ANSWER.value,
        "label": strategy_result.executed_as.replace("_", " ").title(),
        "value": None,
        "display_value": headline,
        "value_type": "text",
        "focus": "VALUE",
        "qualifier": "",
        "qualifier_label": "",
        "qualifier_column": "",
        "source_column": "",
        "supporting_row": {},
        "is_forecast": True,
        "interval": None,
        "model": strategy_result.executed_as,
        "statement": headline,
    }


def forecast_notes(forecast) -> list:
    """
    What happened while the forecast was made, beyond the readiness cautions
    (Stage 8): each is something the user would otherwise not know.
    """
    diag = getattr(forecast, "diagnostics", None) or {}
    notes = []
    clamped = diag.get("horizon_clamped_from")
    if clamped:
        notes.append({"code": "HORIZON_SHORTENED", "message": (
            f"{clamped} periods were asked for; {forecast.horizon} are shown, because a "
            "forecast is never longer than half the history it is built from.")})
    if "fell back" in (getattr(forecast, "model_reason", "") or ""):
        start = forecast.model_reason.rfind("[")
        detail = forecast.model_reason[start + 1:].rstrip("]") if start >= 0 else ""
        notes.append({"code": "MODEL_FALLBACK",
                      "message": f"{detail[:1].upper()}{detail[1:]}." if detail else
                      "The chosen model could not be used; a simpler one was."})
    if diag.get("clipped_at_zero"):
        notes.append({"code": "RANGE_CLIPPED_AT_ZERO", "message": (
            "This measure has never been negative, so the forecast range is cut at zero "
            f"for {diag['clipped_at_zero']} of {forecast.horizon} periods.")})
    return notes


def build_forecast_notice(forecast, readiness, summary, shown_in: list,
                          strategy_result=None) -> dict:
    """
    One status line for a requested forecast, present in every response shape.

    `shown_in` lists the blocks that already display the forecast, so a client
    can hide the notice when the chart or table carries it, and must show it
    when nothing else does (a donut, a KPI card, a refusal).
    """
    claims = getattr(summary, "claims", []) or []

    def claim_text(kind):
        return next((c.text for c in claims if c.kind == kind), "")

    strategy_done = strategy_result is not None and getattr(strategy_result, "executed", False)
    if (forecast is not None and forecast.generated) or strategy_done:
        headline = claim_text("STRATEGY_HEADLINE")
        made = forecast is not None and forecast.generated
        diag = (getattr(forecast, "diagnostics", None) or {}) if made else {}
        return {
            "requested": True,
            "status": "SHOWN",
            "readiness_decision": getattr(readiness, "decision", ""),
            "warnings": list(getattr(readiness, "warnings", []) or []),
            "reason_codes": list(getattr(readiness, "reason_codes", []) or []),
            "message": claim_text("FORECAST_PATH") or headline,
            "strategy": getattr(strategy_result, "executed_as", "") if strategy_done else "",
            "strategy_message": headline if strategy_done else "",
            "reason": "",
            "model": forecast.model if forecast is not None and forecast.generated
            else "PER_CATEGORY",
            "horizon": forecast.horizon if forecast is not None and forecast.generated else 0,
            "horizon_source": diag.get("horizon_source", ""),
            "horizon_requested": diag.get("horizon_requested", 0),
            "notes": forecast_notes(forecast) if made else [],
            "shown_in": shown_in,
        }
    reason = (getattr(forecast, "skipped_reason", "") if forecast is not None else "") \
        or (getattr(readiness, "reason", "") if readiness is not None else "") \
        or "The forecast could not be produced."
    return {
        "requested": True,
        "status": "REFUSED",
        "readiness_decision": getattr(readiness, "decision", ""),
        "warnings": list(getattr(readiness, "warnings", []) or []),
        "reason_codes": list(getattr(readiness, "reason_codes", []) or []),
        "message": claim_text("SKIPPED") or f"No forecast was produced: {reason}",
        "reason": reason,
        "model": "NONE",
        "horizon": 0,
        "shown_in": shown_in,
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
    forecast=None,
    readiness=None,
    scenario=None,
    strategy_result=None,
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
        forecast, readiness, scenario: Stage 4 / 2 / 6 outputs, used to deliver
                         an explicitly requested forecast in any shape.

    Returns:
        A dict with the intent, the ordered block names, and one populated
        entry per block. Blocks the intent did not request are absent, not
        empty - a client can branch on presence alone. When the user
        explicitly asked for a prediction, `forecast_notice` is added; it is
        not a block, it is the status of the request.
    """
    forecast_requested = getattr(analysis, "prediction_trigger", "NONE") == "EXPLICIT"
    forecast_ready = forecast is not None and getattr(forecast, "generated", False)
    strategy_done = (strategy_result is not None and getattr(strategy_result, "executed", False)
                     and strategy_result.executed_as != "TEMPORAL_FORECAST")
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
    shown_in = []
    for name in emitted:
        if name == ResponseBlock.ANSWER.value:
            if forecast_requested and strategy_done:
                blocks["answer"] = build_strategy_answer_block(strategy_result, summary)
                shown_in.append(name)
            elif forecast_requested and forecast_ready:
                blocks["answer"] = build_forecast_answer_block(forecast, analysis)
                shown_in.append(name)
            elif forecast_requested:
                reason = (getattr(forecast, "skipped_reason", "")
                          or getattr(readiness, "reason", "")
                          or "The forecast could not be produced.")
                blocks["answer"] = build_refused_answer_block(reason)
            else:
                blocks["answer"] = build_answer_block(
                    rows, profile, analysis,
                    focus=getattr(response_result, "answer_focus", "VALUE"),
                )
        elif name == ResponseBlock.SUMMARY.value:
            blocks["summary"] = build_summary_block(
                summary, max_sentences, forecast_requested=forecast_requested)
            delivered = [c.text for c in getattr(summary, "claims", []) or []
                         if c.kind in ("FORECAST_PATH", "STRATEGY_HEADLINE")]
            if any(text in blocks["summary"]["text"] for text in delivered):
                shown_in.append(name)
        elif name == ResponseBlock.TABLE.value:
            blocks["table"] = build_table_block(rows, profile, analysis=analysis)
            if forecast_requested and forecast_ready and extend_table_with_forecast(
                    blocks["table"], forecast, scenario):
                shown_in.append(name)
            elif forecast_requested and strategy_done and extend_table_with_category_forecasts(
                    blocks["table"], strategy_result):
                shown_in.append(name)
        elif name == ResponseBlock.CHART.value:
            blocks["chart"] = build_chart_block(chart_spec)
            meta = (chart_spec or {}).get("_meta", {})
            if meta.get("forecast_layered") or meta.get("category_forecasts_layered"):
                shown_in.append(name)

    payload = {
        "response_intent": response_result.to_dict(),
        "blocks_emitted": emitted,
        "blocks_declared": declared,
        **blocks,
    }
    if forecast_requested:
        payload["forecast_notice"] = build_forecast_notice(
            forecast, readiness, summary, shown_in, strategy_result)
    return payload
