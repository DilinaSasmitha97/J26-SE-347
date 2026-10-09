"""
Question-only intent classifier: rules first, AI (LLM) only when the rules are unsure.

  1. The rules always run and give intent, presentation types and
     prediction_needed, each with a confidence.
  2. A decision whose rule confidence is at least RULE_TRUST_THRESHOLD is final.
  3. If any decision is weaker, the LLM is asked once (when a provider key is
     configured). Each weak decision takes the LLM's answer only when the LLM's
     own confidence for it is at least LLM_TRUST_THRESHOLD; otherwise the rule
     answer stays. No key, a provider error or unusable output keeps the rules.
  4. Formats the user did not name must fit the final intent.
  5. Hard guards win last: a declined forecast, "only <format>", excluded formats.

Confidences and the deciding source are written to the service log only; the
response carries the four contract fields. The question is echoed unchanged.

This module has no access to schema, policy, user claims, SQL, database rows or
forecasting code.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import llm
from profiler import log_step

from . import fallback_rules, vonara_rules
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .schema import ClassifyIntentResponse, parse_model_output

RULE_TRUST_THRESHOLD = 0.55
LLM_TRUST_THRESHOLD = 0.60
LLM_ATTEMPTS = 1  # one attempt keeps the click responsive; the rules cover failures

FIELDS = ("intent", "presentation_types", "prediction_needed")
FALLBACK_INTENT = "DETAIL_LOOKUP"  # used when the rules find no intent and the AI cannot help


@dataclass
class Decision:
    value: object
    confidence: float
    source: str  # "rules" | "llm"


@dataclass
class ClassificationDetails:
    decisions: Dict[str, Decision]
    rule_decisions: Dict[str, Decision]
    rule_intent_label: str
    prediction_trigger: str
    llm_status: str  # not-needed | unavailable | used | failed: <reason>
    classified_by: str
    formats_named_by_user: bool = False
    notes: List[str] = field(default_factory=list)


def _rule_decisions(nl_query: str) -> Tuple[Dict[str, Decision], str, str, bool]:
    label, intent_conf, _rationale = vonara_rules.rule_intent(nl_query)
    intent = FALLBACK_INTENT if label == vonara_rules.UNKNOWN else label
    types, types_conf, named = fallback_rules.rule_presentation_types(nl_query, intent, intent_conf)
    prediction, prediction_conf, trigger = vonara_rules.rule_prediction(nl_query)
    return {
        "intent": Decision(intent, intent_conf, "rules"),
        "presentation_types": Decision(types, types_conf, "rules"),
        "prediction_needed": Decision(prediction, prediction_conf, "rules"),
    }, label, trigger, named


def _ask_llm(nl_query: str):
    raw, _stats = llm.call_llm_json(SYSTEM_PROMPT, build_user_prompt(nl_query), retries=LLM_ATTEMPTS)
    return parse_model_output(raw)


def classify_intent_detailed(nl_query: str) -> Tuple[dict, ClassificationDetails]:
    rules, rule_label, trigger, named = _rule_decisions(nl_query)
    final = dict(rules)
    weak = [name for name in FIELDS if rules[name].confidence < RULE_TRUST_THRESHOLD]

    llm_status = "not-needed"
    if weak:
        if not llm.is_available():
            llm_status = "unavailable"
        else:
            try:
                model = _ask_llm(nl_query)
                llm_status = "used"
                offered = {
                    "intent": (model.intent, model.intent_confidence),
                    "presentation_types": (model.presentation_types, model.presentation_types_confidence),
                    "prediction_needed": (model.prediction_needed, model.prediction_confidence),
                }
                for name in weak:
                    value, confidence = offered[name]
                    if confidence >= LLM_TRUST_THRESHOLD:
                        final[name] = Decision(value, confidence, "llm")
            except Exception as exc:  # noqa: BLE001 - any AI failure keeps the rule answers
                llm_status = f"failed: {exc}"
                log_step(f"Intent classification kept the rule answers; AI failed: {exc}", level="WARN")

    notes: List[str] = []
    intent = final["intent"].value
    types_decision = final["presentation_types"]

    # The AI replaced a weak intent but not the formats: formats derived from
    # the old rule intent are re-derived for the new one.
    if final["intent"].source == "llm" and types_decision.source == "rules" and not named:
        types, _, _ = fallback_rules.rule_presentation_types(nl_query, intent, final["intent"].confidence)
        types_decision = Decision(types, final["intent"].confidence, "rules")
        notes.append("formats re-derived for the AI intent")

    types = list(types_decision.value)
    if not named:
        fitted = fallback_rules.fit_to_intent(types, intent)
        if fitted != types:
            notes.append(f"formats fitted to {intent}")
        types = fitted

    # Hard guards.
    excluded = fallback_rules.excluded_formats(nl_query)
    if excluded:
        types = [name for name in types if name not in excluded] or (
            ["summary"] if "table" in excluded else ["table"])
    only = fallback_rules.explicit_only_formats(nl_query)
    if only:
        types = only
    prediction = final["prediction_needed"]
    if prediction.value and fallback_rules.prediction_declined(nl_query):
        prediction = Decision(False, prediction.confidence, prediction.source)
        notes.append("declined forecast enforced")
    final["presentation_types"] = Decision(types, types_decision.confidence, types_decision.source)
    final["prediction_needed"] = prediction

    sources = {final[name].source for name in FIELDS}
    classified_by = "rules+llm" if len(sources) > 1 else sources.pop()

    response = ClassifyIntentResponse(
        nl_query=nl_query,
        intent=final["intent"].value,
        presentation_types=final["presentation_types"].value,
        prediction_needed=final["prediction_needed"].value,
    )
    details = ClassificationDetails(
        decisions=final, rule_decisions=rules, rule_intent_label=rule_label,
        prediction_trigger=trigger, llm_status=llm_status, classified_by=classified_by,
        formats_named_by_user=named, notes=notes,
    )
    log_step(_log_line(details))
    return response.model_dump(), details


def classify_intent(nl_query: str) -> dict:
    """Return {"nl_query", "intent", "presentation_types", "prediction_needed"}."""
    response, _details = classify_intent_detailed(nl_query)
    return response


def _describe(details: ClassificationDetails, name: str) -> str:
    decision = details.decisions[name]
    rule = details.rule_decisions[name]
    text = f"{decision.source} {decision.confidence:.2f}"
    if decision.source == "llm":
        rule_value = details.rule_intent_label if name == "intent" else rule.value
        text += f"; rules {rule_value} {rule.confidence:.2f}"
    if name == "prediction_needed":
        text += f", trigger {details.prediction_trigger}"
    return text


def _log_line(details: ClassificationDetails) -> str:
    d = details.decisions
    line = (
        f"Intent classified | intent={d['intent'].value} ({_describe(details, 'intent')})"
        f" | types={d['presentation_types'].value} ({_describe(details, 'presentation_types')})"
        f" | prediction={d['prediction_needed'].value} ({_describe(details, 'prediction_needed')})"
        f" | classified_by={details.classified_by} | llm={details.llm_status}"
    )
    if details.notes:
        line += f" | notes: {'; '.join(details.notes)}"
    return line
