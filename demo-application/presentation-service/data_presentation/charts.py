"""
Vega-Lite v5 specs for the chart formats the intent classifier recommends.

Unlike visualization.build_chart, which picks its own chart type from the old
analyzer's intent, each builder here draws exactly the requested type, or says
why the returned rows cannot support it. Every builder returns
(spec_or_None, reason, notes).

Specs carry only the plotted fields, already masked upstream, with measures as
numbers and time values as ISO dates (a plain 2015 would otherwise be read by
Vega-Lite as milliseconds after 1970).
"""

from typing import List, Optional, Tuple

from result_profiler import parse_date, parse_number
from schemas import ColumnRole
from visualization import (
    COLORS,
    FEW_CATEGORIES,
    MANY_CATEGORIES,
    _base,
    _humanize,
    _x_encoding,
    _y_encoding,
)

ChartResult = Tuple[Optional[dict], str, List[str]]


# --------------------------------------------------------------------------
# Axis selection
# --------------------------------------------------------------------------


def category_columns(profile) -> List[str]:
    """Columns usable as a category axis, best first: dimensions, then keys, then flags."""
    order = (ColumnRole.DIMENSION.value, ColumnRole.IDENTIFIER.value, ColumnRole.BOOLEAN.value)
    columns = []
    for role in order:
        columns += [c.name for c in profile.columns
                    if c.role == role and c.name != profile.temporal_column and c.name not in columns]
    return columns


def measure_column(profile) -> str:
    return profile.measure_columns[0] if profile.measure_columns else ""


def _time_value(value):
    parsed = parse_date(value)
    return parsed.date().isoformat() if parsed else value


def _plot_rows(rows: list, fields: List[str], temporal: str = "") -> list:
    """Keep only the plotted fields; convert the time field to ISO dates."""
    out = []
    for row in rows:
        point = {field: row.get(field) for field in fields if field}
        if temporal and temporal in point:
            point[temporal] = _time_value(point[temporal])
        out.append(point)
    return out


def _sum_by(rows: list, key: str, measure: str) -> Tuple[list, bool]:
    """Sum the measure per category, keeping first-seen order. Returns (rows, aggregated)."""
    totals, order = {}, []
    for row in rows:
        category = row.get(key)
        value = parse_number(row.get(measure))
        if category not in totals:
            totals[category] = 0.0
            order.append(category)
        if value is not None:
            totals[category] += value
    aggregated = len(order) < len(rows)
    return [{key: c, measure: _tidy(totals[c])} for c in order], aggregated


def _tidy(number: float):
    return int(number) if float(number).is_integer() else round(number, 6)


def _title(question: str, description: str) -> str:
    """A short title naming what is plotted; the question is shown elsewhere and
    is often too long for a chart (it was clipped in the browser)."""
    return description


# --------------------------------------------------------------------------
# Bar chart
# --------------------------------------------------------------------------


def bar_spec(rows: list, profile, question: str = "") -> ChartResult:
    measure = measure_column(profile)
    if not rows:
        return None, "No rows to plot.", []
    if not measure:
        return None, "The result has no numeric column to plot.", []

    categories = category_columns(profile)
    temporal = profile.temporal_column
    notes: List[str] = []

    if categories:
        x, x_is_time = categories[0], False
    elif temporal:
        x, x_is_time = temporal, True
    else:
        return None, "The result has no category or date column to put on the axis.", []

    color = ""
    if x_is_time and profile.layout == "GROUPED" and profile.group_column:
        color = profile.group_column
    elif not x_is_time and len(categories) > 1 and categories[1] != x:
        color = categories[1]

    data = _plot_rows(rows, [x, measure, color], temporal if x_is_time else "")
    if not color and not x_is_time:
        data, aggregated = _sum_by(data, x, measure)
        if aggregated:
            notes.append(f"{_humanize(measure)} is summed per {_humanize(x).lower()}.")
        if len(data) > MANY_CATEGORIES:
            data = sorted(data, key=lambda r: -(parse_number(r.get(measure)) or 0))[:MANY_CATEGORIES]
            notes.append(f"Showing the top {MANY_CATEGORIES} of {len({r.get(x) for r in rows})} "
                         f"{_humanize(x).lower()} values by {_humanize(measure).lower()}.")

    spec = _base(_title(question, f"{_humanize(measure)} by {_humanize(x)}"), data)
    spec["mark"] = {"type": "bar", "tooltip": True}
    if not color:
        spec["mark"]["color"] = COLORS["historical"]
    x_enc = _x_encoding(x, profile)
    if not x_is_time:
        x_enc["type"] = "nominal"
        x_enc["sort"] = None  # keep the SQL's ORDER BY
        x_enc["axis"] = {"labelAngle": -40 if len(data) > 6 else 0}
    spec["encoding"] = {"x": x_enc, "y": _y_encoding(measure, profile)}
    if color:
        spec["encoding"]["color"] = {"field": color, "type": "nominal", "title": _humanize(color)}
        if not x_is_time:
            spec["encoding"]["xOffset"] = {"field": color}
    if len(profile.measure_columns) > 1:
        notes.append(f"Charted {_humanize(measure).lower()}; other numeric columns are in the table.")
    return spec, "", notes


