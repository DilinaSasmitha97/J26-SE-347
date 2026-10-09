"""
Rule-based intent and prediction calculations with confidence.

The lexicons and the scoring/resolution logic are COPIED from the stage-8
Vonara analyzer (query_analyzer.py and response_intent.py), not imported: the
analyzer module also contains schema binding, and this classifier must stay
independent of schema, policy and database code. test_intent_classification.py
checks that the copies have not drifted from the originals.

Only text-based parts are copied. Schema-dependent parts (bind_schema,
_derive_roles, _infer_from_fact_table and the IMPLICIT forecast trigger, which
needs a schema-bound date column) are deliberately left out.

Local additions are kept apart from the copies: EXTRA_INTENT_MARKERS, the
weak-evidence confidence cap, and the split of forecast markers into strong and
soft ones.
"""

import re
from typing import Dict, List, Tuple

INTENTS = (
    "TREND_ANALYSIS", "COMPARISON", "RANKING", "PROPORTION", "DISTRIBUTION",
    "CORRELATION", "ANOMALY_DETECTION", "KPI_SINGLE_VALUE", "DETAIL_LOOKUP",
)
UNKNOWN = "UNKNOWN"

# ==========================================================================
# Copied from query_analyzer.py (stage 8), keys as plain strings
# ==========================================================================

# Weighted evidence markers per intent. Weights are ordinal, not probabilities:
# a 3 is a near-decisive phrase, a 1 is weak corroboration. They were tuned on
# the development split of intent_testset.json only.
INTENT_MARKERS = {
    "TREND_ANALYSIS": {
        3: ["over time", "trend", "month by month", "year over year", "yoy",
            "growth rate", "time series", "monthly", "quarterly", "daily",
            "weekly", "annually", "yearly", "per month", "per quarter", "per year",
            "by month", "by quarter", "by year", "by week", "by day",
            "per day", "per week", "over the last", "history of", "historical"],
        2: ["growth", "increase", "decrease", "rise", "fall", "change",
            "evolution", "progress", "since", "each month", "each year"],
        1: ["by date", "timeline", "period"],
    },
    "COMPARISON": {
        3: ["compare", "comparison", "versus", " vs ", "compared to",
            "difference between", "against each other",
            r"\b(?:for|in|of|by)[ ]each\b", r"\beach (?!other\b)[a-z]+\b.{0,20}\b(?:has|have|had|is|are|was|were)\b"],
        2: ["by region", "by department", "by category", "by product",
            "by team", "by branch", "across", "between"],
        1: ["each", r"\bper[ ]"],
    },
    "RANKING": {
        3: ["top ", "bottom ", "highest", "lowest", "best performing",
            "worst performing", "rank", "ranked", "leaderboard", "most ",
            "least ", "largest", "smallest", "biggest",
            "fewest", "greatest", "youngest", "oldest", "most common", "earliest",
            "latest", "longest", "shortest"],
        2: ["best", "worst", "leading", "order by", "sorted by",
            r"\bfirst[ ](?:\d+|few|ten|five|three)\b", r"\bthe first [a-z]+ (?:to|who|that)\b",
            "sort ", "sorted", "ordered by", "ascending", "descending", "alphabetical"],
        1: ["maximum", "minimum"],
    },
    "PROPORTION": {
        3: ["percentage of", "share of", "proportion", "what portion",
            "breakdown of", "composition", "% of total", "makes up",
            "contribution of"],
        2: ["split by", "distribution across", "ratio", "percent"],
        1: ["part of"],
    },
    "DISTRIBUTION": {
        3: ["distribution of", "histogram", "spread of", "how are .* distributed",
            "frequency of", "range of values"],
        2: ["variance", "standard deviation", "dispersion", "spread",
            "how many fall"],
        1: ["buckets", "bins"],
    },
    "CORRELATION": {
        3: ["correlation", "correlated", "correlate", "relationship between",
            "does .* affect", "impact of .* on", "influence of"],
        2: ["scatter", "associated with", "depend on", "vary with"],
        1: ["against"],
    },
    "ANOMALY_DETECTION": {
        3: ["anomaly", "anomalies", "outlier", "outliers", "unusual",
            "abnormal", "unexpected", "suspicious", "irregular", "spike",
            "spikes", "sudden drop", "out of the ordinary"],
        2: ["strange", "odd", "flag", "deviation", "deviates"],
        1: ["weird"],
    },
    "KPI_SINGLE_VALUE": {
        3: ["total number of", "how many", "how much", "what is the total",
            "what is the average", "overall total", "sum of all", "count of",
            "count the", "find the number of", "what is the number of",
            r"\bthe number of (?!the\b|a\b|an\b|this\b|that\b|his\b|her\b)[a-z]",
            "give the number of", "return the number of",
            r"\b(?:minimum|maximum|average|mean|total)\b(?:,| and)[ ](?:the )?"
            r"(?:minimum|maximum|average|mean|total)\b"],
        2: ["total", "average", "mean", "median", "overall",
            r"\bnumber of (?!the\b|a\b|an\b|this\b|that\b|his\b|her\b)[a-z]"],
        1: ["value of"],
    },
    "DETAIL_LOOKUP": {
        3: ["list all", "show me all", "give me the records", "which rows",
            "details of", "look up", "find the record", "who is", "what is the name of"],
        2: ["list", "show all", "records", "entries", "rows"],
        1: ["find", "get", "show",
            r"^(?:(?:what|which) (?:are|is|was|were) the [a-z]+"
            r"|(?:return|give|tell me|find|show|list|display|provide) (?:me )?"
            r"(?:the|all|a|an|each|every)\b|(?:which|what|who|where)[ ])"],
    },
}

