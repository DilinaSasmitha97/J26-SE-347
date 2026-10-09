"""
Contract for the question-only intent classification step.

    POST /api/v4/classify-intent
    request:  {"nl_query": "..."}
    response: {"nl_query": "...", "presentation_types": [...], "prediction_needed": bool}

The request accepts nothing but the question: no schema, policy, user claims or
SQL. Extra fields are rejected so context cannot leak into classification.
"""

from typing import Any, List, Literal, Tuple, get_args

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

PresentationType = Literal[
    "table", "single_value", "bar_chart", "pie_chart", "line_chart", "summary"
]
PRESENTATION_TYPES: Tuple[str, ...] = get_args(PresentationType)
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


def parse_model_output(raw: Any) -> Tuple[List[str], bool]:
    """
    Validate an LLM classification strictly.

    Values are compared after trimming and lower-casing; anything outside the
    six allowed types, an empty list, or a non-Boolean prediction flag makes the
    whole answer unusable. Repeated values are collapsed in order. Any
    `nl_query` the model returns is ignored: the caller echoes the submitted
    question itself.
    """
    if not isinstance(raw, dict):
        raise ModelOutputError("model output is not a JSON object")

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

    return selected, prediction
