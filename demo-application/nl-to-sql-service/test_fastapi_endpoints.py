import json
from fastapi.testclient import TestClient
from api import app

def run_tests():
    client = TestClient(app)

    print("========================================")
    print("1. Testing GET /api/v1/health")
    print("========================================")
    res = client.get("/api/v1/health")
    print("Status:", res.status_code)
    print("Response:", json.dumps(res.json(), indent=2))
    assert res.status_code == 200

    print("\n========================================")
    print("2. Testing GET /api/v1/schema")
    print("========================================")
    res = client.get("/api/v1/schema")
    print("Status:", res.status_code)
    print("Schema bytes:", res.json().get("schema_bytes"))
    print("Contains 'tenants':", "CREATE TABLE tenants" in res.json().get("schema_meta", ""))
    print("Contains 'employees':", "CREATE TABLE employees" in res.json().get("schema_meta", ""))
    print("Contains 'payroll':", "CREATE TABLE payroll" in res.json().get("schema_meta", ""))
    assert res.status_code == 200

    print("\n========================================")
    print("3. Testing POST /api/v1/translate (Multi-Tenant HR)")
    print("========================================")
    payload = {
        "user_query": "What are the first and last names of employees in Human Resources department?",
        "injected_rules": "STRICT CONSTRAINT: Filter all records by tenant_id = 101."
    }
    res = client.post("/api/v1/translate", json=payload)
    print("Status:", res.status_code)
    if res.status_code == 200:
        data = res.json()
        print("Predicted SQL:\n", data.get("predicted_sql"))
        print("\nMetadata:", json.dumps(data.get("metadata"), indent=2))
    else:
        print("Error detail:", res.text)
    assert res.status_code == 200

    print("\n========================================")
    print("4. Testing POST /api/v1/ask (Direct Execution Must Be Blocked)")
    print("========================================")
    payload_ask = {
        "question": "List employee number, first name, and last name for active employees",
        "injected_rules": "WHERE tenant_id = 101",
        "execute_query": True,
        "max_rows": 5
    }
    res = client.post("/api/v1/ask", json=payload_ask)
    print("Status:", res.status_code)
    if res.status_code == 200:
        data = res.json()
        print("Predicted SQL:\n", data.get("predicted_sql"))
        print(f"Returned {data.get('row_count')} rows:")
        for r in data.get("rows", []):
            print("  -", r)
    else:
        print("Error detail:", res.text)
    assert res.status_code == 403
    assert res.json()["detail"]["error_code"] == "GATEWAY_EXECUTION_REQUIRED"

    print("\n========================================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("========================================")

if __name__ == "__main__":
    run_tests()
