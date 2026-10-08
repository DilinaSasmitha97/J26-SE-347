"""
Query Understanding Engine  -  Part 1 of Component 4.

Takes (natural-language question, database schema, optional security context)
and returns one comprehensive `QueryAnalysis`: the classified intent, whether a
prediction is wanted and over what horizon, which tables and columns the request
touches, the semantic roles of those columns, and a recommended visual encoding.

ARCHITECTURE - hybrid, deterministic-first
------------------------------------------
Two independent analysers run and are then merged:

  A. RULE ENGINE  (`_rule_analysis`)   - lexical/morphological evidence scoring
     over a curated marker lexicon, plus exact/fuzzy schema binding. Runs with
     zero network calls, is fully reproducible, and defines the floor accuracy.

  B. LLM ENGINE   (`_llm_analysis`)    - structured JSON extraction, better at
     paraphrase, ellipsis and multi-clause questions.

`analyze()` merges them under an explicit arbitration policy (`_merge`):
the LLM wins on intent only when it is confident AND its answer is schema-valid;
the rule engine always wins on anything security-relevant (PII flags, injection
markers) and on any field the LLM left outside the closed vocabulary. This makes
the component fail *closed* and keeps every metric reproducible offline.
"""

import re
import time
from difflib import SequenceMatcher

import llm
import response_intent
import scenario_language
from profiler import log_step
from prompts import SYSTEM_PROMPT, build_analysis_prompt
from schemas import (
    ALL_INTENTS,
    ALL_RESPONSE_INTENTS,
    ColumnBinding,
    ColumnRole,
    Granularity,
    HorizonSpec,
    MetricSpec,
    QueryAnalysis,
    QueryIntent,
    RESPONSE_BLOCKS,
    ResponseIntent,
    TableBinding,
    WhatIfSpec,
)

# ==========================================================================
# Lexicons
# ==========================================================================

# Weighted evidence markers per intent. Weights are ordinal, not probabilities:
# a 3 is a near-decisive phrase, a 1 is weak corroboration. They were tuned on
# the development split of intent_testset.json only.
INTENT_MARKERS = {
    QueryIntent.TREND_ANALYSIS: {
        3: ["over time", "trend", "month by month", "year over year", "yoy",
            "growth rate", "time series", "monthly", "quarterly", "daily",
            "weekly", "annually", "yearly", "per month", "per quarter", "per year",
            "by month", "by quarter", "by year", "by week", "by day",
            "per day", "per week", "over the last", "history of", "historical"],
        2: ["growth", "increase", "decrease", "rise", "fall", "change",
            "evolution", "progress", "since", "each month", "each year"],
        1: ["by date", "timeline", "period"],
    },
    QueryIntent.COMPARISON: {
        3: ["compare", "comparison", "versus", " vs ", "compared to",
            "difference between", "against each other",
            # One value per member of a group (Stage 5, Spider DEV): "how many
            # shops are there in each location", "for each template".
            r"\b(?:for|in|of|by)[ ]each\b", r"\beach (?!other\b)[a-z]+\b.{0,20}\b(?:has|have|had|is|are|was|were)\b"],
        2: ["by region", "by department", "by category", "by product",
            "by team", "by branch", "across", "between"],
        1: ["each", r"\bper[ ]"],
    },
    QueryIntent.RANKING: {
        3: ["top ", "bottom ", "highest", "lowest", "best performing",
            "worst performing", "rank", "ranked", "leaderboard", "most ",
            "least ", "largest", "smallest", "biggest",
            "fewest", "greatest", "youngest", "oldest", "most common", "earliest",
            "latest", "longest", "shortest"],
        # "first" ranks only as "the first 10" or "the first student to
        # register"; as "first and second line" or "first, middle and last
        # names" it names columns (Stage 5, Spider DEV).
        2: ["best", "worst", "leading", "order by", "sorted by",
            r"\bfirst[ ](?:\d+|few|ten|five|three)\b", r"\bthe first [a-z]+ (?:to|who|that)\b",
            "sort ", "sorted", "ordered by", "ascending", "descending", "alphabetical"],
        1: ["maximum", "minimum"],
    },
    QueryIntent.PROPORTION: {
        3: ["percentage of", "share of", "proportion", "what portion",
            "breakdown of", "composition", "% of total", "makes up",
            "contribution of"],
        2: ["split by", "distribution across", "ratio", "percent"],
        1: ["part of"],
    },
    QueryIntent.DISTRIBUTION: {
        3: ["distribution of", "histogram", "spread of", "how are .* distributed",
            "frequency of", "range of values"],
        2: ["variance", "standard deviation", "dispersion", "spread",
            "how many fall"],
        1: ["buckets", "bins"],
    },
    QueryIntent.CORRELATION: {
        3: ["correlation", "correlated", "correlate", "relationship between",
            "does .* affect", "impact of .* on", "influence of"],
        2: ["scatter", "associated with", "depend on", "vary with"],
        1: ["against"],
    },
    QueryIntent.ANOMALY_DETECTION: {
        3: ["anomaly", "anomalies", "outlier", "outliers", "unusual",
            "abnormal", "unexpected", "suspicious", "irregular", "spike",
            "spikes", "sudden drop", "out of the ordinary"],
        2: ["strange", "odd", "flag", "deviation", "deviates"],
        1: ["weird"],
    },
    QueryIntent.KPI_SINGLE_VALUE: {
        3: ["total number of", "how many", "how much", "what is the total",
            "what is the average", "overall total", "sum of all", "count of",
            "count the", "find the number of", "what is the number of",
            # "the number of flights" is a count; "the phone number of the
            # student" is a column (Stage 5, Spider DEV).
            r"\bthe number of (?!the\b|a\b|an\b|this\b|that\b|his\b|her\b)[a-z]",
            "give the number of", "return the number of",
            # Several aggregates of one column are still one row of figures.
            r"\b(?:minimum|maximum|average|mean|total)\b(?:,| and)[ ](?:the )?"
            r"(?:minimum|maximum|average|mean|total)\b"],
        2: ["total", "average", "mean", "median", "overall",
            r"\bnumber of (?!the\b|a\b|an\b|this\b|that\b|his\b|her\b)[a-z]"],
        1: ["value of"],
    },
    QueryIntent.DETAIL_LOOKUP: {
        3: ["list all", "show me all", "give me the records", "which rows",
            "details of", "look up", "find the record", "who is", "what is the name of"],
        2: ["list", "show all", "records", "entries", "rows"],
        1: ["find", "get", "show",
            # A question that names the attributes to return, with no other
            # cue, is a lookup (Stage 5, Spider DEV: phrasings like these opened
            # 171 of the questions that got no intent). Deliberately the weakest
            # tier, and one pattern, so any real marker outranks it.
            r"^(?:(?:what|which) (?:are|is|was|were) the [a-z]+"
            r"|(?:return|give|tell me|find|show|list|display|provide) (?:me )?"
            r"(?:the|all|a|an|each|every)\b|(?:which|what|who|where)[ ])"],
    },
}

# A forecast the user turned down ("without a forecast", "no predictions
# please"). Before Stage 6 these words were matched as a REQUEST, so the opt-out
# produced a forecast; and nothing could turn off the implicit forecast a trend
# question gets.
PREDICTION_DECLINED = re.compile(
    r"\b(?:no|not|without|don'?t|do not|never|skip|exclude|excluding|leave out)\s+"
    r"(?:\w+\s+){0,2}?(?:forecasts?|forecasting|predictions?|predict|projections?|project)\b"
)

