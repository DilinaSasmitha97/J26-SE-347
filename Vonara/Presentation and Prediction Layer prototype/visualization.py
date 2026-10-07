"""
Part 2 - Adaptive Visualization Layer, plus the Predictive Grammar Extension.

Two responsibilities:

  1. `build_chart`  - choose an encoding from (intent x result profile) and emit
     a valid Vega-Lite v5 specification. Intent alone is not enough: the same
     TREND intent becomes a line over 24 points, a bar over 4, and a KPI card
     over 1. That cardinality-driven re-selection is the "adaptive" claim.

  2. `extend_with_forecast` - take ANY chart the layer produced and layer on
     forecast mean, confidence band, anomaly markers and scenario line, without
     the caller knowing which chart it was. Formal, composable rules over the
     same grammar - the Predictive Visualization Grammar Extension.

No rendering happens here; the layer emits grammar, which the React client
renders. That keeps the contribution declarative and testable.
"""

from schemas import ColumnRole, Granularity, QueryIntent

VEGA_SCHEMA = "https://vega.github.io/schema/vega-lite/v5.json"

# Colour roles kept semantic rather than literal so the frontend theme can
# remap them; values below are the defaults used in the prototype.
COLORS = {
    "historical": "#4C78A8",
    "forecast": "#F58518",
    "band": "#F58518",
    "anomaly": "#D62728",
    "scenario": "#54A24B",
    "threshold": "#B279A2",
}

# Cardinality bands that trigger re-selection of the encoding.
SINGLE_VALUE = 1
FEW_CATEGORIES = 8         # above this, a pie/donut becomes unreadable
MANY_CATEGORIES = 25       # above this, bars must become a ranked top-N
DENSE_SERIES = 60          # above this, points are dropped from a line


def _vl_type(role: str) -> str:
    """Map a semantic column role to a Vega-Lite measurement type."""
    return {
        ColumnRole.TEMPORAL.value: "temporal",
        ColumnRole.MEASURE.value: "quantitative",
        ColumnRole.DIMENSION.value: "nominal",
        ColumnRole.BOOLEAN.value: "nominal",
        ColumnRole.IDENTIFIER.value: "nominal",
    }.get(role, "nominal")


_TIME_UNIT = {
    Granularity.HOUR.value: "yearmonthdatehours",
    Granularity.DAY.value: "yearmonthdate",
    Granularity.WEEK.value: "yearweek",
    Granularity.MONTH.value: "yearmonth",
    Granularity.QUARTER.value: "yearquarter",
    Granularity.YEAR.value: "year",
}


# ==========================================================================
# Encoding selection
# ==========================================================================


