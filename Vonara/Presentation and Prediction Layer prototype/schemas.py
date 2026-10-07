"""
Formal taxonomies and the canonical output contract for Component 4.

Everything the layer emits is validated against the structures declared here.
Keeping the vocabulary in one module is what makes the research claims
falsifiable: the intent set is closed, the model set is closed, and the
readiness verdicts are closed, so accuracy can be measured against them.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum

ANALYSIS_SCHEMA_VERSION = "1.0"


# ==========================================================================
# Part 1 - Intent taxonomy
# ==========================================================================


class QueryIntent(str, Enum):
    """
    Closed set of semantic intents a result-returning query can express.

    Chosen to be jointly exhaustive over the Spider/BIRD question styles and
    the synthetic business questions in `intent_testset.json`, while staying
    small enough that each intent maps to a distinct visual encoding.
    """

    TREND_ANALYSIS = "TREND_ANALYSIS"        # value of a metric over time
    COMPARISON = "COMPARISON"                # metric across a few categories
    RANKING = "RANKING"                      # ordered top-N / bottom-N
    PROPORTION = "PROPORTION"                # part-to-whole composition
    DISTRIBUTION = "DISTRIBUTION"            # spread/shape of one variable
    CORRELATION = "CORRELATION"              # relationship between 2 measures
    ANOMALY_DETECTION = "ANOMALY_DETECTION"  # outliers / unusual behaviour
    KPI_SINGLE_VALUE = "KPI_SINGLE_VALUE"    # one scalar answer
    DETAIL_LOOKUP = "DETAIL_LOOKUP"          # row-level record retrieval
    UNKNOWN = "UNKNOWN"                      # low-confidence escape hatch


ALL_INTENTS = [i.value for i in QueryIntent if i is not QueryIntent.UNKNOWN]


# ==========================================================================
# Part 1b - Response (presentation) intent taxonomy
# ==========================================================================
#
# `QueryIntent` above answers "what is the user asking *about*". It is an
# analytical taxonomy and it stays internal: prediction and chart-grammar
# selection both read it.
#
# `ResponseIntent` answers the orthogonal question "what SHAPE must the reply
# take". It is the taxonomy the user sees, and it is the one that decides
# which blocks the response envelope emits. Keeping the two apart is what
# lets "what is the highest invoice" and "how many invoices" - two different
# analytical intents (RANKING and KPI_SINGLE_VALUE) - both resolve to one
# scalar answer, while "revenue by month" and "revenue by region" - also two
# different analytical intents - both resolve to a chart.
#
# The set is closed and exhaustive: every request resolves to exactly one of
# the five. There is deliberately no UNKNOWN member, because a presentation
# layer must always render something; low confidence is expressed through the
# confidence score and a warning, never through an unrenderable label.


class ResponseIntent(str, Enum):
    """Closed set of output shapes the presentation layer can emit."""

    SINGLE_ANSWER = "SINGLE_ANSWER"    # one scalar / one record: a direct answer
    SHORT_SUMMARY = "SHORT_SUMMARY"    # a few sentences of narrative, no grid
    TABLE_CONTENT = "TABLE_CONTENT"    # the dataset itself, as rows
    CHART = "CHART"                    # a visual encoding of the dataset
    MIXED_SUMMARY = "MIXED_SUMMARY"    # summary + table + chart in one reply


ALL_RESPONSE_INTENTS = [i.value for i in ResponseIntent]

# Not a sixth intent - a *precondition*. "hello" and "qwertyuiop" have no
# correct response shape, because they are not requests for data at all.
# Before this existed they were labelled with the fallback and the engine
# returned the fallback, so they scored correct by construction and tested
# nothing. A request that fails this check still carries a renderable intent
# (the layer must always render something), but `is_data_request` is False and
# the interface is expected to ask for clarification instead of showing an
# empty table. Used as a gold label in the corpora, where it is a real test.
NOT_A_DATA_REQUEST = "NOT_A_DATA_REQUEST"

# Default when nothing can be decided at all. TABLE_CONTENT is the safe
# default because rendering the raw rows never asserts anything the data does
# not contain - a chart or a narrative both add interpretation.
DEFAULT_RESPONSE_INTENT = ResponseIntent.TABLE_CONTENT


class ResponseBlock(str, Enum):
    """The renderable units a response is assembled from."""

    ANSWER = "ANSWER"     # headline scalar with its label and unit
    SUMMARY = "SUMMARY"   # verified narrative prose
    TABLE = "TABLE"       # column definitions + rows
    CHART = "CHART"       # Vega-Lite spec


# The contract that makes the taxonomy testable: an intent is exactly its
# ordered block list, and the renderer may emit nothing else.
RESPONSE_BLOCKS = {
    ResponseIntent.SINGLE_ANSWER: (ResponseBlock.ANSWER,),
    ResponseIntent.SHORT_SUMMARY: (ResponseBlock.SUMMARY,),
    ResponseIntent.TABLE_CONTENT: (ResponseBlock.TABLE,),
    ResponseIntent.CHART: (ResponseBlock.CHART,),
    ResponseIntent.MIXED_SUMMARY: (
        ResponseBlock.SUMMARY,
        ResponseBlock.TABLE,
        ResponseBlock.CHART,
    ),
}


@dataclass
class ResponseIntentResult:
    """Full, auditable outcome of one presentation-intent classification."""

    intent: str = DEFAULT_RESPONSE_INTENT.value
    confidence: float = 0.0
    source: str = "RULE"            # RULE | LLM | HYBRID | ANALYTIC_PRIOR | GUARDRAIL
    rationale: str = ""
    blocks: list = field(default_factory=list)

    # Which half of the answer the user actually asked for. "which department
    # spends the most" wants the department name with the figure as support;
    # "how much did engineering spend" wants the figure with the department as
    # support. Same row, same intent, opposite emphasis.
    answer_focus: str = "VALUE"     # VALUE | ENTITY

    # Was this a request for data at all? False for greetings, acknowledgements
    # and gibberish. `intent` still holds a renderable shape when this is
    # False, but the interface should clarify rather than render it.
    is_data_request: bool = True
    not_a_request_reason: str = ""

    # How the verdict was reached, which is not the same as how confident it
    # is. A FALLBACK hit that happens to match the gold label is not the same
    # kind of success as a DIRECT one, and reporting them together overstates
    # accuracy - see `evaluate_response_intent.py`.
    #   DIRECT   - markers the user actually wrote decided it
    #   INFERRED - the lexicon was inconclusive; the analytical intent decided
    #   FALLBACK - no evidence of any kind; the default was returned
    evidence_grade: str = "DIRECT"

    # Evidence trail - every number the verdict was derived from.
    scores: dict = field(default_factory=dict)
    matched_markers: dict = field(default_factory=dict)
    runner_up: str = ""
    margin: float = 0.0

    # Repairs applied after the result set was seen.
    guardrails_applied: list = field(default_factory=list)
    original_intent: str = ""
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "confidence": round(float(self.confidence), 4),
            "source": self.source,
            "rationale": self.rationale,
            "blocks": list(self.blocks),
            "answer_focus": self.answer_focus,
            "is_data_request": self.is_data_request,
            "not_a_request_reason": self.not_a_request_reason,
            "evidence_grade": self.evidence_grade,
            "evidence": {
                "scores": {k: round(float(v), 2) for k, v in self.scores.items()},
                "matched_markers": self.matched_markers,
                "runner_up": self.runner_up,
                "margin": round(float(self.margin), 4),
            },
            "guardrails_applied": self.guardrails_applied,
            "original_intent": self.original_intent or self.intent,
            "warnings": self.warnings,
        }


# ==========================================================================
# Prediction Stage 1 - Intent-to-Prediction mapping vocabulary
# ==========================================================================


class PredictionStrategy(str, Enum):
    """What *kind* of predictive question the intent implies."""

    TEMPORAL_FORECAST = "TEMPORAL_FORECAST"          # extend a series forward
    CATEGORY_TRAJECTORY = "CATEGORY_TRAJECTORY"      # which category leads next
    DISTRIBUTION_SHIFT = "DISTRIBUTION_SHIFT"        # how the spread moves
    ANOMALY_PERSISTENCE = "ANOMALY_PERSISTENCE"      # will the anomaly worsen
    NONE = "NONE"                                    # prediction not meaningful


class ForecastModel(str, Enum):
    """Closed set of forecasting models the selection engine may choose."""

    SARIMA = "SARIMA"
    LINEAR_REGRESSION = "LINEAR_REGRESSION"
    EXPONENTIAL_SMOOTHING = "EXPONENTIAL_SMOOTHING"
    WEIGHTED_MOVING_AVERAGE = "WEIGHTED_MOVING_AVERAGE"
    # Benchmarks. Every accuracy claim is stated relative to these, and the
    # selection guard falls back to one when the chosen model cannot beat it
    # on the series' own history.
    NAIVE = "NAIVE"                        # next value = last value
    SEASONAL_NAIVE = "SEASONAL_NAIVE"      # next value = same period last cycle
    NONE = "NONE"


# ==========================================================================
# Prediction Stage 2 - Data readiness verdicts
# ==========================================================================


class ReadinessVerdict(str, Enum):
    READY = "READY"                              # all three gates passed
    NOT_REQUESTED = "NOT_REQUESTED"              # gates never run: no forecast asked
    NOT_TEMPORAL = "NOT_TEMPORAL"                # no usable time axis
    INSUFFICIENT_POINTS = "INSUFFICIENT_POINTS"  # too few observations
    LOW_SIGNAL = "LOW_SIGNAL"                    # noise dominates
    DEGENERATE = "DEGENERATE"                    # constant / all-null series
    MULTI_SERIES = "MULTI_SERIES"                # one series per category: forecast each
    NOT_AGGREGATED = "NOT_AGGREGATED"            # several raw rows per period
    INCOMPLETE = "INCOMPLETE"                    # too many missing values / periods
    TRUNCATED = "TRUNCATED"                      # result cut at the security layer's row cap


# ==========================================================================
# Column semantics (shared by visualization and prediction)
# ==========================================================================


class ColumnRole(str, Enum):
    TEMPORAL = "TEMPORAL"        # date / datetime / period label
    MEASURE = "MEASURE"          # continuous numeric quantity
    DIMENSION = "DIMENSION"      # low-cardinality categorical
    IDENTIFIER = "IDENTIFIER"    # high-cardinality key-like
    BOOLEAN = "BOOLEAN"
    UNSUPPORTED = "UNSUPPORTED"


class Granularity(str, Enum):
    HOUR = "HOUR"
    DAY = "DAY"
    WEEK = "WEEK"
    MONTH = "MONTH"
    QUARTER = "QUARTER"
    YEAR = "YEAR"
    NONE = "NONE"


# Periods per year, used to seed SARIMA seasonality and to widen intervals.
SEASONAL_PERIOD = {
    Granularity.HOUR: 24,
    Granularity.DAY: 7,
    Granularity.WEEK: 52,
    Granularity.MONTH: 12,
    Granularity.QUARTER: 4,
    Granularity.YEAR: 1,
    Granularity.NONE: 1,
}


# ==========================================================================
# Query-understanding output (Part 1 - the analyzer contract)
# ==========================================================================


@dataclass
class TableBinding:
    table: str
    role: str = "FACT"              # FACT | DIMENSION | BRIDGE
    confidence: float = 0.0
    matched_terms: list = field(default_factory=list)


@dataclass
class ColumnBinding:
    table: str
    column: str
    role: str = ColumnRole.UNSUPPORTED.value
    data_type: str = "UNKNOWN"
    is_pii: bool = False
    confidence: float = 0.0
    matched_terms: list = field(default_factory=list)


@dataclass
class MetricSpec:
    column: str
    aggregation: str = "SUM"        # SUM | AVG | COUNT | MIN | MAX | NONE
    table: str = ""


@dataclass
class HorizonSpec:
    value: int = 0
    unit: str = Granularity.NONE.value
    source: str = "NONE"            # EXPLICIT | INFERRED | NONE


@dataclass
class WhatIfSpec:
    present: bool = False
    raw_clause: str = ""
    parameter: str = ""             # the metric being perturbed
    direction: str = ""             # INCREASE | DECREASE | SET
    magnitude_pct: float = 0.0


@dataclass
class QueryAnalysis:
    """
    The comprehensive, machine-checkable understanding of one user request.

    This object is the single input contract for every downstream stage:
    visualization reads `visualization_hint` + `semantic_roles`, prediction
    reads `intent` + `prediction_request`, and summarization reads all of it.
    """

    user_query: str = ""
    normalized_query: str = ""

    # --- analytical intent ---------------------------------------------
    primary_intent: str = QueryIntent.UNKNOWN.value
    secondary_intents: list = field(default_factory=list)
    intent_confidence: float = 0.0
    intent_source: str = "RULE"      # LLM | RULE | HYBRID
    intent_rationale: str = ""

    # --- response (presentation) intent ---------------------------------
    # Decided pre-execution from the question alone, then re-checked against
    # the real result set by the guardrails in `response_intent.py`.
    response_intent: str = DEFAULT_RESPONSE_INTENT.value
    response_intent_confidence: float = 0.0
    response_intent_source: str = "RULE"
    response_intent_rationale: str = ""
    response_blocks: list = field(default_factory=list)
    response_intent_evidence: dict = field(default_factory=dict)
    answer_focus: str = "VALUE"      # VALUE | ENTITY
    is_data_request: bool = True
    not_a_request_reason: str = ""
    response_evidence_grade: str = "DIRECT"   # DIRECT | INFERRED | FALLBACK

    # --- prediction request -------------------------------------------
    prediction_required: bool = False
    prediction_trigger: str = "NONE"  # EXPLICIT | IMPLICIT | NONE
    horizon: HorizonSpec = field(default_factory=HorizonSpec)
    what_if: WhatIfSpec = field(default_factory=WhatIfSpec)

    # --- schema binding -----------------------------------------------
    affected_tables: list = field(default_factory=list)   # list[TableBinding]
    affected_columns: list = field(default_factory=list)  # list[ColumnBinding]
    unresolved_terms: list = field(default_factory=list)

    # --- semantic roles -----------------------------------------------
    metrics: list = field(default_factory=list)           # list[MetricSpec]
    dimensions: list = field(default_factory=list)
    temporal_field: str = ""
    temporal_granularity: str = Granularity.NONE.value
    filters: list = field(default_factory=list)
    ordering: str = ""
    limit: int = 0
    # EXPLICIT when the user stated the bound ("top 10"), INFERRED when a
    # superlative implied one, NONE when the request is genuinely unbounded.
    # Member 1 must not treat an INFERRED limit as a user requirement.
    limit_source: str = "NONE"

    # --- presentation & governance ------------------------------------
    recommended_chart: str = "table"
    chart_alternatives: list = field(default_factory=list)
    chart_rationale: str = ""
    pii_columns_referenced: list = field(default_factory=list)

    # --- diagnostics ---------------------------------------------------
    warnings: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Nested, JSON-serialisable form matching the team interface contract."""
        return {
            "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
            "query_understanding": {
                "user_query": self.user_query,
                "normalized_query": self.normalized_query,
            },
            "intent": {
                "primary_intent": self.primary_intent,
                "secondary_intents": self.secondary_intents,
                "confidence": round(float(self.intent_confidence), 4),
                "intent_source": self.intent_source,
                "rationale": self.intent_rationale,
            },
            "response_intent": {
                "intent": self.response_intent,
                "confidence": round(float(self.response_intent_confidence), 4),
                "source": self.response_intent_source,
                "rationale": self.response_intent_rationale,
                "blocks": self.response_blocks,
                "answer_focus": self.answer_focus,
                "is_data_request": self.is_data_request,
                "not_a_request_reason": self.not_a_request_reason,
                "evidence_grade": self.response_evidence_grade,
                "evidence": self.response_intent_evidence,
            },
            "prediction_request": {
                "prediction_required": self.prediction_required,
                "prediction_trigger": self.prediction_trigger,
                "horizon": asdict(self.horizon),
                "what_if": asdict(self.what_if),
            },
            "schema_binding": {
                "affected_tables": [asdict(t) for t in self.affected_tables],
                "affected_columns": [asdict(c) for c in self.affected_columns],
                "unresolved_terms": self.unresolved_terms,
            },
            "semantic_roles": {
                "metrics": [asdict(m) for m in self.metrics],
                "dimensions": self.dimensions,
                "temporal_field": self.temporal_field,
                "temporal_granularity": self.temporal_granularity,
                "filters": self.filters,
                "ordering": self.ordering,
                "limit": self.limit,
                "limit_source": self.limit_source,
            },
            "visualization_hint": {
                "recommended_chart": self.recommended_chart,
                "alternatives": self.chart_alternatives,
                "rationale": self.chart_rationale,
            },
            "governance": {
                "pii_columns_referenced": self.pii_columns_referenced,
                "read_only": True,
            },
            "warnings": self.warnings,
            "metadata": self.metadata,
        }