# Explicit forecast requests.
PREDICTION_EXPLICIT = [
    "predict", "prediction", "forecast", "forecasting", "project",
    "projection", "projected", "next month", "next quarter", "next year",
    "next week", "tomorrow", "will we", "will i ", "will our",
    "next 3", "next three", "next few", "coming months", "upcoming",
    "will be", "expect", "expected", "estimate for", "future", "outlook",
    "how much will", "what will",
    # Continuation phrasing: characteristic of anomaly follow-ups
    # ("...and will they continue?"), which are forecast requests in substance.
    "will they", "will it", "will this", "continue", "going forward",
    "worsen", "recover", "keep rising", "keep falling", "trending toward",
]

WHAT_IF_MARKERS = [
    "what if", "what-if", "suppose", "assuming", "if i ", "if we ",
    "scenario", "simulate", "hypothetically", "were to",
]

AGG_MARKERS = {
    "SUM": ["total", "sum", "combined", "altogether", "overall spend", "revenue"],
    "AVG": ["average", "avg", "mean", "typical", "per unit"],
    "COUNT": ["how many", "number of", "count", "quantity of records"],
    "MAX": ["maximum", "highest", "peak", "largest", "most"],
    "MIN": ["minimum", "lowest", "smallest", "least"],
}

GRANULARITY_MARKERS = {
    Granularity.HOUR: ["hourly", "per hour", "by hour", "hour"],
    Granularity.DAY: ["daily", "per day", "by day", "day by day", "days"],
    Granularity.WEEK: ["weekly", "per week", "by week", "weeks"],
    Granularity.MONTH: ["monthly", "per month", "by month", "month by month", "months"],
    Granularity.QUARTER: ["quarterly", "per quarter", "by quarter", "quarters", "quarter"],
    Granularity.YEAR: ["yearly", "annually", "per year", "by year", "annual", "years"],
}

# Column-name morphology used when the schema gives weak type information.
TEMPORAL_NAME_HINTS = ["date", "time", "day", "month", "year", "quarter",
                       "week", "period", "created", "updated", "timestamp",
                       "_at", "_on"]
MEASURE_NAME_HINTS = ["amount", "total", "price", "cost", "revenue", "sales",
                      "spend", "expense", "value", "qty", "quantity", "count",
                      "score", "rate", "salary", "balance", "profit", "margin",
                      "units", "hours", "duration"]
IDENTIFIER_NAME_HINTS = ["id", "_id", "uuid", "guid", "code", "key", "number", "no"]

# PII markers - Component 4 never unmasks, but it must refuse to *plot* or
# *narrate* a column Member 2 has flagged, and must warn when one is requested.
PII_NAME_HINTS = ["email", "phone", "mobile", "ssn", "nic", "passport",
                  "address", "dob", "birth", "salary", "credit_card", "card",
                  "account_no", "first_name", "last_name", "full_name",
                  "customer_name", "contact"]

INJECTION_MARKERS = [
    # Regex, not literals: real injection attempts pad the phrasing
    # ("ignore ALL PREVIOUS instructions"), which a fixed substring misses.
    r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|earlier)",
    r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above)",
    r"ignore\s+your\s+(rules|instructions|prompt)",
    r"forget\s+(everything|your|all)",
    r"system\s+prompt",
    r"you\s+are\s+now",
    r"\bact\s+as\b",
    r"\bdrop\s+table\b",
    r"\bdelete\s+from\b",
    r"\btruncate\b",
    r"\bupdate\s+\w+\s+set\b",
    r"\binsert\s+into\b",
    r"\bgrant\s+(all|select)\b",
    r"\bunion\s+(all\s+)?select\b",
    r"--\s*$",
    r"/\*",
    r"tenant_id\s*=",
    r"(every|all|other|another)\s+tenant",
    r"\bbypass\b",
    r"\bwithout\s+(the\s+)?(security|permission|restriction)",
]

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twelve": 12,
    "a few": 3, "next": 1,
}

# Intent -> preferred chart, with fallbacks. Refined by result cardinality in
# visualization.py; this is the pre-execution hint only.
CHART_BY_INTENT = {
    QueryIntent.TREND_ANALYSIS: ("line", ["area", "bar"]),
    QueryIntent.COMPARISON: ("bar", ["grouped_bar", "line"]),
    QueryIntent.RANKING: ("bar", ["table"]),
    QueryIntent.PROPORTION: ("donut", ["pie", "bar"]),
    QueryIntent.DISTRIBUTION: ("histogram", ["bar"]),
    QueryIntent.CORRELATION: ("scatter", ["table"]),
    QueryIntent.ANOMALY_DETECTION: ("line", ["scatter", "bar"]),
    QueryIntent.KPI_SINGLE_VALUE: ("kpi_card", ["bar"]),
    QueryIntent.DETAIL_LOOKUP: ("table", []),
    QueryIntent.UNKNOWN: ("table", []),
}


# ==========================================================================
# Schema parsing
# ==========================================================================

_CREATE_TABLE_RE = re.compile(
    r"CREATE\s+TABLE\s+[`\"\[]?(\w+)[`\"\]]?\s*\((.*?)\)\s*;", re.DOTALL | re.IGNORECASE
)
_COL_RE = re.compile(r"^\s*[`\"\[]?(\w+)[`\"\]]?\s+([A-Za-z]+(?:\s*\([\d,\s]*\))?)")

_CONSTRAINT_TOKENS = ("primary", "foreign", "unique", "key", "constraint",
                      "check", "index")


def parse_schema(schema_meta) -> dict:
    """
    Normalise a schema into {table: {column: sql_type}}.

    Accepts either a DDL string (as Member 1 passes) or an already-structured
    dict, so the analyzer can be driven from tests without DDL round-tripping.
    """
    if not schema_meta:
        return {}

    if isinstance(schema_meta, dict):
        out = {}
        for table, cols in schema_meta.items():
            if isinstance(cols, dict):
                out[str(table)] = {str(c): str(t) for c, t in cols.items()}
            else:  # list of column names
                out[str(table)] = {str(c): "UNKNOWN" for c in cols}
        return out

    tables = {}
    for match in _CREATE_TABLE_RE.finditer(str(schema_meta)):
        table = match.group(1)
        body = match.group(2)
        cols = {}
        depth = 0
        current = ""
        # Split on top-level commas so DECIMAL(10,2) stays intact.
        for ch in body:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if ch == "," and depth == 0:
                cols.update(_parse_column_def(current))
                current = ""
            else:
                current += ch
        cols.update(_parse_column_def(current))
        if cols:
            tables[table] = cols
    return tables


def _parse_column_def(fragment: str) -> dict:
    frag = fragment.strip()
    if not frag:
        return {}
    if frag.split()[0].lower() in _CONSTRAINT_TOKENS:
        return {}
    m = _COL_RE.match(frag)
    if not m:
        return {}
    return {m.group(1): m.group(2).strip().upper()}


