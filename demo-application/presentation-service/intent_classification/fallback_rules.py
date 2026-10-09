"""
Rule-based presentation types with confidence, plus the hard guards.

Formats come from one of two places, read from the question text only:
  * formats the user names ("as a pie chart", "a table")   -> confidence 0.95
  * otherwise the formats that suit the rule intent        -> the intent's confidence

The guards apply to every answer, whichever source produced it, because the
requirements make them non-negotiable: a declined forecast is never requested,
"only <format>" returns exactly the named formats, and an excluded format
("no table") is never returned.
"""

import re
from typing import List, Optional, Tuple

EXPLICIT_FORMAT_CONFIDENCE = 0.95

# --------------------------------------------------------------------------
# Prediction decline (hard guard)
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
# Formats by intent
# --------------------------------------------------------------------------

INTENT_FORMATS = {
    "TREND_ANALYSIS": ["table", "line_chart"],
    "ANOMALY_DETECTION": ["table", "line_chart"],
    "COMPARISON": ["table", "bar_chart"],
    "RANKING": ["table", "bar_chart"],
    "DISTRIBUTION": ["table", "bar_chart"],
    "PROPORTION": ["table", "pie_chart", "bar_chart"],
    "CORRELATION": ["table", "summary"],
    "KPI_SINGLE_VALUE": ["single_value"],
    "DETAIL_LOOKUP": ["table"],
}

# Formats that can sensibly show each intent. Used to drop suggestions that do
# not fit the final intent (a pie chart for a trend). table and summary fit all.
_COMPATIBLE_EXTRA = {
    "TREND_ANALYSIS": {"line_chart", "bar_chart"},
    "ANOMALY_DETECTION": {"line_chart", "bar_chart"},
    "COMPARISON": {"bar_chart"},
    "RANKING": {"bar_chart"},
    "DISTRIBUTION": {"bar_chart"},
    "PROPORTION": {"pie_chart", "bar_chart"},
    "CORRELATION": set(),
    "KPI_SINGLE_VALUE": {"single_value", "bar_chart"},
    "DETAIL_LOOKUP": set(),
}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'").replace("‘", "'")).strip().lower()


def prediction_declined(text: str) -> bool:
    return PREDICTION_DECLINED.search(normalize(text)) is not None


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


def excluded_formats(text: str) -> List[str]:
    return _named_formats(normalize(text))[1]


def explicit_only_formats(text: str) -> Optional[List[str]]:
    """Formats the user restricted the answer to ("show only a pie chart"), else None."""
    lowered = normalize(text)
    if not _ONLY.search(lowered):
        return None
    requested, _, _ = _named_formats(lowered)
    return requested or None


def default_formats(intent: str) -> List[str]:
    return list(INTENT_FORMATS.get(intent, ["table"]))


def rule_presentation_types(text: str, intent: str, intent_confidence: float) -> Tuple[List[str], float, bool]:
    """
    Return (presentation_types, confidence, named_by_user).

    Formats the user names are taken as given (0.95). A summary word on its own
    adds `summary` to the intent's formats, and a generic "chart" picks the
    chart types that suit the intent; in both cases the formats still depend on
    the intent, so they carry the intent's confidence.
    """
    lowered = normalize(text)
    requested, excluded, generic_chart = _named_formats(lowered)
    defaults = default_formats(intent)

    named = [name for name in requested if name != "summary"]
    if named:
        types, confidence, by_user = list(requested), EXPLICIT_FORMAT_CONFIDENCE, True
    elif generic_chart:
        charts = [name for name in defaults if name in _CHART_TYPES] or ["bar_chart"]
        types, confidence, by_user = charts + [n for n in requested if n not in charts], intent_confidence, False
    else:
        types = defaults + [n for n in requested if n not in defaults]
        confidence, by_user = intent_confidence, False

    types = [name for name in types if name not in excluded]
    if not types:
        types = ["summary"] if "table" in excluded else ["table"]
    return types, round(confidence, 4), by_user


def fit_to_intent(types: List[str], intent: str) -> List[str]:
    """Drop formats that cannot show the intent; fall back to the intent's formats."""
    allowed = {"table", "summary"} | _COMPATIBLE_EXTRA.get(intent, set())
    kept = [name for name in types if name in allowed]
    return kept or default_formats(intent)
