"""
Question-only presentation classifier.

Uses the service's existing LLM adapter and provider key when one is
configured. Any failure (no key, transport error, malformed or out-of-contract
output) falls back to the deterministic rules, so classification always returns
a valid answer. The response always echoes the submitted question unchanged.

This module deliberately has no access to schema, policy, user claims, SQL,
database rows or forecasting code.
"""

from typing import List, Tuple

import llm
from profiler import log_step

from . import fallback_rules
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .schema import ClassifyIntentResponse, parse_model_output

# One attempt keeps the debounced UI responsive; the rules cover failures.
LLM_ATTEMPTS = 1


def _apply_explicit_instructions(nl_query: str, types: List[str], prediction: bool) -> Tuple[List[str], bool]:
    """Enforce instructions the model is not allowed to overrule."""
    if prediction and fallback_rules.prediction_declined(nl_query):
        prediction = False
    only = fallback_rules.explicit_only_formats(nl_query)
    if only:
        types = only
    return types, prediction


def _classify_with_llm(nl_query: str) -> Tuple[List[str], bool]:
    raw, _stats = llm.call_llm_json(SYSTEM_PROMPT, build_user_prompt(nl_query), retries=LLM_ATTEMPTS)
    types, prediction = parse_model_output(raw)
    return _apply_explicit_instructions(nl_query, types, prediction)


def classify_intent(nl_query: str) -> dict:
    """Return {"nl_query", "presentation_types", "prediction_needed"} for one question."""
    source = "rules"
    types, prediction = None, None
    if llm.is_available():
        try:
            types, prediction = _classify_with_llm(nl_query)
            source = "llm"
        except Exception as exc:  # noqa: BLE001 - every LLM failure falls back to rules
            log_step(f"Intent classification fell back to rules: {exc}", level="WARN")

    if types is None:
        types, prediction = fallback_rules.classify(nl_query)

    response = ClassifyIntentResponse(
        nl_query=nl_query, presentation_types=types, prediction_needed=prediction
    )
    log_step(
        f"Intent classified by {source}: {response.presentation_types}, "
        f"prediction_needed={response.prediction_needed}"
    )
    return response.model_dump()
