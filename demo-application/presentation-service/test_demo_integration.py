"""Integration-specific checks against the real deterministic API and pipeline."""
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import api
import pipeline
import llm


def history(truncated=False):
    return {
        "columns": [{"name": "month"}, {"name": "headcount"}],
        "rows": [[f"{2023 + i // 12}-{i % 12 + 1:02d}-01", 100 + 5 * i] for i in range(24)],
        "rowCount": 25 if truncated else 24,
        "truncated": truncated,
        "masking": {"columns": [], "maskedCells": 0},
    }


class DemoIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(api.app)
        pipeline.clear_cache()

    def test_analyze_non_data_request_and_permitted_schema(self):
        reply = self.client.post("/api/v4/analyze", json={"user_query": "hello"}).json()
        self.assertEqual(reply["status"], "SUCCESS")
        self.assertFalse(reply["analysis"]["response_intent"]["is_data_request"])
        reply = self.client.post("/api/v4/analyze", json={
            "user_query": "List employees", "schema_meta": {"employees": {"joined_date": "DATE"}}
        }).json()
        for column in reply["analysis"]["schema_binding"]["affected_columns"]:
            self.assertEqual(column["column"], "joined_date")

    def test_masked_columnar_result_preserves_duplicates_and_masking(self):
        reply = self.client.post("/api/v4/present", json={
            "user_query": "List employee emails", "member2_result": {
                "columns": [{"name": "email"}, {"name": "email"}],
                "rows": [["a***@example.com", "b***@example.com"]], "rowCount": 1,
                "masking": {"columns": [{"name": "email", "piiType": "EMAIL"}]}
            }, "security_context": {"tenant_id": "101"}
        }).json()
        self.assertEqual(reply["status"], "SUCCESS")
        self.assertEqual(reply["input"]["columns"], ["email", "email_2"])
        self.assertEqual(len(reply["input"]["masked_columns"]), 2)
        self.assertIn("a***@example.com", str(reply))
        self.assertFalse(reply["cache"]["hit"])

    def test_forecast_and_whatif_use_the_same_historical_rows(self):
        body = {"user_query": "Chart monthly headcount and forecast the next 3 months", "member2_result": history()}
        reply = self.client.post("/api/v4/present", json=body).json()
        self.assertEqual(reply["status"], "SUCCESS")
        self.assertTrue(reply["prediction"]["stage_4_forecast"]["generated"])
        self.assertEqual(len(reply["prediction"]["stage_4_forecast"]["points"]), 3)
        self.assertIn("CHART", reply["response"]["blocks_emitted"])
        scenario = self.client.post("/api/v4/simulate", json={**body, "scenario_text": "Increase the forecast by 10%"}).json()
        self.assertEqual(scenario["status"], "SUCCESS")
        self.assertTrue(scenario["scenario"]["simulated"])

    def test_truncation_and_security_metadata_cannot_reuse_a_cached_forecast(self):
        query = "Chart monthly headcount and forecast the next 3 months"
        first = pipeline.run(query, rows=history(), security_context={"tenant_id": "101", "user_role": "MANAGER"})
        self.assertTrue(first["prediction"]["stage_4_forecast"]["generated"])
        capped = pipeline.run(query, rows=history(True), security_context={"tenant_id": "101", "user_role": "MANAGER"})
        self.assertFalse(capped["cache"]["hit"])
        self.assertEqual(capped["prediction"]["stage_2_readiness"]["verdict"], "TRUNCATED")
        self.assertFalse(capped["prediction"]["stage_4_forecast"]["generated"])
        other_role = pipeline.run(query, rows=history(), security_context={"tenant_id": "101", "user_role": "EMPLOYEE"})
        self.assertFalse(other_role["cache"]["hit"])

    def test_invalid_forecast_options_are_rejected(self):
        reply = self.client.post("/api/v4/present", json={"user_query": "Forecast", "confidence_level": 2})
        self.assertEqual(reply.status_code, 422)

    def test_enabled_hybrid_path_uses_the_llm_transport(self):
        with patch.object(llm, "is_available", return_value=True), patch.object(
            llm, "call_llm_json", return_value=({}, {"model": "mock-model", "provider": "groq"})
        ) as transport:
            reply = self.client.post("/api/v4/analyze", json={
                "user_query": "Count employees", "schema_meta": {"employees": {"id": "INT"}},
                "use_llm": True,
            }).json()
        self.assertEqual(reply["status"], "SUCCESS")
        self.assertEqual(reply["analysis"]["metadata"]["mode"], "HYBRID")
        transport.assert_called_once()

    def test_missing_key_falls_back_without_calling_a_provider(self):
        with patch.object(llm, "is_available", return_value=False), patch.object(llm, "call_llm_json") as transport:
            reply = self.client.post("/api/v4/analyze", json={"user_query": "Count employees", "use_llm": True}).json()
        self.assertEqual(reply["status"], "SUCCESS")
        self.assertEqual(reply["analysis"]["metadata"]["mode"], "RULE_ONLY")
        transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