def select_encoding(analysis, profile) -> dict:
    """
    Resolve the final chart type from intent AND realised result shape.

    Returns {chart, reason, adapted_from, x, y, color}. `adapted_from` is
    non-empty whenever the profile overrode the intent's default, which is the
    evidence trail the evaluation uses to report adaptation frequency.
    """
    intent = QueryIntent(analysis.primary_intent)
    requested = analysis.recommended_chart
    rows = profile.row_count
    measures = profile.measure_columns
    dimensions = profile.dimension_columns
    temporal = profile.temporal_column

    decision = {
        "chart": requested,
        "reason": analysis.chart_rationale,
        "adapted_from": "",
        "x": "",
        "y": "",
        "color": "",
    }

    def adapt(chart, reason):
        if chart != requested:
            decision["adapted_from"] = requested
        decision["chart"] = chart
        decision["reason"] = reason

    # --- degenerate shapes ---------------------------------------------
    if rows == 0:
        adapt("empty_state", "The query returned no rows; nothing can be encoded.")
        return decision

    if not measures and not temporal:
        adapt("table", "No numeric measure was returned, so only a table is faithful.")
        decision["x"] = ""
        return decision

    if rows == SINGLE_VALUE and len(measures) >= 1:
        adapt(
            "kpi_card",
            "A single row with one measure carries no axis; a KPI card is the "
            "honest encoding.",
        )
        decision["y"] = measures[0]
        return decision

    y = measures[0] if measures else ""
    decision["y"] = y

    # --- temporal shapes ------------------------------------------------
    if temporal and y and intent in (
        QueryIntent.TREND_ANALYSIS,
        QueryIntent.ANOMALY_DETECTION,
        QueryIntent.KPI_SINGLE_VALUE,
    ):
        decision["x"] = temporal
        if rows <= 3:
            adapt("bar", f"Only {rows} time periods: discrete bars read more clearly than a line.")
        elif rows > DENSE_SERIES:
            adapt("line", f"{rows} points: a line with point markers suppressed.")
        else:
            adapt("line", f"{rows} ordered time periods encode naturally as a line.")
        if dimensions and len(dimensions) >= 1 and rows > 3:
            decision["color"] = dimensions[0]
            decision["reason"] += f" Series split by '{dimensions[0]}'."
        return decision

    # --- categorical shapes ---------------------------------------------
    x = dimensions[0] if dimensions else (temporal or (measures[1] if len(measures) > 1 else ""))
    decision["x"] = x

    # build_chart only runs for a CHART block, and guardrail G2 has already
    # found the rows chartable. A data grid here would ship a CHART block the
    # client cannot draw (found in the Stage 7 UI: "show spend by vendor" is a
    # DETAIL_LOOKUP that asks for a chart), so these fall back to bars.
    if intent is QueryIntent.CORRELATION:
        if len(measures) >= 2:
            decision["x"], decision["y"] = measures[0], measures[1]
            adapt("scatter", "Two quantitative measures encode as a scatter plot.")
        elif x and y:
            adapt("bar", f"Correlation needs two numeric measures; only '{y}' was returned, "
                         f"so it is compared across '{x}'.")
        else:
            adapt("table", "Correlation needs two numeric measures; only one was returned.")
        return decision

    if intent is QueryIntent.DISTRIBUTION:
        if y:
            decision["x"] = y
            adapt("histogram", f"Distribution of '{y}' binned across {rows} observations.")
        else:
            adapt("table", "No numeric column to bin.")
        return decision

    if intent is QueryIntent.PROPORTION:
        distinct = _distinct_of(profile, x)
        if distinct and distinct > FEW_CATEGORIES:
            adapt(
                "bar",
                f"{distinct} categories exceed the {FEW_CATEGORIES}-slice legibility "
                "limit for part-to-whole marks; a sorted bar preserves comparison.",
            )
        else:
            adapt("donut", f"{distinct or rows} categories encode as part-to-whole slices.")
        return decision

    if intent is QueryIntent.RANKING:
        adapt("bar", f"Ranked comparison across {rows} entities, sorted by '{y}'.")
        if rows > MANY_CATEGORIES:
            decision["reason"] += (
                f" Truncated to the top {MANY_CATEGORIES} to stay readable."
            )
        return decision

    if intent is QueryIntent.COMPARISON:
        if len(dimensions) >= 2:
            decision["color"] = dimensions[1]
            adapt("grouped_bar", f"Two dimensions present: grouped by '{dimensions[1]}'.")
        elif rows > MANY_CATEGORIES:
            adapt("bar", f"{rows} categories: rendered as a sorted, truncated bar chart.")
        else:
            adapt("bar", f"Measure compared across {rows} categories.")
        return decision

    if intent is QueryIntent.DETAIL_LOOKUP:
        if x and y:
            adapt("bar", f"Row-level values asked for as a chart: '{y}' compared across {rows} rows of '{x}'.")
        else:
            adapt("table", "Row-level retrieval is presented as a table, not a chart.")
        return decision

    adapt("bar" if x and y else "table", "Default encoding for the resolved shape.")
    return decision


def _distinct_of(profile, column: str):
    col = profile.column(column) if column else None
    return col.distinct_count if col else None


# ==========================================================================
# Base chart construction
# ==========================================================================


