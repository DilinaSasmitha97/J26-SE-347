"""
Deterministic classification rules, used when no LLM is configured or the model
returns unusable output. They read the question text only.

Two rules also guard LLM answers (see classifier.py), because the requirements
make them non-negotiable: a declined forecast is never requested, and "only
<format>" returns exactly the named formats.
"""

import re
from typing import List, Optional, Tuple

# --------------------------------------------------------------------------
# Prediction
# --------------------------------------------------------------------------

_FORECAST_WORDS = (
    r"(?:forecasts?|forecasting|forecasted|predictions?|predictive|predict|"
    r"projections?|project|extrapolat\w*)"
)

PREDICTION_DECLINED = re.compile(
    r"\b(?:no|not|without|never|skip|skipping|exclude|excluding|omit|omitting|"
    r"leave out|don'?t|doesn'?t|no need (?:for|to))\s+(?:\w+\s+){0,3}?"
    + _FORECAST_WORDS + r"\b"
)

PREDICTION_REQUESTED = re.compile(
    r"\b(?:forecast\w*|predict\w*|projections?|projected|extrapolat\w*|outlook)\b"
    r"|\bproject\s+(?:the|our|my|future|next|for|forward|ahead|how)\b"
    r"|\bwhat will\b|\bhow (?:many|much)\b(?:\s+\w+){0,4}?\s+will\b"
    r"|\bexpected to\b|\bin the future\b|\bfuture\b|\bgoing forward\b"
)

# --------------------------------------------------------------------------
# Explicitly named formats
# --------------------------------------------------------------------------

# "the employees table" names a database table, not a format, so a table is
# only requested with an indefinite article, "as/in a table", or table wording.
_TABLE_REQUEST = (
    r"\b(?:a|an)\s+(?:\w+\s+)?table\b|\b(?:as|in|into)\s+(?:the\s+)?table\b"
    r"|\btable\s+(?:view|format|form|layout)\b|\btabular\b"
    r"|\btables?\s+(?:and|or|plus)\b|\b(?:and|or|plus)\s+(?:a\s+)?tables?\b"
)

FORMAT_PATTERNS = {
    "table": re.compile(_TABLE_REQUEST),
    "single_value": re.compile(
        r"\bsingle (?:value|number|figure)\b|\bone number\b|\bkpi\b"
        r"|\bjust the (?:number|count|total|figure|value)\b|\bheadline (?:number|figure)\b"
    ),
    "bar_chart": re.compile(
        r"\bbar(?:s|[- ]?(?:charts?|graphs?|plots?))\b|\bcolumn[- ]?(?:charts?|graphs?)\b|\bhistograms?\b"
    ),
    "pie_chart": re.compile(r"\b(?:pie|donut|doughnut)(?:[- ]?(?:charts?|graphs?))?\b"),
    "line_chart": re.compile(r"\bline[- ]?(?:charts?|graphs?|plots?)\b|\btrend[- ]?lines?\b"),
    "summary": re.compile(
        r"\bsummary\b(?!\s+table)|\bsummari[sz](?:e|ed|ing)\b|\boverview\b|\bexplain\w*\b"
        r"|\bexplanation\b|\bdescribe\b|\bnarrative\b|\bwrite[- ]?up\b|\bin words\b|\binsights?\b"
    ),
}

# Exclusions may name a format without the article a request needs ("no table").
_EXCLUDABLE = {**FORMAT_PATTERNS, "table": re.compile(r"\btables?\b|\btabular\b")}

_GENERIC_CHART = re.compile(r"\b(?:charts?|graphs?|plots?|visuali[sz](?:e|ation)s?|diagrams?)\b")
_CHART_TYPES = ("bar_chart", "pie_chart", "line_chart")

_NEGATION = (
    r"\b(?:no|not|without|never|skip|exclude|excluding|omit|leave out|except"
    r"|don'?t (?:show|include|need|want|use)|do not (?:show|include|need|want|use))"
    r"\s+(?:\w+\s+){0,2}?"
)

_ONLY = re.compile(r"\b(?:only|just|solely|exclusively)\b")

# --------------------------------------------------------------------------
# Analytical shape of the question
# --------------------------------------------------------------------------

_TIME_SERIES = re.compile(
    r"\bover time\b|\btrend(?:s|ing)?\b|\btime[- ]series\b|\btimeline\b"
    r"|\b(?:monthly|weekly|daily|yearly|annually|quarterly)\b"
    r"|\b(?:per|by|each|every)\s+(?:day|week|month|quarter|year|date)\b"
    r"|\b(?:month|year|quarter|week)[- ]over[- ](?:month|year|quarter|week)\b"
    r"|\bover the (?:years|months|quarters|weeks)\b"
    r"|\bgrowth\b|\b(?:grow|grew|grown|evolv\w*|evolution)\b"
    r"|\bhow (?:has|have|did)\b(?:\s+\w+){0,6}?\s+chang\w*\b|\bchanges? over\b"
)

_DISTRIBUTION = re.compile(
    r"\bdistribution\b|\bdistributed\b|\bbreak ?down\b|\bbroken down\b|\bshares?\b"
    r"|\bproportions?\b|\bpercentages?\b|\bpercent\b|\bsplit\b|\bcomposition\b"
    r"|\bmake-?up\b|\bratios?\b|\bmix\b"
)
_SCALAR_SHARE = re.compile(r"\bwhat (?:percentage|percent|proportion|share|fraction|ratio)\b")

