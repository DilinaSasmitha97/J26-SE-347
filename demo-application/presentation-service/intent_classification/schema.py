"""
Contract for the question-only intent classification step.

    POST /api/v4/classify-intent
    request:  {"nl_query": "..."}
    response: {"nl_query": "...", "intent": "...", "presentation_types": [...],
               "prediction_needed": bool}

The request accepts nothing but the question: no schema, policy, user claims or
SQL. Extra fields are rejected so context cannot leak into classification.
Confidences are logged by the service and never appear in the response.
"""

from dataclasses import dataclass
from typing import Any, List, Literal, Tuple, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

PresentationType = Literal[
    "table", "single_value", "bar_chart", "pie_chart", "line_chart", "summary"
]
PRESENTATION_TYPES: Tuple[str, ...] = get_args(PresentationType)

Intent = Literal[
    "TREND_ANALYSIS", "COMPARISON", "RANKING", "PROPORTION", "DISTRIBUTION",
    "CORRELATION", "ANOMALY_DETECTION", "KPI_SINGLE_VALUE", "DETAIL_LOOKUP",
]
INTENTS: Tuple[str, ...] = get_args(Intent)

MAX_QUERY_CHARS = 2000


class ClassifyIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nl_query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS)

    @field_validator("nl_query")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nl_query must contain a question, not only whitespace")
        return value


class ClassifyIntentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nl_query: str
    intent: Intent
    presentation_types: List[PresentationType] = Field(min_length=1)
    prediction_needed: StrictBool

    @field_validator("presentation_types")
    @classmethod
    def _unique(cls, value: List[str]) -> List[str]:
        if len(set(value)) != len(value):
            raise ValueError("presentation_types must not contain duplicates")
        return value


class ModelOutputError(ValueError):
    """The model answered, but not with a usable classification."""


@dataclass
class ModelClassification:
    intent: str
    intent_confidence: float
    presentation_types: List[str]
    presentation_types_confidence: float
    prediction_needed: bool
    prediction_confidence: float


def _confidence(value: Any) -> float:
    """A missing or non-numeric confidence counts as 0, so it is never trusted."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return max(0.0, min(float(value), 1.0))


def parse_model_output(raw: Any) -> ModelClassification:
    """
    Validate an LLM classification strictly.

    The intent must be one of the nine labels; presentation types must be a
    non-empty list of the six allowed values (trimmed, lower-cased, repeats
    collapsed in order); prediction_needed must be a Boolean. Any violation
    makes the whole answer unusable. Confidences are clamped to 0-1. Any
    `nl_query` the model returns is ignored: the caller echoes the question.
    """
    if not isinstance(raw, dict):
        raise ModelOutputError("model output is not a JSON object")

    intent = raw.get("intent")
    if not isinstance(intent, str) or intent.strip().upper() not in INTENTS:
        raise ModelOutputError(f"intent {intent!r} is not allowed")

    types = raw.get("presentation_types")
    if not isinstance(types, list) or not types:
        raise ModelOutputError("presentation_types must be a non-empty list")

    selected: List[str] = []
    for value in types:
        if not isinstance(value, str):
            raise ModelOutputError(f"presentation type {value!r} is not a string")
        name = value.strip().lower()
        if name not in PRESENTATION_TYPES:
            raise ModelOutputError(f"presentation type {value!r} is not allowed")
        if name not in selected:
            selected.append(name)

    prediction = raw.get("prediction_needed")
    if not isinstance(prediction, bool):
        raise ModelOutputError("prediction_needed must be a Boolean")

    return ModelClassification(
        intent=intent.strip().upper(),
        intent_confidence=_confidence(raw.get("intent_confidence")),
        presentation_types=selected,
        presentation_types_confidence=_confidence(raw.get("presentation_types_confidence")),
        prediction_needed=prediction,
        prediction_confidence=_confidence(raw.get("prediction_confidence")),
    )