def _base(title: str, rows: list) -> dict:
    return {
        "$schema": VEGA_SCHEMA,
        "title": title,
        "data": {"values": rows},
        "width": "container",
        "height": 320,
        "autosize": {"type": "fit", "contains": "padding"},
    }


def _x_encoding(field: str, profile, granularity: str = None) -> dict:
    col = profile.column(field)
    role = col.role if col else ColumnRole.DIMENSION.value
    enc = {"field": field, "type": _vl_type(role), "title": _humanize(field)}
    if enc["type"] == "temporal":
        unit = _TIME_UNIT.get(granularity or profile.granularity)
        if unit:
            enc["timeUnit"] = unit
    return enc


def _y_encoding(field: str, profile, aggregate: str = None) -> dict:
    enc = {"field": field, "type": "quantitative", "title": _humanize(field)}
    if aggregate:
        enc["aggregate"] = aggregate.lower()
    return enc


def _humanize(name: str) -> str:
    return (name or "").replace("_", " ").strip().title()


def build_chart(analysis, profile, rows: list, title: str = None) -> dict:
    """
    Emit a Vega-Lite v5 spec for the historical result set.

    The returned dict always carries a `_meta` key describing how the encoding
    was chosen; `extend_with_forecast` reads it, and the evaluation harness uses
    it to audit adaptation decisions.
    """
    decision = select_encoding(analysis, profile)
    chart = decision["chart"]
    x, y, color = decision["x"], decision["y"], decision["color"]
    title = title or _humanize(analysis.normalized_query[:80]) or "Query Result"

    spec = _base(title, rows)
    spec["_meta"] = {
        "chart_type": chart,
        "selection_reason": decision["reason"],
        "adapted_from_intent_default": decision["adapted_from"],
        "intent": analysis.primary_intent,
        "row_count": profile.row_count,
        "x_field": x,
        "y_field": y,
        "color_field": color,
        "forecast_layered": False,
    }

    if chart == "empty_state":
        spec["mark"] = {"type": "text", "text": "No data returned for this query."}
        spec["encoding"] = {}
        return spec

    if chart == "table":
        # Vega-Lite has no table mark; emit an explicit tabular contract that
        # the frontend renders as a data grid.
        spec.pop("mark", None)
        spec["_meta"]["render_as"] = "data_grid"
        spec["_meta"]["columns"] = [c.name for c in profile.columns]
        spec["encoding"] = {}
        return spec

    if chart == "kpi_card":
        spec["_meta"]["render_as"] = "kpi_card"
        spec["mark"] = {"type": "text", "fontSize": 42, "fontWeight": "bold"}
        spec["encoding"] = {
            "text": {"field": y, "type": "quantitative", "format": ",.2f"}
        }
        spec["height"] = 140
        return spec

    if chart == "histogram":
        spec["mark"] = {"type": "bar", "color": COLORS["historical"], "tooltip": True}
        spec["encoding"] = {
            "x": {"field": x, "type": "quantitative", "bin": {"maxbins": 20},
                  "title": _humanize(x)},
            "y": {"aggregate": "count", "type": "quantitative", "title": "Frequency"},
        }
        return spec

    if chart == "scatter":
        spec["mark"] = {"type": "point", "filled": True, "size": 70,
                        "color": COLORS["historical"], "tooltip": True}
        spec["encoding"] = {
            "x": {"field": x, "type": "quantitative", "title": _humanize(x),
                  "scale": {"zero": False}},
            "y": {"field": y, "type": "quantitative", "title": _humanize(y),
                  "scale": {"zero": False}},
        }
        if color:
            spec["encoding"]["color"] = {"field": color, "type": "nominal"}
        return spec

    if chart in ("pie", "donut"):
        spec["mark"] = {
            "type": "arc",
            "tooltip": True,
            "innerRadius": 70 if chart == "donut" else 0,
        }
        spec["encoding"] = {
            "theta": {"field": y, "type": "quantitative", "stack": "normalize"},
            "color": {"field": x, "type": "nominal", "title": _humanize(x)},
        }
        spec.pop("width", None)
        spec["height"] = 300
        return spec

    if chart in ("bar", "grouped_bar"):
        spec["mark"] = {"type": "bar", "tooltip": True,
                        "color": None if color else COLORS["historical"]}
        if spec["mark"]["color"] is None:
            spec["mark"].pop("color")
        encoding = {
            "x": _x_encoding(x, profile),
            "y": _y_encoding(y, profile),
        }
        if analysis.primary_intent == QueryIntent.RANKING.value:
            encoding["x"]["sort"] = {"field": y, "order": "descending"}
        if color:
            encoding["color"] = {"field": color, "type": "nominal", "title": _humanize(color)}
            encoding["xOffset"] = {"field": color}
        spec["encoding"] = encoding
        return spec

    if chart == "area":
        spec["mark"] = {"type": "area", "opacity": 0.7, "color": COLORS["historical"],
                        "tooltip": True}
        spec["encoding"] = {"x": _x_encoding(x, profile), "y": _y_encoding(y, profile)}
        return spec

    # line (default temporal encoding)
    spec["mark"] = {
        "type": "line",
        "point": profile.row_count <= DENSE_SERIES,
        "color": None if color else COLORS["historical"],
        "tooltip": True,
    }
    if spec["mark"]["color"] is None:
        spec["mark"].pop("color")
    spec["encoding"] = {"x": _x_encoding(x, profile), "y": _y_encoding(y, profile)}
    if color:
        spec["encoding"]["color"] = {"field": color, "type": "nominal",
                                     "title": _humanize(color)}
    return spec