# --------------------------------------------------------------------------
# Pie chart
# --------------------------------------------------------------------------


def pie_spec(rows: list, profile, question: str = "") -> ChartResult:
    measure = measure_column(profile)
    if not rows:
        return None, "No rows to plot.", []
    if not measure:
        return None, "The result has no numeric column to size the slices.", []
    categories = category_columns(profile)
    if not categories:
        return None, "The result has no category column to split into slices.", []

    x = categories[0]
    data, aggregated = _sum_by(_plot_rows(rows, [x, measure]), x, measure)
    values = [parse_number(r.get(measure)) or 0 for r in data]
    if len(data) < 2:
        return None, "Only one category was returned; a pie chart needs at least two.", []
    if len(data) > FEW_CATEGORIES:
        return None, (f"{len(data)} categories were returned; a pie chart stays readable "
                      f"up to {FEW_CATEGORIES}. Use the bar chart instead."), []
    if any(v < 0 for v in values):
        return None, "Some values are negative, which cannot form slices of a whole.", []
    if sum(values) <= 0:
        return None, "All values are zero, so there is no whole to divide.", []

    notes = []
    if aggregated or len(categories) > 1:
        notes.append(f"{_humanize(measure)} is summed per {_humanize(x).lower()}.")
    spec = _base(_title(question, f"Share of {_humanize(measure)} by {_humanize(x)}"), data)
    spec["height"] = 300
    spec["mark"] = {"type": "arc", "tooltip": True, "innerRadius": 0}
    spec["encoding"] = {
        "theta": {"field": measure, "type": "quantitative", "stack": True, "title": _humanize(measure)},
        "color": {"field": x, "type": "nominal", "title": _humanize(x), "sort": None},
        "tooltip": [
            {"field": x, "type": "nominal", "title": _humanize(x)},
            {"field": measure, "type": "quantitative", "title": _humanize(measure)},
        ],
    }
    return spec, "", notes


# --------------------------------------------------------------------------
# Line chart
# --------------------------------------------------------------------------


def line_spec(rows: list, profile, question: str = "") -> ChartResult:
    measure = measure_column(profile)
    temporal = profile.temporal_column
    if not rows:
        return None, "No rows to plot.", []
    if not measure:
        return None, "The result has no numeric column to draw.", []
    if not temporal:
        return None, "The result has no date or period column to draw over time.", []
    points = {row.get(temporal) for row in rows}
    if len(points) < 2:
        return None, "Only one period was returned; a line needs at least two.", []

    color = profile.group_column if profile.layout == "GROUPED" and profile.group_column else ""
    column = profile.column(temporal)
    is_date = column is not None and column.role == ColumnRole.TEMPORAL.value
    data = _plot_rows(rows, [temporal, measure, color], temporal if is_date else "")

    notes = []
    if not color and len(points) < len(rows):
        notes.append(f"Several rows share a period; {_humanize(measure).lower()} is summed per period.")

    spec = _base(_title(question, f"{_humanize(measure)} over time"), data)
    spec["mark"] = {"type": "line", "point": len(points) <= 60, "tooltip": True}
    if not color:
        spec["mark"]["color"] = COLORS["historical"]
    x_enc = _x_encoding(temporal, profile)
    if not is_date:
        x_enc["type"] = "ordinal"
        x_enc["sort"] = None
    y_enc = _y_encoding(measure, profile, aggregate="sum" if not color and len(points) < len(rows) else None)
    spec["encoding"] = {"x": x_enc, "y": y_enc}
    if color:
        spec["encoding"]["color"] = {"field": color, "type": "nominal", "title": _humanize(color)}
    return spec, "", notes
