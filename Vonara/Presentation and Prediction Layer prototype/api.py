"""
REST gateway for Component 4.

Mirrors the conventions of Member 1's FastAPI gateway so the middleware chain
exposes one consistent surface. Three endpoints:

  POST /api/v4/analyze    Part 1 only - called BEFORE SQL generation
  POST /api/v4/present    Full pipeline - called AFTER Member 2 returns rows
  POST /api/v4/simulate   Re-run a what-if against an existing result set
  GET  /api/v4/health     Liveness + capability report

Run:  uvicorn api:app --reload --port 8004
"""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

import llm
import pipeline

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
    user_query: str
    schema_meta: Optional[Any] = None
    security_context: Optional[SecurityContext] = None
    use_llm: bool = True


class PresentRequest(BaseModel):
    user_query: str
    raw_results: List[Dict[str, Any]] = Field(default_factory=list)
    schema_meta: Optional[Any] = None
    schema_types: Optional[Dict[str, str]] = None
    security_context: Optional[SecurityContext] = None
    use_llm: bool = True
    use_llm_summary: bool = False
    confidence_level: float = 0.95
    horizon: Optional[int] = None
    scenario_text: str = ""
    value_column: Optional[str] = None


class SimulateRequest(BaseModel):
    user_query: str
    raw_results: List[Dict[str, Any]] = Field(default_factory=list)
    scenario_text: str
    schema_meta: Optional[Any] = None
    security_context: Optional[SecurityContext] = None
    horizon: Optional[int] = None


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
        },
    }


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
            rows=request.raw_results,
            schema_meta=request.schema_meta,
            schema_types=request.schema_types,
            security_context=_ctx(request.security_context),
            use_llm=request.use_llm,
            use_llm_summary=request.use_llm_summary,
            confidence_level=request.confidence_level,
            horizon=request.horizon,
            scenario_text=request.scenario_text,
            value_column=request.value_column,
        )
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
            rows=request.raw_results,
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
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "ERROR",
            "error_code": "SIMULATION_FAILED",
            "detail": str(exc),
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8004)