PREDICTION_DECLINED = re.compile(
    r"\b(?:no|not|without|don'?t|do not|never|skip|exclude|excluding|leave out)\s+"
    r"(?:\w+\s+){0,2}?(?:forecasts?|forecasting|predictions?|predict|projections?|project)\b"
)

PREDICTION_EXPLICIT = [
    "predict", "prediction", "forecast", "forecasting", "project",
    "projection", "projected", "next month", "next quarter", "next year",
    "next week", "tomorrow", "will we", "will i ", "will our",
    "next 3", "next three", "next few", "coming months", "upcoming",
    "will be", "expect", "expected", "estimate for", "future", "outlook",
    "how much will", "what will",
    "will they", "will it", "will this", "continue", "going forward",
    "worsen", "recover", "keep rising", "keep falling", "trending toward",
]

WHAT_IF_MARKERS = [
    "what if", "what-if", "suppose", "assuming", "if i ", "if we ",
    "scenario", "simulate", "hypothetically", "were to",
]


def normalize(text: str) -> str:
    t = (text or "").lower().strip()
    t = re.sub(r"[‘’“”]", "'", t)
    t = re.sub(r"\s+", " ", t)
    return t


# ==========================================================================
# Copied from response_intent.py (stage 8)
# ==========================================================================

_NEUTRAL_PHRASES = [
    (re.compile(r"\bat (?:least|most)\b"), "thresholdfilter"),
    (re.compile(r"\b(?:no|not) (?:more|less|fewer|greater) than\b"), "thresholdfilter"),
    (re.compile(r"\b(?:more|less|fewer) than (?:a |one )?single\b"), "thresholdfilter"),
    (re.compile(r"\bthan\s+(?:the\s+)?(?:overall\s+)?(?:average|mean|minimum|maximum)\b"),
     "than normfilter"),
    (re.compile(r"\b(?:above|below|over|under)\s+(?:the\s+)?(?:overall\s+)?(?:average|mean)\b"),
     "normfilter"),
    (re.compile(r"\b(first|last|middle|full|given|family|maiden)\s+(names?)\b"), r"\1\2"),
    (re.compile(r"\bacross all\b"), "overall"),
]


def neutralize(text: str) -> str:
    """Rewrite threshold, average-filter and name phrases (see _NEUTRAL_PHRASES)."""
    for pattern, replacement in _NEUTRAL_PHRASES:
        text = pattern.sub(replacement, text)
    return text


_PER_ROW_COUNT = re.compile(
    r"\b(?:names?|ids?)\b.{0,60}\b(?:and|with) (?:the )?(?:number of|count of|how many)\b"
    r"|\bhow many\b.{0,40}\b(?:they|them|each of them)\b"
)

