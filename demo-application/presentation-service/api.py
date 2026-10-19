"""
REST gateway for Component 4.

Mirrors the conventions of Member 1's FastAPI gateway so the middleware chain
exposes one consistent surface. Three endpoints:

  POST /api/v4/classify-intent  Question-only presentation/prediction classification
  POST /api/v4/render     Data presentation: masked result in the classified formats
  POST /api/v4/predict    Prediction layer: forecast, readiness, anomalies, verified summary
  POST /api/v4/analyze    Part 1 only - called BEFORE SQL generation
  POST /api/v4/present    Full pipeline - called AFTER Member 2 returns rows
  POST /api/v4/simulate   Re-run a what-if against an existing result set
  GET  /api/v4/health     Liveness + capability report

Run:  uvicorn api:app --reload --port 8004
"""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

import data_presentation
import input_adapter
import intent_classification
from intent_classification.schema import Intent, PresentationType
import llm
import pipeline
import prediction_layer

app = FastAPI(
    title="Secure NLIDB - Presentation & Prediction Layer",
    description=(
        "Component 4 of project J26-SE-347. Classifies query intent, generates "
        "adaptive Vega-Lite grammar, produces confidence-bounded forecasts with "
        "dual-dimension anomaly detection, and emits mathematically verified "
        "unified temporal summaries."
    ),
    version=pipeline.PIPELINE_VERSION,
)


# ==========================================================================
# Request models
# ==========================================================================


