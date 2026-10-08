"""
Capture real API responses as UI test fixtures (Stage 7).

Each fixture is what /api/v4/present (or /simulate) actually returned for a
question over the SQLite test database, so the UI tests render the real
contract rather than hand-written JSON. Re-run after any change to the
response envelope:

    python frontend/scripts/make_fixtures.py
"""

import json
import os
import sys
import warnings
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "none")
warnings.filterwarnings("ignore")
COMPONENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(COMPONENT))
os.chdir(COMPONENT)

import profiler  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import demo_api  # noqa: E402

profiler.VERBOSE = False
OUT = COMPONENT / "frontend" / "src" / "__fixtures__"

PRESENT = {
    "answer": ("travel_total", "What is the total amount spent on travel?"),
    "table_pii": ("employees", "List all employees in the Finance department"),
    "chart_forecast": ("expenses_a", "Show my monthly expenses over time and forecast the next 3 months"),
    "report": ("expenses_a", "Deep dive into my monthly expenses"),
    "forecast_refused": ("software_a", "Show monthly spend on Software and forecast the next 3 months"),
    "forecast_answer": ("expenses_d", "How much will I spend next month?"),
}
SIMULATE = {
    "whatif": ("expenses_d", "Show monthly expenses and predict the next 3 months", "cut spending by 20%"),
    "whatif_refused": ("expenses_d", "Show monthly expenses and predict the next 3 months",
                       "what if prices change somehow"),
}


def main() -> int:
    client = TestClient(demo_api.app)
    OUT.mkdir(parents=True, exist_ok=True)
    sources = {}
    for name, (dataset, question) in PRESENT.items():
        src = sources.setdefault(dataset, client.post("/demo/rows", json={"dataset_id": dataset}).json())
        body = client.post("/api/v4/present", json={"user_query": question, **src}).json()
        assert body["status"] == "SUCCESS", body
        (OUT / f"{name}.json").write_text(json.dumps(body, indent=1), encoding="utf-8")
        print(f"{name}: {body['response']['response_intent']['intent']} {body['response']['blocks_emitted']}")
    for name, (dataset, question, scenario) in SIMULATE.items():
        src = sources.setdefault(dataset, client.post("/demo/rows", json={"dataset_id": dataset}).json())
        body = client.post("/api/v4/simulate",
                           json={"user_query": question, "scenario_text": scenario, **src}).json()
        assert body["status"] == "SUCCESS", body
        (OUT / f"{name}.json").write_text(json.dumps(body, indent=1), encoding="utf-8")
        print(f"{name}: simulated={body['scenario'].get('simulated')}")
    datasets = client.get("/demo/datasets").json()
    (OUT / "datasets.json").write_text(json.dumps(datasets, indent=1), encoding="utf-8")
    print(f"datasets: {len(datasets['datasets'])}")
    policy = client.get("/demo/policy").json()
    (OUT / "policy.json").write_text(json.dumps(policy, indent=1), encoding="utf-8")
    rows = client.post("/demo/rows", json={"dataset_id": "employees"}).json()
    (OUT / "rows_employees.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"policy: {policy['version']}; employees rows: {rows['member2_result']['rowCount']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