# ==========================================================================
# Local additions (not in stage 8)
# ==========================================================================

# Wording seen in this demo's questions that the stage-8 lexicon misses
# ("give me gender variation in my company").
EXTRA_INTENT_MARKERS = {
    "PROPORTION": {
        2: ["variation", "distribution", "make-up", "makeup", "breakdown"],
    },
}

# A win on a single weak marker (total evidence <= 1) is a guess. The stage-8
# formula gives it about 0.89, which would stop the AI from being consulted.
WEAK_EVIDENCE_MAX_SCORE = 1.0
WEAK_EVIDENCE_CONFIDENCE_CAP = 0.50

# Stage-8 forecast markers split by reliability. The strong ones name a
# forecast outright; the rest ("next month", "will be", "expect", "continue")
# also occur in plain historical or filtering questions, so they only suggest
# a forecast and leave the decision to the AI.
STRONG_PREDICTION_MARKERS = ("predict", "prediction", "forecast", "forecasting",
                             "projection", "projected")

PREDICTION_CONFIDENCE = {
    "DECLINED": 0.97,
    "EXPLICIT": 0.90,
    "SOFT": 0.50,
    "NONE": 0.80,
}


def _merged_markers() -> Dict[str, Dict[int, List[str]]]:
    merged = {intent: {w: list(m) for w, m in tiers.items()} for intent, tiers in INTENT_MARKERS.items()}
    for intent, tiers in EXTRA_INTENT_MARKERS.items():
        for weight, markers in tiers.items():
            merged[intent].setdefault(weight, []).extend(markers)
    return merged


_MARKERS = _merged_markers()


def _marker_found(marker: str, text: str) -> bool:
    """Marker matching exactly as stage 8's _score_intents does it."""
    pattern = marker.strip()
    if any(c in pattern for c in ".*[]"):
        return re.search(pattern, text) is not None
    if pattern[0].isalnum():
        return re.search(r"(?<![a-z0-9])" + re.escape(pattern), text) is not None
    return pattern in text


# ==========================================================================
# Scoring and resolution (copied logic from query_analyzer.py stage 8)
# ==========================================================================


def _score_intents(text: str) -> Tuple[dict, dict]:
    """Accumulate weighted marker evidence for every intent."""
    scores = {intent: 0.0 for intent in _MARKERS}
    hits = {intent: [] for intent in _MARKERS}
    for intent, tiers in _MARKERS.items():
        for weight, markers in tiers.items():
            for marker in markers:
                if _marker_found(marker, text):
                    scores[intent] += float(weight)
                    hits[intent].append(marker.strip())
    return scores, hits


def _resolve_intent(text: str, scores: dict, hits: dict) -> Tuple[str, float, str]:
    """Pick the primary intent with stage-8 precedence rules and confidence."""
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, best_score = ranked[0]
    runner_score = ranked[1][1] if len(ranked) > 1 else 0.0

    if best_score == 0:
        return UNKNOWN, 0.2, "No decisive lexical markers found."

    grouped = (re.search(r"\b(?:for|in|of|by|to) each\b|\bper\b|\beach (?!other\b)[a-z]+"
                         r"|\beach\s*[?.!]?$", text)
               or _PER_ROW_COUNT.search(text))
    superlative = re.search(
        r"\b(?:most|least|highest|lowest|largest|smallest|biggest|greatest|fewest"
        r"|youngest|oldest|earliest|latest|longest|shortest|top|bottom)\b", text)
    kpi_explicit = re.search(
        r"\bhow (?:many|much)\b|\btotal\b|\baverage\b|\bmean\b|\bcount (?:the|of)\b|\bsum\b",
        text)
    if scores["ANOMALY_DETECTION"] >= 3:
        best = "ANOMALY_DETECTION"
    elif scores["CORRELATION"] >= 3:
        best = "CORRELATION"
    elif scores["RANKING"] >= 3 and re.search(r"top\s+\d+|bottom\s+\d+", text):
        best = "RANKING"
    elif scores["PROPORTION"] >= 3 and best == "COMPARISON":
        best = "PROPORTION"
    elif (superlative and scores["RANKING"] >= 3
          and (best == "DETAIL_LOOKUP"
               or (best == "KPI_SINGLE_VALUE" and not kpi_explicit))):
        best = "RANKING"
    elif (best == "DETAIL_LOOKUP" and grouped
          and re.search(r"\b(?:number|count) of\b|\bhow many\b|\b(?:total|average|sum)\b", text)):
        best = "COMPARISON"
    elif (best == "KPI_SINGLE_VALUE" and grouped
          and scores["TREND_ANALYSIS"] < 3):
        best = "COMPARISON"
    elif (
        scores["TREND_ANALYSIS"] >= 3
        and best == "KPI_SINGLE_VALUE"
        and scores["KPI_SINGLE_VALUE"] < scores["TREND_ANALYSIS"] + 2
    ):
        best = "TREND_ANALYSIS"

    best_score = scores[best]
    separation = (best_score - runner_score) / max(best_score, 1.0)
    saturation = min(best_score / 6.0, 1.0)
    confidence = round(min(0.35 + 0.5 * separation + 0.25 * saturation, 0.97), 4)

    marker_note = ", ".join(f"'{h}'" for h in hits[best][:3]) or "structural cues"
    rationale = f"Matched {marker_note} (evidence {best_score:.0f} vs next {runner_score:.0f})."
    return best, confidence, rationale


