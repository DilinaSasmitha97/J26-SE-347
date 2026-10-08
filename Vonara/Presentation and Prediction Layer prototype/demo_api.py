"""
Demo server for the Stage 7 user interface.

Wraps the production API (api.py) unchanged and adds two things the UI needs
while the other components are not running:

  GET  /demo/policy     the forecasting policy in force (forecast_config.json)
  GET  /demo/datasets   result sets the UI can ask questions about - the
                        integration fixtures' SQL, grouped, with example
                        questions (stand-in for Member 1's SQL generation)
  POST /demo/rows       runs a dataset's SQL on the SQLite test database and
                        returns Member 2's exact masked /api/query payload
                        (stand-in for Members 2 and 3)

The UI then calls the REAL contract - POST /api/v4/present and
/api/v4/simulate - with that payload, exactly as an orchestrator will once the
team's services are connected. Nothing here is imported by api.py, so the
production surface does not change.

Run:   python test_db/seed.py            (once; builds the SQLite database)
       cd frontend && npm install && npm run build   (once)
       uvicorn demo_api:app --port 8004  then open http://localhost:8004
During UI development: `npm run dev` in frontend/ (proxies to port 8004).
"""

import json
import sys
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "test_db"))

import db_config  # noqa: E402
import member2_stub  # noqa: E402

import prediction  # noqa: E402
from api import app  # noqa: E402  (the production app; routes added below)

FRONTEND_DIST = HERE / "frontend" / "dist"

# Curated result sets: one per kind of question the component handles. Each
# names the fixture whose SQL it runs; every fixture with the same SQL lends
# its question as an example.
_DATASETS = [
    # (id, fixture, title, note, group, kind) - kind picks the icon in the UI
    ("expenses_a", "F01", "Monthly expenses", "36 months, trend and seasonality", "Time series", "trend"),
    ("expenses_d", "W01", "Monthly expenses (steady growth)", "24 months, clean linear growth",
     "Time series", "trend"),
    ("expenses_b", "F05", "Monthly expenses (short history)", "5 months only", "Time series", "trend"),
    ("software_a", "F16", "Monthly Software spend", "one category, noisy", "Time series", "trend"),
    ("tickets_a", "F07", "Weekly support tickets", "158 weeks of ticket counts", "Time series", "trend"),
    ("by_category", "C01", "Expenses by category", "one total per category", "Breakdowns", "bar"),
    ("by_vendor", "P04", "Spend by vendor", "one total per vendor (15 vendors)", "Breakdowns", "bar"),
    ("amounts", "D01", "Individual expense amounts", "every invoice, for distributions",
     "Breakdowns", "distribution"),
    ("units_revenue", "K01", "Units sold vs revenue", "two measures, for relationships",
     "Breakdowns", "scatter"),
    ("employees", "L01", "Finance employees", "names and emails, PII-masked by Member 2",
     "Records & figures", "table"),
    ("travel_total", "S01", "Total travel spend", "a single figure", "Records & figures", "figure"),
]


# Extra example questions per data source, so each one shows more than one
# kind of answer. Each was run through /api/v4/present before being listed.
_MORE_EXAMPLES = {
    "expenses_d": ["Give me a report on monthly expenses with a forecast"],
    "expenses_b": ["Show monthly expenses", "Summarise monthly expenses"],
    "software_a": ["Show monthly software spend over time"],
    "tickets_a": ["Show weekly support tickets over time", "Were there any unusual weeks for tickets?"],
    "by_category": ["Show expenses by category", "Which category has the highest spend?"],
    "by_vendor": ["Show spend by vendor", "Who are the top vendors by spend?"],
    "amounts": ["How are invoice amounts spread?"],
    "units_revenue": ["Plot revenue against units sold"],
    "employees": ["List the finance employees with their emails"],
    "travel_total": ["How much did we spend on travel?"],
}


@lru_cache(maxsize=None)
def _shape(sql: str) -> dict:
    """Rows, columns and masked columns of a data source, as Member 2 returns them."""
    payload = member2_stub.query(sql)
    return {
        "row_count": payload.get("rowCount", len(payload.get("rows") or [])),
        "columns": [c.get("name") for c in payload.get("columns") or []],
        "masked": [{"name": m.get("name"), "pii_type": m.get("piiType")}
                   for m in (payload.get("masking") or {}).get("columns") or []],
    }


def _fixtures() -> dict:
    data = json.loads((db_config.TEST_DB_DIR / "fixtures.json").read_text(encoding="utf-8"))
    return {c["id"]: c for c in data["cases"]}


def _catalogue() -> list:
    fixtures = _fixtures()
    out = []
    for key, fid, title, note, group, kind in _DATASETS:
        case = fixtures.get(fid)
        if not case:
            continue
        # Fixture questions that probe attacks are kept out of the example
        # chips; they stay in the test suite.
        examples = [c["question"] for c in fixtures.values()
                    if c["sql"] == case["sql"] and c["group"] != "edge"
                    and "ignore your previous" not in c["question"].lower()]
        examples += [q for q in _MORE_EXAMPLES.get(key, []) if q not in examples]
        out.append({"id": key, "title": title, "note": note, "group": group, "kind": kind,
                    "tenant": case["tenant"], "sql": case["sql"], "examples": examples[:6],
                    **_shape(case["sql"])})
    return out


@app.get("/demo/datasets")
def demo_datasets() -> dict:
    try:
        return {"datasets": _catalogue(), "backend": db_config.backend()}
    except db_config.DatabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/demo/policy")
def demo_policy() -> dict:
    """The forecasting policy in force (forecast_config.json), read-only, for the console."""
    return {"file": "forecast_config.json", **prediction.CONFIG}


class RowsRequest(BaseModel):
    dataset_id: str


@app.post("/demo/rows")
def demo_rows(request: RowsRequest) -> dict:
    dataset = next((d for d in _catalogue() if d["id"] == request.dataset_id), None)
    if dataset is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset {request.dataset_id!r}")
    try:
        payload = member2_stub.query(dataset["sql"])
    except db_config.DatabaseNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "member2_result": payload,
        "security_context": {"tenant_id": dataset["tenant"]},
        "schema_meta": db_config.schema_ddl(),
        "sql": dataset["sql"],
    }


# The built UI, served last so the API routes above take precedence.
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")
