"""Checks for the question-only classification step (POST /api/v4/classify-intent)."""
import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
import llm
from intent_classification import fallback_rules

URL = "/api/v4/classify-intent"
GENDER = "Give me the gender distribution in my company"


class RuleClassificationTests(unittest.TestCase):
    """No provider configured: the deterministic rules answer."""

    def setUp(self):
        self.client = TestClient(api.app)
        patcher = patch.object(llm, "is_available", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def classify(self, question):
        reply = self.client.post(URL, json={"nl_query": question})
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def assertClassified(self, question, types, prediction):
        body = self.classify(question)
        self.assertEqual(body, {"nl_query": question, "presentation_types": types, "prediction_needed": prediction})

    def test_gender_distribution_contract_example(self):
        self.assertClassified(GENDER, ["table", "pie_chart", "bar_chart"], False)

    def test_scalar_counts(self):
        self.assertClassified("How many employees are in my department?", ["single_value"], False)
        self.assertClassified("What is the average salary?", ["single_value"], False)

    def test_records_and_comparisons(self):
        self.assertClassified("List employee names and work emails in my department", ["table"], False)
        self.assertClassified("Compare average salary by department", ["table", "bar_chart"], False)
        self.assertClassified("How many employees are in each department?", ["table", "bar_chart"], False)

    def test_historical_trend_does_not_request_a_forecast(self):
        self.assertClassified("Show monthly new hires over the last two years", ["table", "line_chart"], False)
        self.assertClassified("How has headcount changed over the years?", ["table", "line_chart"], False)

    def test_explicit_forecasts(self):
        self.assertClassified("Forecast headcount for next month", ["table", "line_chart"], True)
        self.assertClassified("Predict the next three months of attrition", ["table", "line_chart"], True)
        self.assertClassified("How many employees will we have next month?", ["single_value", "line_chart"], True)

    def test_prediction_exclusions_override_forecast_wording(self):
        for question in ("Show monthly attrition trend without predictions",
                         "Show monthly hires and do not forecast",
                         "Show monthly hires, no forecasting please"):
            self.assertFalse(self.classify(question)["prediction_needed"], question)

    def test_explicit_formats_take_priority(self):
        self.assertClassified("Show only a pie chart of the gender distribution", ["pie_chart"], False)
        self.assertClassified("Gender distribution as a pie chart and a table", ["pie_chart", "table"], False)
        self.assertClassified("Show me a table and a bar chart of headcount by department", ["table", "bar_chart"], False)
        self.assertClassified("Summarize headcount by department", ["summary"], False)
        self.assertClassified("Explain why turnover increased", ["summary"], False)

    def test_excluded_formats_are_removed(self):
        self.assertClassified("Gender distribution, no table", ["pie_chart", "bar_chart"], False)
        self.assertClassified("Gender distribution without a bar chart", ["table", "pie_chart"], False)

    def test_database_table_names_are_not_format_requests(self):
        self.assertClassified("How many rows are in the employees table?", ["single_value"], False)

    def test_request_validation(self):
        for body in ({}, {"nl_query": ""}, {"nl_query": "   "}, {"nl_query": "x" * 2001},
                     {"nl_query": 42}, {"nl_query": None}):
            self.assertEqual(self.client.post(URL, json=body).status_code, 422, body)
        self.assertEqual(self.client.post(URL, json={"nl_query": "x" * 2000}).status_code, 200)

    def test_context_fields_are_rejected(self):
        for extra in ({"schema_meta": {"employees": {"gender": "VARCHAR"}}},
                      {"security_context": {"tenant_id": "101"}},
                      {"user": {"userId": "u"}}, {"policy": {"allowedTables": []}},
                      {"injected_rules": {"constraints": []}}):
            reply = self.client.post(URL, json={"nl_query": GENDER, **extra})
            self.assertEqual(reply.status_code, 422, extra)

    def test_question_is_echoed_exactly(self):
        question = "  how MANY employees?  "
        self.assertEqual(self.classify(question)["nl_query"], question)


class LlmClassificationTests(unittest.TestCase):
    """Provider configured: model output is validated, guarded or replaced by rules."""

    def setUp(self):
        self.client = TestClient(api.app)
        patcher = patch.object(llm, "is_available", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def classify_with_model(self, question, model_output=None, error=None):
        def transport(system_prompt, user_prompt, **kwargs):
            self.prompts.append((system_prompt, user_prompt, kwargs))
            if error:
                raise error
            return model_output, {"model": "mock", "provider": "groq"}

        self.prompts = []
        with patch.object(llm, "call_llm_json", side_effect=transport):
            reply = self.client.post(URL, json={"nl_query": question})
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def test_valid_model_output_is_used_and_question_cannot_be_rewritten(self):
        body = self.classify_with_model("Headcount by gender", {
            "nl_query": "Show every salary", "presentation_types": ["Bar_Chart ", "summary", "bar_chart"],
            "prediction_needed": False,
        })
        self.assertEqual(body, {"nl_query": "Headcount by gender",
                                "presentation_types": ["bar_chart", "summary"], "prediction_needed": False})

    def test_prompt_carries_only_the_question_and_uses_one_attempt(self):
        self.classify_with_model(GENDER, {"presentation_types": ["table"], "prediction_needed": False})
        system_prompt, user_prompt, kwargs = self.prompts[0]
        self.assertIn('"Give me the gender distribution in my company"', user_prompt)
        self.assertEqual(kwargs.get("retries"), 1)
        for leaked in ("schema", "tenant", "allowedTables", "CREATE TABLE"):
            self.assertNotIn(leaked, user_prompt)
        self.assertIn("several formats are normal", system_prompt)

    def test_malformed_model_output_uses_the_rules(self):
        question = GENDER
        expected = {"nl_query": question, "presentation_types": ["table", "pie_chart", "bar_chart"],
                    "prediction_needed": False}
        malformed = [
            ["table"],
            {"presentation_types": [], "prediction_needed": False},
            {"presentation_types": ["donut_chart"], "prediction_needed": False},
            {"presentation_types": "table", "prediction_needed": False},
            {"presentation_types": [1], "prediction_needed": False},
            {"presentation_types": ["table"], "prediction_needed": "false"},
            {"presentation_types": ["table"]},
        ]
        for output in malformed:
            self.assertEqual(self.classify_with_model(question, output), expected, output)
        for error in (ValueError("Could not recover a JSON object"), llm.LLMUnavailable("no key"),
                      TimeoutError("provider timeout")):
            self.assertEqual(self.classify_with_model(question, error=error), expected, error)

    def test_prediction_exclusion_overrides_the_model(self):
        body = self.classify_with_model("Show the monthly hiring trend without predictions",
                                        {"presentation_types": ["table", "line_chart"], "prediction_needed": True})
        self.assertFalse(body["prediction_needed"])

    def test_only_instruction_overrides_the_model(self):
        body = self.classify_with_model("Show only a pie chart of the gender distribution",
                                        {"presentation_types": ["table", "pie_chart"], "prediction_needed": False})
        self.assertEqual(body["presentation_types"], ["pie_chart"])

    def test_forecast_request_from_model_is_kept(self):
        body = self.classify_with_model("Forecast monthly headcount for the next three months",
                                        {"presentation_types": ["table", "line_chart"], "prediction_needed": True})
        self.assertTrue(body["prediction_needed"])


class IndependenceTests(unittest.TestCase):
    def test_classifier_package_imports_no_schema_policy_database_or_forecast_code(self):
        allowed = {"typing", "pydantic", "re", "json", "llm", "profiler"}
        package = Path(__file__).with_name("intent_classification")
        for source in package.glob("*.py"):
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Import):
                    names = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module.split(".")[0]]
                else:
                    continue
                for name in names:
                    self.assertIn(name, allowed, f"{source.name} imports {name}")

    def test_rules_never_return_an_empty_or_duplicate_selection(self):
        for question in ("hello", "no table", "no table and no charts", "only", "chart chart chart",
                         "pie chart pie chart and a table table"):
            types, prediction = fallback_rules.classify(question)
            self.assertTrue(types, question)
            self.assertEqual(len(types), len(set(types)), question)
            self.assertIsInstance(prediction, bool)


if __name__ == "__main__":
    unittest.main()