class SecurityContext(BaseModel):
    """Contract fields supplied by Member 3's access-control layer."""

    tenant_id: str = ""
    user_role: str = ""
    prompt_grounding_rules: str = ""
    denied_tables: List[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    user_query: str = Field(min_length=1, max_length=2000)
    schema_meta: Optional[Any] = None
    security_context: Optional[SecurityContext] = None
    # Deterministic by default (Stage 6). With an LLM provider configured the
    # old default sent every question, and the schema, to the provider.
    use_llm: bool = False


class PresentRequest(BaseModel):
    user_query: str = Field(min_length=1, max_length=2000)
    raw_results: List[Dict[str, Any]] = Field(default_factory=list)
    # Member 2's /api/query response, forwarded unchanged. Takes precedence
    # over `raw_results` when both are sent.
    member2_result: Optional[Dict[str, Any]] = None
    schema_meta: Optional[Any] = None
    schema_types: Optional[Dict[str, str]] = None
    security_context: Optional[SecurityContext] = None
    use_llm: bool = False
    use_llm_summary: bool = False
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    horizon: Optional[int] = Field(default=None, ge=1, le=24)
    scenario_text: str = Field(default="", max_length=1000)
    value_column: Optional[str] = None


class SimulateRequest(BaseModel):
    user_query: str = Field(min_length=1, max_length=2000)
    raw_results: List[Dict[str, Any]] = Field(default_factory=list)
    member2_result: Optional[Dict[str, Any]] = None
    scenario_text: str = Field(min_length=1, max_length=1000)
    schema_meta: Optional[Any] = None
    security_context: Optional[SecurityContext] = None
    horizon: Optional[int] = Field(default=None, ge=1, le=24)


class RenderRequest(BaseModel):
    """Masked result plus the classification it should be shown in."""

    model_config = ConfigDict(extra="forbid")

    member2_result: Dict[str, Any]
    user_query: str = Field(default="", max_length=2000)
    intent: Optional[Intent] = None
    # None means "not classified": formats are then chosen from the data.
    presentation_types: Optional[List[PresentationType]] = Field(default=None, min_length=1)

    @field_validator("presentation_types")
    @classmethod
    def _unique(cls, value):
        if value is not None and len(set(value)) != len(value):
            raise ValueError("presentation_types must not contain duplicates")
        return value


class PredictRequest(BaseModel):
    """Masked result plus the classification that asked for a prediction."""

    model_config = ConfigDict(extra="forbid")

    member2_result: Dict[str, Any]
    user_query: str = Field(default="", max_length=2000)
    intent: Intent
    prediction_needed: StrictBool


def _ctx(model: Optional[SecurityContext]) -> dict:
    return model.model_dump() if model else {}


# ==========================================================================
# Endpoints
# ==========================================================================


@app.get("/api/v4/health")
def health() -> dict:
    """Liveness plus a capability report, so callers can branch on what is available."""
    import importlib.util

    return {
        "status": "UP",
        "component": "Presentation & Prediction Layer",
        "pipeline_version": pipeline.PIPELINE_VERSION,
        "llm_provider": llm.PROVIDER,
        "llm_available": llm.is_available(),
        "active_model": llm.active_model(),
        "capabilities": {
            "sarima": importlib.util.find_spec("statsmodels") is not None,
            "deterministic_fallback": True,
            "grounded_summary_verification": True,
            "intent_classification": True,
        },
    }


@app.post(
    "/api/v4/classify-intent",
    response_model=intent_classification.ClassifyIntentResponse,
)
def classify_intent(request: intent_classification.ClassifyIntentRequest) -> dict:
    """
    Classify the intent, recommend presentation types and say whether a
    forecast is requested.

    Reads only the question: no schema, policy, user claims, SQL or rows. The
    request model rejects any other field. Rules decide first; the LLM is asked
    only for decisions the rules are unsure about. Always answers; confidences
    go to the service log, not the response.
    """
    return intent_classification.classify_intent(request.nl_query)


@app.post("/api/v4/render")
def render(request: RenderRequest) -> dict:
    """
    Data presentation layer: one view per recommended presentation type.

    Charts are Vega-Lite v5 specs. A format the rows cannot support is returned
    with `available: false` and a reason. No forecasting runs here.
    """
    try:
        return data_presentation.build_views(
            request.member2_result,
            intent=request.intent,
            presentation_types=request.presentation_types,
            question=request.user_query,
        )
    except input_adapter.InputFormatError as exc:
        return {"status": "ERROR", "error_code": "INPUT_FORMAT_ERROR", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "error_code": "RENDER_FAILED", "detail": str(exc)}


@app.post("/api/v4/predict")
def predict(request: PredictRequest) -> dict:
    """
    Prediction layer: intent-to-strategy mapping, data readiness, model
    selection, a confidence-bounded forecast, dual-dimension anomalies and a
    verified unified summary. Runs for a forecast request, or for an anomaly
    question on its own. No what-if simulation.
    """
    if prediction_layer.prediction_mode(request.intent, request.prediction_needed) is None:
        return {"status": "ERROR", "error_code": "PREDICTION_NOT_REQUESTED",
                "detail": "The classification asks for neither a forecast nor anomaly detection."}
    try:
        return prediction_layer.run_prediction(
            request.member2_result, request.intent, request.prediction_needed, request.user_query)
    except input_adapter.InputFormatError as exc:
        return {"status": "ERROR", "error_code": "INPUT_FORMAT_ERROR", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "error_code": "PREDICTION_FAILED", "detail": str(exc)}


@app.post("/api/v4/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    """
    Part 1 only: classify intent, detect prediction demand, bind schema.

    Call this BEFORE SQL generation. Member 1 can use `semantic_roles` to shape
    the query, and Member 3 can use `affected_tables` to pre-authorise access.
    """
    try:
        return pipeline.analyze_only(
            request.user_query,
            request.schema_meta,
            _ctx(request.security_context),
            request.use_llm,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "error_code": "ANALYSIS_FAILED",
            "detail": str(exc),
        }


@app.post("/api/v4/present")
def present(request: PresentRequest) -> dict:
    """
    Full pipeline over a PII-masked result set from Member 2.

    Returns the visualization grammar, all six prediction stages, and the
    unified temporal summary with its claim trace.
    """
    try:
        return pipeline.run(
            request.user_query,
            rows=request.member2_result or request.raw_results,
            schema_meta=request.schema_meta,
            schema_types=request.schema_types,
            security_context=_ctx(request.security_context),
            use_llm=request.use_llm,
            use_llm_summary=request.use_llm_summary,
            confidence_level=request.confidence_level,
            horizon=request.horizon,
            scenario_text=request.scenario_text,
            value_column=request.value_column,
            enable_cache=False,
        )
    except input_adapter.InputFormatError as exc:
        # The payload itself is malformed: a caller-side problem, reported as
        # such so it is not mistaken for a failure of this component (Stage 8).
        return {"status": "ERROR", "error_code": "INPUT_FORMAT_ERROR", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "error_code": "PRESENTATION_FAILED",
            "detail": str(exc),
        }


@app.post("/api/v4/simulate")
def simulate(request: SimulateRequest) -> dict:
    """
    Stage 6 re-entry: apply a new scenario to an already-returned result set.

    Kept separate from /present so an interactive what-if does not require
    re-executing SQL against the tenant database - the scenario is a
    transformation of data the user has already been authorised to see.
    """
    try:
        envelope = pipeline.run(
            request.user_query,
            rows=request.member2_result or request.raw_results,
            schema_meta=request.schema_meta,
            security_context=_ctx(request.security_context),
            use_llm=False,
            horizon=request.horizon,
            scenario_text=request.scenario_text,
            enable_cache=False,
        )
        return {
            "status": "SUCCESS",
            "scenario": envelope["prediction"]["stage_6_scenario"],
            "visualization": envelope["visualization"],
            "summary": envelope["summary"],
        }
    except input_adapter.InputFormatError as exc:
        return {"status": "ERROR", "error_code": "INPUT_FORMAT_ERROR", "detail": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "error_code": "SIMULATION_FAILED",
            "detail": str(exc),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8004)