# ==========================================================================
# Public calculations
# ==========================================================================


def _prediction_marker_found(marker: str, text: str, plural: bool) -> bool:
    """
    Whole-word match with inflections, so "project" is not found in "projects"
    and "expect" is not found in "unexpected" (stage 8 used plain substrings).
    """
    suffix = r"(?:s|ed|ing)?" if plural else r"(?:ed|ing)?"
    pattern = r"(?<![a-z0-9])" + re.escape(marker.strip()) + suffix + r"(?![a-z0-9])"
    return re.search(pattern, text) is not None


def rule_prediction(question: str) -> Tuple[bool, float, str]:
    """
    Stage-8 prediction triggers, question only: (prediction_needed, confidence, trigger).

    DECLINED  -> False, 0.97   the user turned a forecast down
    EXPLICIT  -> True,  0.90   strong forecast word, or a what-if scenario
    SOFT      -> True,  0.50   only a soft future cue: below threshold, the AI decides
    NONE      -> False, 0.80   no forecast cue
    """
    text = normalize(question)
    what_if = any(m in text for m in WHAT_IF_MARKERS)
    if PREDICTION_DECLINED.search(text) and not what_if:
        trigger = "DECLINED"
    elif what_if or any(_prediction_marker_found(m, text, plural=True) for m in STRONG_PREDICTION_MARKERS):
        trigger = "EXPLICIT"
    elif any(_prediction_marker_found(m, text, plural=False) for m in PREDICTION_EXPLICIT):
        trigger = "SOFT"
    else:
        trigger = "NONE"
    return trigger in ("EXPLICIT", "SOFT"), PREDICTION_CONFIDENCE[trigger], trigger


def rule_intent(question: str) -> Tuple[str, float, str]:
    """Return (intent, confidence, rationale). UNKNOWN means no usable evidence."""
    text = normalize(question)
    scored_text = neutralize(text)
    scores, hits = _score_intents(scored_text)
    intent, confidence, rationale = _resolve_intent(scored_text, scores, hits)

    if intent != UNKNOWN and scores[intent] <= WEAK_EVIDENCE_MAX_SCORE:
        confidence = min(confidence, WEAK_EVIDENCE_CONFIDENCE_CAP)
        rationale += " Weak evidence only; confidence capped."

    # Stage 8 promotes a lookup or scalar reading to a trend when a forecast is
    # explicitly requested, since a forecast presupposes a time series. Only
    # strong forecast cues promote here; a soft cue is left to the AI.
    _, _, trigger = rule_prediction(question)
    if trigger == "EXPLICIT" and intent in ("KPI_SINGLE_VALUE", "DETAIL_LOOKUP", UNKNOWN):
        rationale += f" Promoted from {intent} to TREND_ANALYSIS: an explicit forecast presupposes a time series."
        intent = "TREND_ANALYSIS"
        confidence = max(confidence, 0.75)

    return intent, round(confidence, 4), rationale