# ==========================================================================
# Predictive Visualization Grammar Extension
# ==========================================================================

# The extension is defined by four composable rules. Each takes the base spec
# plus one prediction artefact and returns a new layer. Because every rule
# emits an independent layer keyed on the SAME x/y fields, they compose in any
# combination without the base chart needing to know about prediction.
EXTENSION_RULES = [
    "R1_FORECAST_MEAN      - dashed continuation of the historical mark",
    "R2_CONFIDENCE_BAND    - area mark between lower and upper bounds",
    "R3_ANOMALY_MARKERS    - point + rule marks at breaching observations",
    "R4_SCENARIO_OVERLAY   - second dashed line for the simulated path",
    "R5_CATEGORY_FORECASTS - one dashed line + band per category, coloured like its series",
]

# Charts whose grammar admits a forecast continuation. A pie has no time axis,
# so R1-R4 are undefined on it - the extension declares this explicitly rather
# than producing a nonsensical layer.
EXTENDABLE_CHARTS = {"line", "area", "bar"}


def extend_with_forecast(
    spec: dict,
    forecast=None,
    anomaly_report=None,
    scenario=None,
    strategy_result=None,
) -> dict:
    """
    Apply the grammar extension rules to a base chart.

    Returns a new layered spec. When the base chart cannot carry a forecast,
    the original spec is returned with `_meta.forecast_layered = False` and a
    stated reason, so the frontend can render a separate forecast panel instead.
    """
    base_chart = spec.get("_meta", {}).get("chart_type", "")
    x_field = spec.get("_meta", {}).get("x_field", "")
    y_field = spec.get("_meta", {}).get("y_field", "")

    has_forecast = forecast is not None and getattr(forecast, "generated", False)
    has_anomalies = anomaly_report is not None and getattr(anomaly_report, "evaluated", False)
    has_scenario = scenario is not None and getattr(scenario, "simulated", False)
    details = getattr(strategy_result, "details", None) or {}
    categories = details.get("categories") or details.get("categories_forecast") or []
    color_field = spec.get("_meta", {}).get("color_field", "")
    has_categories = (
        bool(categories) and getattr(strategy_result, "executed", False)
        and color_field and color_field == details.get("group_column")
    )

    if not (has_forecast or has_anomalies or has_scenario or has_categories):
        spec.setdefault("_meta", {})["forecast_layered"] = False
        spec["_meta"]["extension_skipped_reason"] = "No prediction artefacts to layer."
        return spec

    if base_chart not in EXTENDABLE_CHARTS:
        spec.setdefault("_meta", {})["forecast_layered"] = False
        spec["_meta"]["extension_skipped_reason"] = (
            f"Chart type '{base_chart}' has no continuous axis; forecast is "
            "delivered as a separate panel."
        )
        return spec

    base_rows = spec.get("data", {}).get("values", [])
    base_encoding = spec.get("encoding", {})
    base_mark = spec.get("mark", {})
    applied = []

    # Historical layer, carried over unchanged.
    layers = [
        {
            "data": {"values": base_rows},
            "mark": base_mark,
            "encoding": base_encoding,
        }
    ]

    if has_forecast:
        # Bridge row: the last historical observation is repeated as the first
        # forecast point so the dashed line joins the solid one with no gap.
        bridge = []
        if forecast.historical_dates and forecast.historical_values:
            bridge.append(
                {
                    x_field: forecast.historical_dates[-1],
                    "forecast": forecast.historical_values[-1],
                    "lower_bound": forecast.historical_values[-1],
                    "upper_bound": forecast.historical_values[-1],
                    "segment": "bridge",
                }
            )
        forecast_rows = bridge + [
            {
                x_field: p.timestamp,
                "forecast": p.predicted,
                "lower_bound": p.lower_bound,
                "upper_bound": p.upper_bound,
                "label": p.label,
                "segment": "forecast",
            }
            for p in forecast.points
        ]

        # R2 first so the band renders beneath the mean line.
        layers.append(
            {
                "data": {"values": forecast_rows},
                "mark": {"type": "area", "opacity": 0.18, "color": COLORS["band"],
                         "tooltip": True},
                "encoding": {
                    "x": dict(base_encoding.get("x", {}), field=x_field),
                    "y": {"field": "lower_bound", "type": "quantitative",
                          "title": _humanize(y_field)},
                    "y2": {"field": "upper_bound"},
                },
            }
        )
        applied.append("R2_CONFIDENCE_BAND")

        layers.append(
            {
                "data": {"values": forecast_rows},
                "mark": {
                    "type": "line",
                    "strokeDash": [6, 4],
                    "color": COLORS["forecast"],
                    "point": True,
                    "tooltip": True,
                },
                "encoding": {
                    "x": dict(base_encoding.get("x", {}), field=x_field),
                    "y": {"field": "forecast", "type": "quantitative",
                          "title": _humanize(y_field)},
                },
            }
        )
        applied.append("R1_FORECAST_MEAN")

    if has_anomalies:
        anomaly_rows = []
        for a in anomaly_report.historical_anomalies:
            anomaly_rows.append(
                {x_field: a.label, "value": a.value, "dimension": "HISTORICAL",
                 "severity": a.severity, "direction": a.direction}
            )
        if has_forecast:
            fc_by_label = {p.label: p.timestamp for p in forecast.points}
            for a in anomaly_report.predictive_warnings:
                anomaly_rows.append(
                    {x_field: fc_by_label.get(a.label, a.label), "value": a.value,
                     "dimension": "PREDICTIVE", "severity": a.severity,
                     "direction": a.direction}
                )

        if anomaly_rows:
            layers.append(
                {
                    "data": {"values": anomaly_rows},
                    "mark": {"type": "point", "filled": True, "size": 150,
                             "shape": "triangle-up", "color": COLORS["anomaly"],
                             "tooltip": True},
                    "encoding": {
                        "x": dict(base_encoding.get("x", {}), field=x_field),
                        "y": {"field": "value", "type": "quantitative"},
                        # Explicit shapes: without a scale the encoding
                        # overrode the mark's triangle with Vega's default
                        # circle (Stage 7, seen in the rendered UI).
                        "shape": {"field": "dimension", "type": "nominal",
                                  "scale": {"domain": ["HISTORICAL", "PREDICTIVE"],
                                            "range": ["triangle-up", "diamond"]},
                                  "legend": {"title": "Anomaly"}},
                    },
                }
            )
            applied.append("R3_ANOMALY_MARKERS")

        # Threshold reference lines make the adaptive band visible, which is
        # what distinguishes this from an unexplained red dot. They are only
        # drawable when the band lives in the same space as the plotted values:
        # after detrending the fence is centred on the residual, so a flat rule
        # at those levels would be actively misleading. The same holds in the
        # STL seasonal space added in Stage 3; this guard missed it until the
        # Stage 7 UI drew a seasonal series with "normal range" lines at about
        # +/-2,700 on an axis of monthly totals near 20,000.
        if not (getattr(anomaly_report, "detrended", False)
                or getattr(anomaly_report, "seasonal", False)):
            bounds = [{"threshold": anomaly_report.upper_threshold, "bound": "upper"}]
            # A lower fence below zero on a measure that is never negative
            # rules nothing out; drawing it only stretched the axis below zero.
            if not (anomaly_report.lower_threshold < 0 <= anomaly_report.q1):
                bounds.append({"threshold": anomaly_report.lower_threshold, "bound": "lower"})
            layers.append(
                {
                    "data": {"values": bounds},
                    "mark": {"type": "rule", "strokeDash": [3, 3],
                             "color": COLORS["threshold"], "opacity": 0.7},
                    "encoding": {"y": {"field": "threshold", "type": "quantitative"}},
                }
            )
            applied.append("R3_THRESHOLD_RULES")

    if has_scenario:
        scenario_rows = [
            {x_field: p["timestamp"], "scenario": p["predicted"], "label": p["label"]}
            for p in scenario.scenario_points
        ]
        layers.append(
            {
                "data": {"values": scenario_rows},
                "mark": {"type": "line", "strokeDash": [2, 3], "point": True,
                         "color": COLORS["scenario"], "tooltip": True},
                "encoding": {
                    "x": dict(base_encoding.get("x", {}), field=x_field),
                    "y": {"field": "scenario", "type": "quantitative",
                          "title": _humanize(y_field)},
                },
            }
        )
        applied.append("R4_SCENARIO_OVERLAY")

    if has_categories:
        # One band + one dashed line per category, coloured by the same field
        # as the historical series so each forecast reads as its continuation.
        category_rows = []
        for c in categories:
            for p in c["points"]:
                category_rows.append({
                    x_field: p["timestamp"] or p["label"], color_field: c["category"],
                    "forecast": p["predicted"], "lower_bound": p["lower"],
                    "upper_bound": p["upper"], "label": p["label"],
                })
        x_enc = dict(base_encoding.get("x", {}), field=x_field)
        color_enc = {"field": color_field, "type": "nominal"}
        layers.append({
            "data": {"values": category_rows},
            "mark": {"type": "area", "opacity": 0.12, "tooltip": True},
            "encoding": {"x": x_enc, "color": color_enc,
                         "y": {"field": "lower_bound", "type": "quantitative"},
                         "y2": {"field": "upper_bound"}},
        })
        layers.append({
            "data": {"values": category_rows},
            "mark": {"type": "line", "strokeDash": [6, 4], "point": True, "tooltip": True},
            "encoding": {"x": x_enc, "color": color_enc,
                         "y": {"field": "forecast", "type": "quantitative",
                               "title": _humanize(y_field)}},
        })
        applied.append("R5_CATEGORY_FORECASTS")

    extended = {
        "$schema": VEGA_SCHEMA,
        "title": spec.get("title", ""),
        "width": "container",
        "height": spec.get("height", 320),
        "autosize": {"type": "fit", "contains": "padding"},
        "resolve": {"scale": {"y": "shared", "x": "shared"}},
        "layer": layers,
        "_meta": dict(spec.get("_meta", {})),
    }
    extended["_meta"].update(
        {
            "forecast_layered": has_forecast,
            "category_forecasts_layered": bool(has_categories),
            "extension_rules_applied": applied,
            "layer_count": len(layers),
        }
    )
    return extended