_COMPARISON = re.compile(
    r"\bcompar\w*\b|\bversus\b|\bvs\b|\branking\b|\brank\b|\b(?:top|bottom) \d+\b"
    r"|\bwhich \w+ (?:has|have|had) the (?:most|fewest|least|highest|lowest|largest|smallest)\b"
    r"|\bdifference between\b"
)

_ORDERING = re.compile(
    r"\b(?:sort|sorted|order|ordered|rank|ranked|arrange|arranged)\s+(?:them\s+)?by\s+\w+"
    r"(?:\s+(?:asc|desc|ascending|descending))?"
)
_GROUPING = re.compile(r"\b(?:by|per|each|every|across|grouped by|broken down by)\s+(?!\d)\w+")

# A forecast phrased as one number ("how many employees will we have next month?").
_SCALAR_FORECAST = re.compile(r"\bhow (?:many|much)\b|\bwhat will (?:the |our |my )?(?:total|average|number|count)\b")

_AGGREGATE = re.compile(
    r"\bhow (?:many|much)\b|\bnumber of\b|\bcount\b|\btotal\b|\bsum\b|\baverage\b|\bavg\b"
    r"|\bmean\b|\bmedian\b|\bmaximum\b|\bminimum\b|\bmax\b|\bmin\b|\bheadcount\b"
)


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("‘", "'")).strip().lower()


def prediction_declined(text: str) -> bool:
    return PREDICTION_DECLINED.search(normalize(text)) is not None


def prediction_needed(text: str) -> bool:
    lowered = normalize(text)
    if PREDICTION_DECLINED.search(lowered):
        return False
    return PREDICTION_REQUESTED.search(lowered) is not None


def _negated(lowered: str, pattern: re.Pattern) -> bool:
    return re.search(_NEGATION + r"(?:" + pattern.pattern + r")", lowered) is not None


def _named_formats(lowered: str) -> Tuple[List[str], List[str], bool]:
    """(requested, excluded, generic_chart_requested); requested in order of appearance."""
    found = []
    excluded = []
    for name, pattern in FORMAT_PATTERNS.items():
        if _negated(lowered, _EXCLUDABLE[name]):
            excluded.append(name)
            continue
        match = pattern.search(lowered)
        if match:
            found.append((match.start(), name))

    # A generic chart word counts only when it is not part of a named chart
    # type, so "no bar chart" does not exclude every chart.
    unnamed = lowered
    for name in _CHART_TYPES:
        unnamed = FORMAT_PATTERNS[name].sub(" ~ ", unnamed)
    generic = False
    if _negated(unnamed, _GENERIC_CHART):
        excluded.extend(name for name in _CHART_TYPES if name not in excluded)
    elif _GENERIC_CHART.search(unnamed):
        generic = True

    requested = [name for _, name in sorted(found) if name not in excluded]
    if any(name in _CHART_TYPES for name in requested):
        generic = False
    return requested, excluded, generic


def explicit_only_formats(text: str) -> Optional[List[str]]:
    """Formats the user restricted the answer to ("show only a pie chart"), else None."""
    lowered = normalize(text)
    if not _ONLY.search(lowered):
        return None
    requested, _, _ = _named_formats(lowered)
    return requested or None


def _shape(lowered: str, predicting: bool) -> str:
    grouped = _GROUPING.search(_ORDERING.sub(" ", lowered)) is not None
    aggregate = _AGGREGATE.search(lowered) is not None

    if _TIME_SERIES.search(lowered):
        return "time"
    if predicting:
        return "scalar_forecast" if _SCALAR_FORECAST.search(lowered) and not grouped else "time"
    if _SCALAR_SHARE.search(lowered) and not grouped:
        return "scalar"
    if _DISTRIBUTION.search(lowered):
        return "distribution"
    if _COMPARISON.search(lowered) or (aggregate and grouped):
        return "comparison"
    if aggregate:
        return "scalar"
    return "records"


_SHAPE_FORMATS = {
    "time": ["table", "line_chart"],
    "scalar_forecast": ["single_value", "line_chart"],
    "distribution": ["table", "pie_chart", "bar_chart"],
    "comparison": ["table", "bar_chart"],
    "scalar": ["single_value"],
    "records": ["table"],
}

# A generic "chart" or "graph" request takes the chart type that suits the shape.
_SHAPE_CHARTS = {
    "time": ["line_chart"],
    "scalar_forecast": ["line_chart"],
    "distribution": ["pie_chart", "bar_chart"],
    "comparison": ["bar_chart"],
    "scalar": ["bar_chart"],
    "records": ["bar_chart"],
}


def classify(text: str) -> Tuple[List[str], bool]:
    """Return (presentation_types, prediction_needed) from the question alone."""
    lowered = normalize(text)
    predicting = prediction_needed(text)
    requested, excluded, generic_chart = _named_formats(lowered)
    shape = _shape(lowered, predicting)

    if requested or generic_chart:
        # Explicit instructions take priority over the shape-based guidance.
        types = list(requested)
        if generic_chart:
            types.extend(name for name in _SHAPE_CHARTS[shape] if name not in types)
    else:
        types = list(_SHAPE_FORMATS[shape])

    types = [name for name in types if name not in excluded]
    if not types:
        types = ["summary"] if "table" in excluded else ["table"]
    return types, predicting
