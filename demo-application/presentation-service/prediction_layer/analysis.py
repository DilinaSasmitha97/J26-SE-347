"""
Adapter from the intent classifier's output to the stage functions.

The stage-2..8 prediction code (prediction.py, strategies.py, summarization.py)
reads only a handful of fields from the old analyzer's QueryAnalysis. This
builds exactly those from the new classifier, so the old analyzer is not run
and the classifier stays the single source of intent.
"""

from types import SimpleNamespace

from query_analyzer import _detect_horizon, normalize
from schemas import Granularity, HorizonSpec

DEFAULT_HORIZON = 3


def build_analysis(intent: str, prediction_needed: bool, question: str = "") -> SimpleNamespace:
    """
    Fields read by the stages:
      primary_intent       the classifier's intent
      prediction_required  the classifier's prediction_needed
      prediction_trigger   EXPLICIT when a forecast was asked for: Stage 1 then
                           promotes an intent with no strategy (a KPI) to a
                           temporal forecast, as stage 8 does
      horizon              periods asked for in the question ("next 6 months"),
                           else the default, marked INFERRED
    """
    text = normalize(question or "")
    horizon = _detect_horizon(text)
    if not horizon.value:
        horizon = HorizonSpec(DEFAULT_HORIZON, Granularity.NONE.value, "INFERRED")
    return SimpleNamespace(
        primary_intent=intent or "UNKNOWN",
        prediction_required=bool(prediction_needed),
        prediction_trigger="EXPLICIT" if prediction_needed else "NONE",
        horizon=horizon,
        normalized_query=text,
        temporal_field="",
    )
