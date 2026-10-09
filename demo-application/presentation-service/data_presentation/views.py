"""
Build the presentation views for one executed, PII-masked result.

One view per presentation type the intent classifier recommended, in its
order. A view the rows cannot support stays in the list with `available:
false` and a reason, so the user sees why a recommended format is missing.
Without a classification, formats are chosen from the shape of the data.

No forecasting, anomaly or what-if code runs here.
"""

import os
from types import SimpleNamespace
from typing import List, Optional

import input_adapter
import llm
import response_renderer
import summarization
from profiler import log_step
from result_profiler import coerce_measures, profile_results

from . import charts

PRESENTATION_TYPES = ("table", "single_value", "bar_chart", "pie_chart", "line_chart", "summary")

LABELS = {
    "table": "Table",
    "single_value": "Single value",
    "bar_chart": "Bar chart",
    "pie_chart": "Pie chart",
    "line_chart": "Line chart",
    "summary": "Summary",
}


def llm_summary_enabled() -> bool:
    """AI-written summaries are on unless PRESENTATION_LLM_SUMMARY=false; they need a key."""
    return os.getenv("PRESENTATION_LLM_SUMMARY", "true").lower() != "false" and llm.is_available()


def _view(kind: str, block: Optional[dict] = None, reason: str = "", notes: List[str] = None) -> dict:
    return {
        "type": kind,
        "label": LABELS[kind],
        "available": block is not None,
        "reason": "" if block is not None else reason,
        "notes": notes or [],
        "block": block,
    }


def _table_view(rows, profile, adapted) -> dict:
    block = response_renderer.build_table_block(rows, profile)
    if not block["columns"]:
        block["columns"] = [{"name": name, "label": charts._humanize(name), "role": "UNSUPPORTED",
                             "type": "string", "align": "left", "null_count": 0}
                            for name in adapted.columns]
    for column in block["columns"]:
        column["masked"] = column["name"] in adapted.masked_columns
    notes = []
    if adapted.truncated:
        notes.append(f"The database returned more rows than were delivered; showing "
                     f"{adapted.rows_received} of {adapted.row_count}.")
    if block["truncated"]:
        notes.append(f"Showing the first {block['rows_returned']} of {block['row_count']} rows.")
    return _view("table", block, notes=notes)


def _single_value_view(rows, profile) -> dict:
    if not rows:
        return _view("single_value", reason="No rows were returned.")
    if len(rows) > 1:
        return _view("single_value", reason=f"The result has {len(rows)} rows; a single value needs exactly one.")
    block = response_renderer.build_answer_block(rows, profile, None)
    value = block.get("value")
    if isinstance(value, int) and not isinstance(value, bool):
        block["display_value"] = f"{value:,}"  # a count reads 93, not 93.00
    return _view("single_value", block)


def _chart_view(kind, builder, rows, profile, question) -> dict:
    spec, reason, notes = builder(rows, profile, question)
    return _view(kind, {"spec": spec} if spec else None, reason, notes)


def _summary_view(rows, profile, intent) -> dict:
    if not rows:
        return _view("summary", reason="No rows were returned to summarise.")
    analysis = SimpleNamespace(primary_intent=intent or "")
    summary = summarization.summarize(profile, rows, analysis, use_llm=llm_summary_enabled())
    block = summary.to_dict()
    block.pop("rejected_narration", None)  # audit only; never shown as the summary
    return _view("summary", block)


def choose_from_data(rows, profile) -> List[str]:
    """Formats for a result that was not classified (Continue without classification)."""
    if len(rows) == 1 and len(profile.columns) <= 2 and profile.measure_columns:
        return ["single_value"]
    if profile.is_time_series and profile.temporal_column:
        return ["table", "line_chart"]
    if profile.measure_columns and charts.category_columns(profile):
        types = ["table", "bar_chart"]
        pie, _, _ = charts.pie_spec(rows, profile)
        return types + (["pie_chart"] if pie else [])
    return ["table"]


def build_views(result, intent: Optional[str] = None, presentation_types: Optional[list] = None,
                question: str = "") -> dict:
    adapted = input_adapter.adapt_result(result)
    profile = profile_results(adapted.rows)
    rows = coerce_measures(adapted.rows, profile)

    source = "classification" if presentation_types else "data"
    types = list(presentation_types) if presentation_types else choose_from_data(rows, profile)

    builders = {
        "table": lambda: _table_view(rows, profile, adapted),
        "single_value": lambda: _single_value_view(rows, profile),
        "bar_chart": lambda: _chart_view("bar_chart", charts.bar_spec, rows, profile, question),
        "pie_chart": lambda: _chart_view("pie_chart", charts.pie_spec, rows, profile, question),
        "line_chart": lambda: _chart_view("line_chart", charts.line_spec, rows, profile, question),
        "summary": lambda: _summary_view(rows, profile, intent),
    }
    views = [builders[kind]() for kind in types]

    summary = next((v for v in views if v["type"] == "summary" and v["available"]), None)
    log_step(
        "Presentation rendered | source=" + source
        + f" | intent={intent or '-'} | rows={len(rows)}"
        + " | available=" + str([v["type"] for v in views if v["available"]])
        + " | unavailable=" + str({v["type"]: v["reason"] for v in views if not v["available"]})
        + (f" | summary={summary['block']['mode']}" if summary else "")
    )
    return {
        "status": "SUCCESS",
        "source": source,
        "intent": intent,
        "row_count": adapted.row_count,
        "rows_received": adapted.rows_received,
        "masked_columns": adapted.masked_columns,
        "views": views,
    }