def classify_column_role(column: str, sql_type: str) -> str:
    """Assign a semantic role from the column's declared type and its name."""
    name = column.lower()
    dtype = (sql_type or "").upper()

    if any(t in dtype for t in ("DATE", "TIME", "YEAR")):
        return ColumnRole.TEMPORAL.value
    if "BOOL" in dtype or "BIT" in dtype:
        return ColumnRole.BOOLEAN.value

    is_numeric = any(
        t in dtype
        for t in ("INT", "DECIMAL", "NUMERIC", "FLOAT", "DOUBLE", "REAL", "MONEY")
    )

    # An INT named *_id is a key, not a quantity - the single most common
    # mis-encoding in naive text-to-chart systems.
    if any(name == h or name.endswith(h) for h in IDENTIFIER_NAME_HINTS):
        return ColumnRole.IDENTIFIER.value
    if any(h in name for h in TEMPORAL_NAME_HINTS):
        return ColumnRole.TEMPORAL.value
    if is_numeric:
        if any(h in name for h in MEASURE_NAME_HINTS):
            return ColumnRole.MEASURE.value
        return ColumnRole.MEASURE.value
    if any(t in dtype for t in ("CHAR", "TEXT", "STRING", "ENUM")):
        return ColumnRole.DIMENSION.value
    if dtype == "UNKNOWN":
        if any(h in name for h in MEASURE_NAME_HINTS):
            return ColumnRole.MEASURE.value
        return ColumnRole.DIMENSION.value
    return ColumnRole.UNSUPPORTED.value


def is_pii_column(column: str) -> bool:
    name = column.lower()
    return any(h in name for h in PII_NAME_HINTS)


def render_schema_block(tables: dict, max_tables: int = 25) -> str:
    """Minimal-context schema projection handed to the LLM."""
    lines = []
    for table, cols in list(tables.items())[:max_tables]:
        rendered = ", ".join(f"{c}:{t}" for c, t in cols.items())
        lines.append(f"- {table}({rendered})")
    return "\n".join(lines)


# ==========================================================================
# Text utilities
# ==========================================================================


def normalize(text: str) -> str:
    t = (text or "").lower().strip()
    t = re.sub(r"[‘’“”]", "'", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _tokens(text: str) -> list:
    return re.findall(r"[a-z0-9_]+", normalize(text))


def _singular(word: str) -> str:
    if len(word) > 3 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("ses"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


# ==========================================================================
# A. Deterministic rule engine
# ==========================================================================


def _score_intents(text: str) -> dict:
    """Accumulate weighted marker evidence for every intent."""
    scores = {intent: 0.0 for intent in INTENT_MARKERS}
    hits = {intent: [] for intent in INTENT_MARKERS}

    for intent, tiers in INTENT_MARKERS.items():
        for weight, markers in tiers.items():
            for marker in markers:
                pattern = marker.strip()
                if any(c in pattern for c in ".*[]"):
                    found = re.search(pattern, text) is not None
                elif pattern[0].isalnum():
                    # A literal marker must start a word: before Stage 5 "each"
                    # matched inside "teach" and "per" inside "percent". The end
                    # stays open so "increase" still matches "increased".
                    found = re.search(r"(?<![a-z0-9])" + re.escape(pattern), text) is not None
                else:
                    found = pattern in text
                if found:
                    scores[intent] += float(weight)
                    hits[intent].append(pattern)
    return scores, hits


def _resolve_intent(text: str, scores: dict, hits: dict) -> tuple:
    """
    Pick the primary intent, applying precedence rules where markers collide.

    The rules encode genuine semantic dominance, not arbitrary tie-breaks:
    an explicit outlier request stays ANOMALY_DETECTION even though it usually
    also contains temporal words; a top-N request stays RANKING even though
    "most" also signals KPI.
    """
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, best_score = ranked[0]
    runner, runner_score = ranked[1] if len(ranked) > 1 else (QueryIntent.UNKNOWN, 0.0)

    if best_score == 0:
        return QueryIntent.UNKNOWN, [], 0.2, "No decisive lexical markers found."

    # Precedence overrides.
    grouped = (re.search(r"\b(?:for|in|of|by|to) each\b|\bper\b|\beach (?!other\b)[a-z]+"
                         r"|\beach\s*[?.!]?$", text)
               or response_intent._PER_ROW_COUNT.search(text))
    superlative = re.search(
        r"\b(?:most|least|highest|lowest|largest|smallest|biggest|greatest|fewest"
        r"|youngest|oldest|earliest|latest|longest|shortest|top|bottom)\b", text)
    # KPI evidence that names an aggregate outright, as opposed to "the number
    # of" inside "the airport with the highest number of flights".
    kpi_explicit = re.search(
        r"\bhow (?:many|much)\b|\btotal\b|\baverage\b|\bmean\b|\bcount (?:the|of)\b|\bsum\b",
        text)
    if scores[QueryIntent.ANOMALY_DETECTION] >= 3:
        best = QueryIntent.ANOMALY_DETECTION
    elif scores[QueryIntent.CORRELATION] >= 3:
        best = QueryIntent.CORRELATION
    elif scores[QueryIntent.RANKING] >= 3 and re.search(r"top\s+\d+|bottom\s+\d+", text):
        best = QueryIntent.RANKING
    elif scores[QueryIntent.PROPORTION] >= 3 and best is QueryIntent.COMPARISON:
        best = QueryIntent.PROPORTION
    elif (superlative and scores[QueryIntent.RANKING] >= 3
          and (best is QueryIntent.DETAIL_LOOKUP
               or (best is QueryIntent.KPI_SINGLE_VALUE and not kpi_explicit))):
        # "the code of the airport with the most flights" retrieves the top
        # entity: a ranking, whatever attribute it returns.
        best = QueryIntent.RANKING
    elif (best is QueryIntent.DETAIL_LOOKUP and grouped
          and re.search(r"\b(?:number|count) of\b|\bhow many\b|\b(?:total|average|sum)\b", text)):
        # "show all template codes and the number of templates for each":
        # a value per group, not a list of records.
        best = QueryIntent.COMPARISON
    elif (best is QueryIntent.KPI_SINGLE_VALUE and grouped
          and scores[QueryIntent.TREND_ANALYSIS] < 3):
        # "how many shops are there in each location" counts per location:
        # one value per group is a comparison, not one figure.
        best = QueryIntent.COMPARISON
    elif (
        scores[QueryIntent.TREND_ANALYSIS] >= 3
        and best is QueryIntent.KPI_SINGLE_VALUE
        and scores[QueryIntent.KPI_SINGLE_VALUE] < scores[QueryIntent.TREND_ANALYSIS] + 2
    ):
        # "total revenue per month" is a trend, not a scalar KPI.
        best = QueryIntent.TREND_ANALYSIS

    best_score = scores[best]

    # Confidence: separation between winner and runner-up, damped by absolute
    # evidence so a 1-vs-0 win is never as confident as a 6-vs-1 win.
    separation = (best_score - runner_score) / max(best_score, 1.0)
    saturation = min(best_score / 6.0, 1.0)
    confidence = round(min(0.35 + 0.5 * separation + 0.25 * saturation, 0.97), 4)

    secondary = [
        i.value for i, s in ranked[1:4] if s >= 2 and s >= best_score * 0.5 and i is not best
    ]
    marker_note = ", ".join(f"'{h}'" for h in hits[best][:3]) or "structural cues"
    rationale = f"Matched {marker_note} (evidence {best_score:.0f} vs next {runner_score:.0f})."
    return best, secondary, confidence, rationale


def _detect_horizon(text: str) -> HorizonSpec:
    """Extract a forecast horizon: '3 months', 'next quarter', 'next three months'."""
    unit_map = {
        "hour": Granularity.HOUR, "day": Granularity.DAY, "week": Granularity.WEEK,
        "month": Granularity.MONTH, "quarter": Granularity.QUARTER,
        "year": Granularity.YEAR,
    }

    m = re.search(r"next\s+(\d+)\s+(hour|day|week|month|quarter|year)s?", text)
    if m:
        return HorizonSpec(int(m.group(1)), unit_map[m.group(2)].value, "EXPLICIT")

    m = re.search(
        r"next\s+(one|two|three|four|five|six|seven|eight|nine|ten|twelve|a few)\s+"
        r"(hour|day|week|month|quarter|year)s?",
        text,
    )
    if m:
        return HorizonSpec(
            NUMBER_WORDS[m.group(1)], unit_map[m.group(2)].value, "EXPLICIT"
        )

    m = re.search(r"(\d+)[- ](hour|day|week|month|quarter|year)s?\s+(forecast|projection|ahead)", text)
    if m:
        return HorizonSpec(int(m.group(1)), unit_map[m.group(2)].value, "EXPLICIT")

    m = re.search(r"next\s+(hour|day|week|month|quarter|year)", text)
    if m:
        return HorizonSpec(1, unit_map[m.group(1)].value, "EXPLICIT")

    return HorizonSpec(0, Granularity.NONE.value, "NONE")


def _detect_what_if(text: str) -> WhatIfSpec:
    if not any(m in text for m in WHAT_IF_MARKERS):
        return WhatIfSpec()

    clause = text
    for marker in WHAT_IF_MARKERS:
        idx = text.find(marker)
        if idx != -1:
            clause = text[idx:]
            break

    # Shared with the simulate box (scenario_language); whole words only, so
    # "unless" is not "less" and "supplier" is not "up". A clause that cannot be
    # read as one percentage change keeps present=True with no direction, and
    # the what-if engine reports why it was refused.
    parsed = scenario_language.parse(clause)
    direction = parsed["direction"] if parsed["valid"] else ""
    magnitude = parsed["magnitude_pct"] if parsed["valid"] else 0.0

    return WhatIfSpec(
        present=True,
        raw_clause=clause[:160],
        parameter="",  # bound to a metric during merge, once metrics are known
        direction=direction,
        magnitude_pct=magnitude,
    )


def _detect_granularity(text: str) -> str:
    for gran, markers in GRANULARITY_MARKERS.items():
        if any(m in text for m in markers):
            return gran.value
    return Granularity.NONE.value


def _detect_aggregation(text: str, default: str = "SUM") -> str:
    for agg, markers in AGG_MARKERS.items():
        if any(m in text for m in markers):
            return agg
    return default


def _detect_limit(text: str) -> int:
    m = re.search(r"\b(?:top|bottom|first|last)\s+(\d+)\b", text)
    if m:
        return int(m.group(1))
    m = re.search(
        r"\b(?:top|bottom|first)\s+(one|two|three|four|five|ten)\b", text
    )
    if m:
        return NUMBER_WORDS[m.group(1)]
    return 0


def bind_schema(text: str, tables: dict) -> tuple:
    """
    Bind question terms to schema objects.

    Exact token match scores highest; a fuzzy match above 0.82 catches plural
    and minor-spelling drift ("expences" -> "expenses"). Terms that bind to
    nothing are surfaced as `unresolved_terms` rather than silently dropped,
    which is what lets the pipeline warn instead of plotting the wrong column.
    """
    toks = set(_tokens(text))
    toks |= {_singular(t) for t in toks}

    table_bindings = []
    column_bindings = []
    matched_terms = set()

    for table, cols in tables.items():
        t_lower = table.lower()
        t_terms = set(re.split(r"[_\s]+", t_lower)) | {t_lower, _singular(t_lower)}
        t_hits = sorted(toks & t_terms)
        t_conf = 0.0
        if t_hits:
            t_conf = 0.95
        else:
            for tok in toks:
                if len(tok) > 3 and _similar(tok, t_lower) >= 0.82:
                    t_hits = [tok]
                    t_conf = 0.70
                    break

        col_hits_for_table = []
        for col, dtype in cols.items():
            c_lower = col.lower()
            c_terms = set(re.split(r"[_\s]+", c_lower)) | {c_lower, _singular(c_lower)}
            c_terms = {c for c in c_terms if len(c) > 2}
            hits = sorted(toks & c_terms)
            conf = 0.0
            if hits:
                conf = 0.9 if c_lower in toks else 0.75
            else:
                for tok in toks:
                    if len(tok) > 3 and _similar(tok, c_lower) >= 0.85:
                        hits = [tok]
                        conf = 0.65
                        break
            if conf:
                matched_terms.update(hits)
                col_hits_for_table.append(
                    ColumnBinding(
                        table=table,
                        column=col,
                        role=classify_column_role(col, dtype),
                        data_type=dtype,
                        is_pii=is_pii_column(col),
                        confidence=conf,
                        matched_terms=hits,
                    )
                )

        if t_conf or col_hits_for_table:
            matched_terms.update(t_hits)
            # A table reached only through its columns is still relevant, but
            # with confidence derived from those columns.
            confidence = t_conf or max(c.confidence for c in col_hits_for_table) * 0.8
            has_measure = any(
                c.role == ColumnRole.MEASURE.value for c in cols_to_bindings(cols)
            )
            table_bindings.append(
                TableBinding(
                    table=table,
                    role="FACT" if has_measure else "DIMENSION",
                    confidence=round(confidence, 3),
                    matched_terms=t_hits,
                )
            )
            column_bindings.extend(col_hits_for_table)

    table_bindings.sort(key=lambda t: -t.confidence)
    column_bindings.sort(key=lambda c: -c.confidence)

    stop = {
        "the", "a", "an", "of", "for", "and", "or", "in", "on", "at", "to",
        "by", "me", "my", "show", "give", "what", "which", "how", "is", "are",
        "was", "were", "with", "from", "over", "last", "next", "all", "total",
        "per", "each", "top", "bottom", "highest", "lowest", "predict",
        "forecast", "please", "can", "you", "i", "we", "us", "it", "that",
        "this", "there", "their", "do", "does", "did", "get", "list", "have",
        # Time and quantity words are query vocabulary, not schema terms - they
        # would otherwise dominate `unresolved_terms` on every forecast request.
        "hour", "hours", "day", "days", "week", "weeks", "month", "months",
        "quarter", "quarters", "year", "years", "daily", "weekly", "monthly",
        "quarterly", "yearly", "annual", "annually", "time", "period", "periods",
        "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "twelve", "few", "many", "much", "some", "any", "then", "also",
        "average", "count", "sum", "number", "value", "values", "data", "about",
        "between", "across", "during", "since", "until", "compare", "trend",
        "project", "projected", "coming", "upcoming", "future", "past",
    }
    unresolved = sorted(
        t for t in toks
        if t not in stop and t not in matched_terms and len(t) > 3 and not t.isdigit()
    )

    return table_bindings, column_bindings, unresolved[:12]


def cols_to_bindings(cols: dict) -> list:
    """Helper: role-classify every column of a table (no question context)."""
    return [
        ColumnBinding(table="", column=c, role=classify_column_role(c, t), data_type=t)
        for c, t in cols.items()
    ]


def _derive_roles(text: str, columns: list, intent) -> tuple:
    """Split bound columns into metrics, dimensions and the temporal field."""
    metrics, dimensions, temporal = [], [], ""

    for c in columns:
        if c.role == ColumnRole.TEMPORAL.value and not temporal:
            temporal = c.column
        elif c.role == ColumnRole.MEASURE.value:
            if not any(m.column == c.column for m in metrics):
                metrics.append(
                    MetricSpec(
                        column=c.column,
                        aggregation=_detect_aggregation(text),
                        table=c.table,
                    )
                )
        elif c.role in (ColumnRole.DIMENSION.value, ColumnRole.BOOLEAN.value):
            if c.column not in dimensions:
                dimensions.append(c.column)

    # DETAIL_LOOKUP returns rows, not aggregates - suppress invented metrics.
    if intent is QueryIntent.DETAIL_LOOKUP:
        metrics = []

    return metrics, dimensions, temporal


def _detect_injection(raw_query: str) -> list:
    """
    Flag instruction-injection and destructive-SQL patterns in the user text.

    This is a *reporting* control, not the enforcement boundary: Member 2's AST
    gate is what actually blocks execution. Its value here is that Component 4
    reads raw user text when building prompts, so it must mark a request as
    suspicious before that text reaches any model.
    """
    text = normalize(raw_query)
    return [pattern for pattern in INJECTION_MARKERS if re.search(pattern, text)]


def _infer_from_fact_table(tables: dict, table_bindings: list, text: str) -> tuple:
    """
    Recover a measure and a time axis from the bound table when the question
    named neither.

    "Predict my expenses for the next 3 months" binds the `expenses` table but
    mentions no column, yet the request is unambiguous: aggregate the table's
    measure over its date column. Without this, every such query would fail the
    readiness gate for want of a measure - the single most common gap observed
    in development.
    """
    if not table_bindings:
        return [], ""

    primary = table_bindings[0].table
    cols = tables.get(primary, {})
    measures, temporal = [], ""

    for col, dtype in cols.items():
        role = classify_column_role(col, dtype)
        if role == ColumnRole.TEMPORAL.value and not temporal:
            temporal = col
        elif role == ColumnRole.MEASURE.value and not is_pii_column(col):
            # Prefer a column whose name states a quantity over an incidental
            # numeric (e.g. `amount` over `units`), by scoring name evidence.
            score = sum(1 for h in MEASURE_NAME_HINTS if h in col.lower())
            measures.append((score, col))

    measures.sort(key=lambda p: -p[0])
    inferred = (
        [MetricSpec(column=measures[0][1], aggregation=_detect_aggregation(text), table=primary)]
        if measures
        else []
    )
    return inferred, temporal


def _rule_analysis(user_query: str, tables: dict) -> QueryAnalysis:
    text = normalize(user_query)
    # Thresholds ("at least two"), average filters and "first name" are not
    # superlatives or KPIs; the shared rewrite keeps both classifiers agreed.
    scored_text = response_intent.neutralize(text)
    scores, hits = _score_intents(scored_text)
    intent, secondary, confidence, rationale = _resolve_intent(scored_text, scores, hits)

    table_bindings, column_bindings, unresolved = bind_schema(user_query, tables)
    metrics, dimensions, temporal = _derive_roles(text, column_bindings, intent)

    horizon = _detect_horizon(text)
    what_if = _detect_what_if(text)
    declined = PREDICTION_DECLINED.search(text) is not None
    explicit_pred = not declined and any(m in text for m in PREDICTION_EXPLICIT)

    # A forecast request is inherently a question about a series over time, so
    # a scalar or lookup reading cannot be correct. Promote before the chart
    # hint and the prediction strategy are derived from the intent.
    if (explicit_pred or what_if.present) and intent in (
        QueryIntent.KPI_SINGLE_VALUE,
        QueryIntent.DETAIL_LOOKUP,
        QueryIntent.UNKNOWN,
    ):
        rationale = (
            f"{rationale} Promoted from {intent.value} to TREND_ANALYSIS: an "
            "explicit forecast request presupposes a time series."
        )
        if intent.value not in secondary:
            secondary.insert(0, intent.value)
        intent = QueryIntent.TREND_ANALYSIS
        confidence = max(confidence, 0.75)
        metrics, dimensions, temporal = _derive_roles(text, column_bindings, intent)

    # Fill a missing measure or time axis from the bound fact table.
    if not metrics and intent is not QueryIntent.DETAIL_LOOKUP:
        inferred_metrics, inferred_temporal = _infer_from_fact_table(
            tables, table_bindings, text
        )
        metrics = inferred_metrics
        if not temporal:
            temporal = inferred_temporal
    elif not temporal:
        _, temporal = _infer_from_fact_table(tables, table_bindings, text)

    if declined and not what_if.present:
        # The user said no: no explicit forecast and no implicit one either.
        trigger = "DECLINED"
        required = False
    elif explicit_pred or what_if.present:
        trigger = "EXPLICIT"
        required = True
    elif intent is QueryIntent.TREND_ANALYSIS and temporal:
        trigger = "IMPLICIT"
        required = True
    else:
        trigger = "NONE"
        required = False

    # An explicit forecast with no stated horizon defaults to 3 periods, which
    # is recorded as INFERRED so the summary can disclose the assumption.
    granularity = _detect_granularity(text)
    if required and horizon.source == "NONE":
        horizon = HorizonSpec(
            3, granularity if granularity != Granularity.NONE.value else Granularity.MONTH.value,
            "INFERRED",
        )
    if granularity == Granularity.NONE.value and horizon.unit != Granularity.NONE.value:
        granularity = horizon.unit

    chart, alternatives = CHART_BY_INTENT[intent]

    warnings = []
    injections = _detect_injection(user_query)
    if injections:
        warnings.append("PROMPT_INJECTION_SUSPECTED")
    pii_cols = [c.column for c in column_bindings if c.is_pii]
    if pii_cols:
        warnings.append("PII_COLUMNS_REFERENCED")
    if not table_bindings and tables:
        warnings.append("NO_SCHEMA_BINDING")
    if unresolved:
        warnings.append("UNRESOLVED_TERMS")

    return QueryAnalysis(
        user_query=user_query,
        normalized_query=text,
        primary_intent=intent.value,
        secondary_intents=secondary,
        intent_confidence=confidence,
        intent_source="RULE",
        intent_rationale=rationale,
        prediction_required=required,
        prediction_trigger=trigger,
        horizon=horizon,
        what_if=what_if,
        affected_tables=table_bindings,
        affected_columns=column_bindings,
        unresolved_terms=unresolved,
        metrics=metrics,
        dimensions=dimensions,
        temporal_field=temporal,
        temporal_granularity=granularity,
        filters=[],
        ordering="",
        limit=_detect_limit(text),
        recommended_chart=chart,
        chart_alternatives=alternatives,
        chart_rationale=f"{intent.value} maps to '{chart}' by the intent-encoding table.",
        pii_columns_referenced=pii_cols,
        warnings=warnings,
        metadata={"injection_markers": injections},
    )


# ==========================================================================
# B. LLM engine
# ==========================================================================


def _coerce_enum(value, allowed: list, fallback: str) -> str:
    """Force a model-supplied label into the closed vocabulary."""
    if not isinstance(value, str):
        return fallback
    v = value.strip().upper().replace(" ", "_").replace("-", "_")
    return v if v in allowed else fallback


def _llm_analysis(user_query: str, tables: dict, security_block: str, profiler):
    """Run structured extraction. Returns (payload_dict, token_stats)."""
    schema_block = render_schema_block(tables)
    user_prompt = build_analysis_prompt(user_query, schema_block, security_block)
    return llm.call_llm_json(SYSTEM_PROMPT, user_prompt, profiler=profiler)


def _validate_llm_payload(payload: dict, tables: dict) -> dict:
    """
    Clamp an LLM payload to reality.

    Any table/column the model invented is stripped and recorded, so a
    hallucinated binding can never reach the chart builder or the forecaster.
    """
    valid_tables = {t.lower(): t for t in tables}
    valid_cols = {
        (t.lower(), c.lower()): (t, c) for t, cols in tables.items() for c in cols
    }
    hallucinated = []

    clean_tables = []
    for entry in payload.get("affected_tables", []) or []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("table", "")).lower()
        if name in valid_tables:
            real = valid_tables[name]
            clean_tables.append(
                TableBinding(
                    table=real,
                    role=_coerce_enum(entry.get("role"), ["FACT", "DIMENSION", "BRIDGE"], "FACT"),
                    confidence=_as_float(entry.get("confidence"), 0.8),
                    matched_terms=_as_list(entry.get("matched_terms")),
                )
            )
        elif name:
            hallucinated.append(f"table:{entry.get('table')}")

    clean_cols = []
    for entry in payload.get("affected_columns", []) or []:
        if not isinstance(entry, dict):
            continue
        t = str(entry.get("table", "")).lower()
        c = str(entry.get("column", "")).lower()
        if (t, c) in valid_cols:
            real_t, real_c = valid_cols[(t, c)]
            dtype = tables[real_t][real_c]
            clean_cols.append(
                ColumnBinding(
                    table=real_t,
                    column=real_c,
                    # Trust the declared type over the model's guess.
                    role=classify_column_role(real_c, dtype),
                    data_type=dtype,
                    is_pii=is_pii_column(real_c),
                    confidence=_as_float(entry.get("confidence"), 0.8),
                    matched_terms=_as_list(entry.get("matched_terms")),
                )
            )
        elif c:
            hallucinated.append(f"column:{entry.get('table')}.{entry.get('column')}")

    all_cols = {c.column.lower() for c in clean_cols} or {
        c.lower() for cols in tables.values() for c in cols
    }

    clean_metrics = []
    for entry in payload.get("metrics", []) or []:
        if not isinstance(entry, dict):
            continue
        col = str(entry.get("column", ""))
        if col.lower() in all_cols:
            clean_metrics.append(
                MetricSpec(
                    column=col,
                    aggregation=_coerce_enum(
                        entry.get("aggregation"),
                        ["SUM", "AVG", "COUNT", "MIN", "MAX", "NONE"],
                        "SUM",
                    ),
                    table=str(entry.get("table", "")),
                )
            )
        elif col:
            hallucinated.append(f"metric:{col}")

    temporal = str(payload.get("temporal_field", "") or "")
    if temporal and temporal.lower() not in all_cols:
        hallucinated.append(f"temporal:{temporal}")
        temporal = ""

    dimensions = [d for d in _as_list(payload.get("dimensions")) if str(d).lower() in all_cols]

    horizon_raw = payload.get("horizon") or {}
    horizon = HorizonSpec(
        value=int(_as_float(horizon_raw.get("value"), 0)),
        unit=_coerce_enum(
            horizon_raw.get("unit"), [g.value for g in Granularity], Granularity.NONE.value
        ),
        source=_coerce_enum(horizon_raw.get("source"), ["EXPLICIT", "INFERRED", "NONE"], "NONE"),
    )

    wi_raw = payload.get("what_if") or {}
    what_if = WhatIfSpec(
        present=bool(wi_raw.get("present", False)),
        raw_clause=str(wi_raw.get("raw_clause", ""))[:160],
        parameter=str(wi_raw.get("parameter", "")),
        direction=_coerce_enum(
            wi_raw.get("direction"), ["INCREASE", "DECREASE", "SET"], ""
        ),
        magnitude_pct=_as_float(wi_raw.get("magnitude_pct"), 0.0),
    )

    return {
        "normalized_query": str(payload.get("normalized_query", "")),
        "primary_intent": _coerce_enum(
            payload.get("primary_intent"), ALL_INTENTS, QueryIntent.UNKNOWN.value
        ),
        "secondary_intents": [
            _coerce_enum(s, ALL_INTENTS, "") for s in _as_list(payload.get("secondary_intents"))
        ],
        "intent_confidence": max(0.0, min(_as_float(payload.get("intent_confidence"), 0.5), 1.0)),
        "intent_rationale": str(payload.get("intent_rationale", ""))[:300],
        # An out-of-vocabulary response intent falls back to "", which the
        # merge policy reads as "the model abstained" and keeps the rule verdict.
        "response_intent": _coerce_enum(
            payload.get("response_intent"), ALL_RESPONSE_INTENTS, ""
        ),
        "response_intent_confidence": max(
            0.0, min(_as_float(payload.get("response_intent_confidence"), 0.5), 1.0)
        ),
        "response_intent_rationale": str(payload.get("response_intent_rationale", ""))[:300],
        "prediction_required": bool(payload.get("prediction_required", False)),
        "prediction_trigger": _coerce_enum(
            payload.get("prediction_trigger"), ["EXPLICIT", "IMPLICIT", "NONE"], "NONE"
        ),
        "horizon": horizon,
        "what_if": what_if,
        "affected_tables": clean_tables,
        "affected_columns": clean_cols,
        "unresolved_terms": [str(u) for u in _as_list(payload.get("unresolved_terms"))][:12],
        "metrics": clean_metrics,
        "dimensions": [str(d) for d in dimensions],
        "temporal_field": temporal,
        "temporal_granularity": _coerce_enum(
            payload.get("temporal_granularity"),
            [g.value for g in Granularity],
            Granularity.NONE.value,
        ),
        "filters": [f for f in _as_list(payload.get("filters")) if isinstance(f, dict)],
        "ordering": str(payload.get("ordering", "")),
        "limit": int(_as_float(payload.get("limit"), 0)),
        "recommended_chart": str(payload.get("recommended_chart", "") or ""),
        "chart_alternatives": [str(a) for a in _as_list(payload.get("chart_alternatives"))],
        "chart_rationale": str(payload.get("chart_rationale", ""))[:300],
        "warnings": [str(w) for w in _as_list(payload.get("warnings"))],
        "hallucinated_bindings": hallucinated,
    }


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_list(value) -> list:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


# ==========================================================================
# Arbitration
# ==========================================================================

# Below this, the LLM's intent is not trusted over the rule engine's.
LLM_INTENT_TRUST_THRESHOLD = 0.60

# At or above this the rule engine's intent stands even against a confident
# LLM (Stage 6). Before, a confident LLM always won; on 60 Spider TEST
# questions that lowered intent agreement from 91.7 % to 81.7 % while the
# response shape, which already used this policy, improved. Same value as
# response_intent.LEXICAL_TRUST_THRESHOLD.
RULE_INTENT_TRUST_THRESHOLD = 0.55

# Warning tags that carry a security meaning downstream. These may only be
# raised by the deterministic rule engine, whose decision is reproducible and
# traceable to an inspectable pattern. If the LLM emits one it is recorded in
# metadata for analysis but never becomes a finding.
RULE_OWNED_WARNINGS = {
    "PROMPT_INJECTION_SUSPECTED",
    "PII_COLUMNS_REFERENCED",
    "NO_SCHEMA_BINDING",
}


def _merge(rule: QueryAnalysis, llm_out: dict) -> QueryAnalysis:
    """
    Combine the two analyses under an explicit, auditable policy.

    Policy:
      * intent          - LLM if confident, in-vocabulary AND the rule verdict
                          is weak (below RULE_INTENT_TRUST_THRESHOLD or
                          UNKNOWN); a confident rule verdict stands.
      * schema binding  - union, LLM entries already reality-checked.
      * prediction flag - logical OR (missing a wanted forecast is the worse
                          error; an unwanted one is discarded by readiness).
      * security fields - rule engine only. Never delegated to the model.
    """
    merged = QueryAnalysis(**{**rule.__dict__})
    # Carry the rule engine's metadata forward now, so anything recorded during
    # merging (suppressed warnings, arbitration notes) survives to the caller.
    merged.metadata = dict(rule.metadata)
    decisions = []

    llm_intent = llm_out["primary_intent"]
    llm_conf = llm_out["intent_confidence"]

    rule_weak = (rule.primary_intent == QueryIntent.UNKNOWN.value
                 or rule.intent_confidence < RULE_INTENT_TRUST_THRESHOLD)
    if (llm_intent != QueryIntent.UNKNOWN.value and llm_conf >= LLM_INTENT_TRUST_THRESHOLD
            and (rule_weak or llm_intent == rule.primary_intent)):
        if llm_intent != rule.primary_intent:
            decisions.append(
                f"intent: LLM '{llm_intent}' ({llm_conf:.2f}) overrode rule "
                f"'{rule.primary_intent}' ({rule.intent_confidence:.2f})"
            )
        merged.primary_intent = llm_intent
        merged.intent_confidence = round((llm_conf * 0.7) + (rule.intent_confidence * 0.3), 4)
        merged.intent_rationale = llm_out["intent_rationale"] or rule.intent_rationale
        merged.secondary_intents = [s for s in llm_out["secondary_intents"] if s] or rule.secondary_intents
    else:
        decisions.append(
            f"intent: kept rule '{rule.primary_intent}' (LLM confidence "
            f"{llm_conf:.2f} below {LLM_INTENT_TRUST_THRESHOLD})"
        )
    merged.intent_source = "HYBRID"

    # The model's response-intent vote is parked in metadata rather than applied
    # here: the deterministic classifier has not run yet at this point, and it
    # needs the *merged* analytical intent as its prior. `analyze()` arbitrates
    # the two once both verdicts exist.
    if llm_out.get("response_intent"):
        merged.metadata["llm_response_intent"] = {
            "intent": llm_out["response_intent"],
            "confidence": llm_out["response_intent_confidence"],
            "rationale": llm_out["response_intent_rationale"],
        }

    if llm_out["normalized_query"]:
        merged.normalized_query = llm_out["normalized_query"]

    # --- schema binding: union, keyed to avoid duplicates ---------------
    seen_t = {t.table for t in merged.affected_tables}
    for t in llm_out["affected_tables"]:
        if t.table not in seen_t:
            merged.affected_tables.append(t)
            seen_t.add(t.table)

    seen_c = {(c.table, c.column) for c in merged.affected_columns}
    for c in llm_out["affected_columns"]:
        if (c.table, c.column) not in seen_c:
            merged.affected_columns.append(c)
            seen_c.add((c.table, c.column))

    # --- semantic roles: LLM fills gaps, never erases rule findings -----
    if llm_out["metrics"]:
        seen_m = {m.column for m in merged.metrics}
        for m in llm_out["metrics"]:
            if m.column not in seen_m:
                merged.metrics.append(m)
                seen_m.add(m.column)
    for d in llm_out["dimensions"]:
        if d not in merged.dimensions:
            merged.dimensions.append(d)
    if not merged.temporal_field and llm_out["temporal_field"]:
        merged.temporal_field = llm_out["temporal_field"]
    if merged.temporal_granularity == Granularity.NONE.value:
        merged.temporal_granularity = llm_out["temporal_granularity"]
    if not merged.filters:
        merged.filters = llm_out["filters"]
    if not merged.ordering:
        merged.ordering = llm_out["ordering"]
    if not merged.limit:
        merged.limit = llm_out["limit"]

    # --- prediction: OR, with the more specific horizon winning ---------
    # A DECLINED forecast is never switched back on by the model: the logical
    # OR below would otherwise turn "without a forecast" into a forecast
    # whenever the LLM read the word "forecast" as a request (Stage 6).
    merged.prediction_required = (rule.prediction_trigger != "DECLINED"
                                  and (rule.prediction_required or llm_out["prediction_required"]))
    if rule.prediction_trigger == "NONE" and llm_out["prediction_trigger"] != "NONE":
        merged.prediction_trigger = llm_out["prediction_trigger"]
    if rule.horizon.source != "EXPLICIT" and llm_out["horizon"].source == "EXPLICIT":
        merged.horizon = llm_out["horizon"]
        decisions.append("horizon: adopted LLM explicit horizon")
    if not merged.what_if.present and llm_out["what_if"].present:
        merged.what_if = llm_out["what_if"]

    # --- chart hint: recomputed from the final intent -------------------
    intent_enum = QueryIntent(merged.primary_intent)
    chart, alternatives = CHART_BY_INTENT[intent_enum]
    llm_chart = llm_out["recommended_chart"]
    if llm_chart and llm_chart in [chart] + alternatives:
        merged.recommended_chart = llm_chart
        merged.chart_rationale = llm_out["chart_rationale"] or merged.chart_rationale
    else:
        merged.recommended_chart = chart
        merged.chart_rationale = (
            f"{merged.primary_intent} maps to '{chart}' by the intent-encoding table."
        )
    merged.chart_alternatives = alternatives

    # --- warnings: union, but security flags stay rule-owned ------------
    # A model-raised warning is an opinion, not a finding. Observed in testing:
    # the LLM emitted PROMPT_INJECTION_SUSPECTED for the benign phrase "where
    # are we headed". Letting that through would (a) put a false security
    # finding in front of Member 2, and (b) make the flag unfalsifiable, since
    # it would no longer correspond to any inspectable rule. Security-classified
    # tags are therefore admitted only from the deterministic engine; anything
    # else the model says is kept, but prefixed so its provenance is explicit.
    for w in llm_out["warnings"]:
        tag = w.strip().upper().replace(" ", "_")
        if not tag:
            continue
        if tag in RULE_OWNED_WARNINGS:
            # Recorded for analysis, never promoted to a real finding.
            merged.metadata.setdefault("llm_suppressed_security_warnings", []).append(tag)
            continue
        advisory = tag if tag.startswith("LLM_") else f"LLM_{tag}"
        if advisory not in merged.warnings:
            merged.warnings.append(advisory)

    if llm_out["hallucinated_bindings"]:
        merged.warnings.append("LLM_HALLUCINATED_BINDINGS_STRIPPED")

    merged.pii_columns_referenced = sorted(
        {c.column for c in merged.affected_columns if c.is_pii}
    )
    if merged.pii_columns_referenced and "PII_COLUMNS_REFERENCED" not in merged.warnings:
        merged.warnings.append("PII_COLUMNS_REFERENCED")

    merged.metadata["arbitration"] = decisions
    merged.metadata["hallucinated_bindings"] = llm_out["hallucinated_bindings"]
    return merged


# ==========================================================================
# Public entry point
# ==========================================================================


def analyze(
    user_query: str,
    schema_meta=None,
    security_context: dict = None,
    use_llm: bool = False,
    profiler=None,
) -> QueryAnalysis:
    """
    Produce the comprehensive analysis of one natural-language data request.

    Args:
        user_query:       the raw question (treated as untrusted data).
        schema_meta:      DDL string or {table: {column: type}} mapping.
        security_context: optional dict from Member 3, e.g.
                          {"tenant_id": "...", "user_role": "...",
                           "prompt_grounding_rules": "...",
                           "denied_tables": [...]}.
        use_llm:          when False, or when no provider is configured, the
                          deterministic rule engine alone produces the result.

    Returns:
        QueryAnalysis - call `.to_dict()` for the JSON contract form.
    """
    started = time.perf_counter()
    security_context = security_context or {}
    tables = parse_schema(schema_meta)

    # Enforce Member 3's table denylist before any binding happens.
    denied = {str(t).lower() for t in security_context.get("denied_tables", [])}
    if denied:
        tables = {t: c for t, c in tables.items() if t.lower() not in denied}

    rule = _rule_analysis(user_query, tables)

    mode = "RULE_ONLY"
    token_stats = {}
    if use_llm and llm.is_available():
        try:
            payload, token_stats = _llm_analysis(
                user_query,
                tables,
                security_context.get("prompt_grounding_rules", ""),
                profiler,
            )
            validated = _validate_llm_payload(payload, tables)
            result = _merge(rule, validated)
            mode = "HYBRID"
        except Exception as exc:  # noqa: BLE001 - degrade, never fail the request
            log_step(f"LLM analysis failed, using rule engine: {exc}", level="WARN")
            result = rule
            result.warnings.append("LLM_UNAVAILABLE_RULE_FALLBACK")
            mode = "RULE_FALLBACK"
    else:
        result = rule
        if use_llm:
            log_step("No LLM provider configured - deterministic mode.", level="DEBUG")

    # Bind an unparameterised what-if to the primary metric.
    if result.what_if.present and not result.what_if.parameter and result.metrics:
        result.what_if.parameter = result.metrics[0].column

    # Presentation intent. Runs last so it can read the settled analytical
    # intent as its prior, and pre-execution so callers know what the UI will
    # need before a single row is fetched.
    response = response_intent.classify(user_query, result)

    # Arbitration, same policy as the analytical intent: the model may override
    # the lexicon only when it is confident AND the deterministic verdict was
    # itself weak. A confident rule verdict is never overturned by the model,
    # which keeps the offline accuracy figures a genuine floor.
    llm_vote = result.metadata.get("llm_response_intent")
    if llm_vote and llm_vote["intent"] != response.intent:
        if (
            llm_vote["confidence"] >= LLM_INTENT_TRUST_THRESHOLD
            and response.confidence < response_intent.LEXICAL_TRUST_THRESHOLD
        ):
            response.rationale = (
                f"LLM '{llm_vote['intent']}' ({llm_vote['confidence']:.2f}) overrode "
                f"weak rule verdict '{response.intent}' ({response.confidence:.2f}). "
                f"{llm_vote['rationale']}"
            )
            response.intent = llm_vote["intent"]
            response.blocks = [
                b.value for b in RESPONSE_BLOCKS[ResponseIntent(llm_vote["intent"])]
            ]
            response.confidence = round(
                (llm_vote["confidence"] * 0.7) + (response.confidence * 0.3), 4
            )
            response.source = "LLM"
        else:
            response.source = "HYBRID"
            response.rationale += (
                f" LLM proposed '{llm_vote['intent']}' "
                f"({llm_vote['confidence']:.2f}); rule verdict kept."
            )

    result.response_intent = response.intent
    result.response_intent_confidence = response.confidence
    result.response_intent_source = response.source
    result.response_intent_rationale = response.rationale
    result.response_blocks = response.blocks
    result.response_intent_evidence = response.to_dict()["evidence"]
    result.answer_focus = response.answer_focus
    result.is_data_request = response.is_data_request
    result.not_a_request_reason = response.not_a_request_reason
    result.response_evidence_grade = response.evidence_grade

    # Row bounds implied by a superlative. "which departments spend the most"
    # names a top slice, not the whole table, but says how big it is only when
    # the user counted it out. An inferred bound is marked INFERRED and warned
    # about, so Member 1 can apply it as a default and the client can offer to
    # widen it - it is never presented as something the user asked for.
    bounds = response_intent.derive_bounds(
        result.normalized_query,
        response.intent,
        explicit_limit=result.limit,
        metric_column=result.metrics[0].column if result.metrics else "",
    )
    result.limit = bounds["limit"]
    result.limit_source = bounds["limit_source"]
    if bounds["ordering"] and not result.ordering:
        result.ordering = bounds["ordering"]
    for warning in bounds["warnings"]:
        if warning not in result.warnings:
            result.warnings.append(warning)

    # The chart hint follows the response shape, not the analytical intent.
    # "which department spends the most" is analytically a RANKING, which maps
    # to a bar chart - but the user asked for a name, so proposing a bar chart
    # would hint at output they did not request.
    hint = response_intent.CHART_HINT_BY_RESPONSE.get(
        ResponseIntent(response.intent)
    )
    if hint is not None:
        chart, alternatives = hint
        result.chart_rationale = (
            f"Response intent {response.intent} renders as '{chart}'; the "
            f"analytical encoding '{result.recommended_chart}' is not used."
        )
        result.recommended_chart = chart
        result.chart_alternatives = alternatives
    for warning in response.warnings:
        if warning not in result.warnings:
            result.warnings.append(warning)

    if denied:
        result.metadata["denied_tables_enforced"] = sorted(denied)

    result.metadata.update(
        {
            "mode": mode,
            "model": token_stats.get("model", llm.active_model()),
            "provider": token_stats.get("provider", "none"),
            "prompt_tokens": token_stats.get("prompt_tokens", 0),
            "completion_tokens": token_stats.get("completion_tokens", 0),
            "total_tokens": token_stats.get("total_tokens", 0),
            "schema_tables_considered": len(tables),
            "execution_time_ms": round((time.perf_counter() - started) * 1000.0, 2),
            "tenant_id": security_context.get("tenant_id", ""),
            "user_role": security_context.get("user_role", ""),
        }
    )
    log_step(
        f"Analysis [{mode}] intent={result.primary_intent} "
        f"response={result.response_intent} "
        f"conf={result.intent_confidence:.2f} predict={result.prediction_required} "
        f"tables={[t.table for t in result.affected_tables]}"
    )
    return result
