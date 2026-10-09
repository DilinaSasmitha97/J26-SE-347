"""Checks for the question-only classification step (POST /api/v4/classify-intent)."""
import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
import llm
import query_analyzer
import response_intent
from intent_classification import classifier, fallback_rules, vonara_rules

URL = "/api/v4/classify-intent"
GENDER = "Give me the gender distribution in my company"
WEAK_INTENT = "What does our workforce look like?"          # intent 0.50, prediction 0.80
ALL_WEAK = "What will happen next month?"                     # intent 0.50, prediction 0.50 (soft cue)
WEAK_PREDICTION = "How many employees will we have next month?"  # intent 0.97, prediction 0.50


def model_answer(intent="PROPORTION", types=("table", "pie_chart", "bar_chart"), prediction=False,
                 intent_conf=0.9, types_conf=0.9, prediction_conf=0.9):
    return {"intent": intent, "intent_confidence": intent_conf,
            "presentation_types": list(types), "presentation_types_confidence": types_conf,
            "prediction_needed": prediction, "prediction_confidence": prediction_conf}


class RuleClassificationTests(unittest.TestCase):
    """No provider configured: the rules answer every decision."""

    def setUp(self):
        self.client = TestClient(api.app)
        patcher = patch.object(llm, "is_available", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def classify(self, question):
        reply = self.client.post(URL, json={"nl_query": question})
        self.assertEqual(reply.status_code, 200, reply.text)
        return reply.json()

    def assertClassified(self, question, intent, types, prediction):
        self.assertEqual(self.classify(question), {
            "nl_query": question, "intent": intent, "presentation_types": types, "prediction_needed": prediction})

    def test_gender_distribution_contract_example(self):
        self.assertClassified(GENDER, "PROPORTION", ["table", "pie_chart", "bar_chart"], False)
        self.assertClassified("give me gender variation in my company", "PROPORTION",
                              ["table", "pie_chart", "bar_chart"], False)

    def test_response_has_exactly_the_four_contract_fields(self):
        self.assertEqual(list(self.classify(GENDER)), ["nl_query", "intent", "presentation_types", "prediction_needed"])

    def test_scalar_counts(self):
        self.assertClassified("How many employees are in my department?", "KPI_SINGLE_VALUE", ["single_value"], False)
        self.assertClassified("What is the average salary?", "KPI_SINGLE_VALUE", ["single_value"], False)

    def test_records_and_comparisons(self):
        self.assertClassified("List employee names and work emails in my department", "DETAIL_LOOKUP", ["table"], False)
        self.assertClassified("Compare average salary by department", "COMPARISON", ["table", "bar_chart"], False)
        self.assertClassified("How many employees are in each department?", "COMPARISON", ["table", "bar_chart"], False)

    def test_historical_trend_does_not_request_a_forecast(self):
        self.assertClassified("Show monthly new hires over the last two years", "TREND_ANALYSIS",
                              ["table", "line_chart"], False)

    def test_explicit_forecasts(self):
        self.assertClassified("Forecast headcount for next month", "TREND_ANALYSIS", ["table", "line_chart"], True)
        self.assertClassified("Predict the next three months of attrition", "TREND_ANALYSIS",
                              ["table", "line_chart"], True)

    def test_prediction_exclusions(self):
        for question in ("Show monthly attrition trend without predictions",
                         "Show monthly hires and do not forecast",
                         "Show monthly hires, no forecasting please"):
            self.assertFalse(self.classify(question)["prediction_needed"], question)

    def test_explicit_formats_take_priority(self):
        self.assertClassified("Show only a pie chart of the gender distribution", "PROPORTION", ["pie_chart"], False)
        self.assertClassified("Gender distribution as a pie chart and a table", "PROPORTION",
                              ["pie_chart", "table"], False)
        self.assertClassified("Summarize headcount by department", "COMPARISON",
                              ["table", "bar_chart", "summary"], False)

    def test_excluded_formats_are_removed(self):
        self.assertClassified("Gender distribution, no table", "PROPORTION", ["pie_chart", "bar_chart"], False)
        self.assertClassified("Gender distribution without a bar chart", "PROPORTION", ["table", "pie_chart"], False)

    def test_database_table_names_are_not_format_requests(self):
        self.assertClassified("How many rows are in the employees table?", "KPI_SINGLE_VALUE", ["single_value"], False)

    def test_weak_rules_without_a_provider_keep_the_rule_answer(self):
        with patch.object(llm, "call_llm_json") as transport:
            body = self.classify("Tell me about the team")
        transport.assert_not_called()
        self.assertEqual(body["intent"], "DETAIL_LOOKUP")
        self.assertEqual(body["presentation_types"], ["table"])

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
            self.assertEqual(self.client.post(URL, json={"nl_query": GENDER, **extra}).status_code, 422, extra)

    def test_question_is_echoed_exactly(self):
        question = "  how MANY employees?  "
        self.assertEqual(self.classify(question)["nl_query"], question)


class RuleConfidenceTests(unittest.TestCase):
    def test_stage8_confidence_formula_and_weak_evidence_cap(self):
        intent, confidence, _ = vonara_rules.rule_intent("Show monthly new hires over the last two years")
        self.assertEqual((intent, confidence), ("TREND_ANALYSIS", 0.97))  # 6 vs 1, capped at 0.97
        intent, confidence, _ = vonara_rules.rule_intent("How many employees are in each department?")
        self.assertEqual(intent, "COMPARISON")
        self.assertAlmostEqual(confidence, 0.6417, places=4)  # 4 vs 3: close race
        self.assertLessEqual(vonara_rules.rule_intent(WEAK_INTENT)[1], 0.50)  # one weak marker
        self.assertEqual(vonara_rules.rule_intent("hello")[:2], ("UNKNOWN", 0.2))

    def test_prediction_triggers(self):
        self.assertEqual(vonara_rules.rule_prediction("Forecast headcount"), (True, 0.90, "EXPLICIT"))
        self.assertEqual(vonara_rules.rule_prediction("What if salaries rise by 10%?"), (True, 0.90, "EXPLICIT"))
        self.assertEqual(vonara_rules.rule_prediction(WEAK_PREDICTION), (True, 0.50, "SOFT"))
        self.assertEqual(vonara_rules.rule_prediction("Monthly hires, do not forecast"), (False, 0.97, "DECLINED"))
        self.assertEqual(vonara_rules.rule_prediction("List employees"), (False, 0.80, "NONE"))
        # Word-start matching: these are not forecast cues.
        self.assertEqual(vonara_rules.rule_prediction("List employee projects")[2], "NONE")
        self.assertEqual(vonara_rules.rule_prediction("Any unexpected absences?")[2], "NONE")

    def test_named_formats_are_confident_and_derived_formats_follow_the_intent(self):
        self.assertEqual(fallback_rules.rule_presentation_types("Show it as a pie chart", "DETAIL_LOOKUP", 0.2),
                         (["pie_chart"], 0.95, True))
        self.assertEqual(fallback_rules.rule_presentation_types("Gender split", "PROPORTION", 0.68),
                         (["table", "pie_chart", "bar_chart"], 0.68, False))


class LlmFallbackTests(unittest.TestCase):
    """Provider configured: the LLM is asked only for decisions the rules are unsure about."""

    def setUp(self):
        self.client = TestClient(api.app)
        patcher = patch.object(llm, "is_available", return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.prompts = []

    def run_with_model(self, question, output=None, error=None):
        def transport(system_prompt, user_prompt, **kwargs):
            self.prompts.append((system_prompt, user_prompt, kwargs))
            if error:
                raise error
            return output, {"model": "mock", "provider": "groq"}

        with patch.object(llm, "call_llm_json", side_effect=transport):
            return classifier.classify_intent_detailed(question)

    def test_confident_rules_never_call_the_llm(self):
        response, details = self.run_with_model("Show monthly new hires over the last two years", model_answer())
        self.assertEqual(self.prompts, [])
        self.assertEqual((details.classified_by, details.llm_status), ("rules", "not-needed"))
        self.assertEqual(response["intent"], "TREND_ANALYSIS")

    def test_weak_intent_is_taken_from_a_confident_llm_and_strong_prediction_stays(self):
        response, details = self.run_with_model(WEAK_INTENT, model_answer(prediction=True, prediction_conf=0.99))
        self.assertEqual(len(self.prompts), 1)
        self.assertEqual(response, {"nl_query": WEAK_INTENT, "intent": "PROPORTION",
                                    "presentation_types": ["table", "pie_chart", "bar_chart"],
                                    "prediction_needed": False})
        self.assertEqual(details.decisions["intent"].source, "llm")
        self.assertEqual(details.decisions["prediction_needed"].source, "rules")
        self.assertEqual(details.classified_by, "rules+llm")

    def test_weak_prediction_only_is_taken_from_the_llm(self):
        response, details = self.run_with_model(WEAK_PREDICTION, model_answer(intent="PROPORTION", prediction=False))
        self.assertEqual(response["intent"], "KPI_SINGLE_VALUE")  # rules were confident
        self.assertFalse(response["prediction_needed"])
        self.assertEqual(details.decisions["prediction_needed"].source, "llm")

    def test_all_weak_decisions_from_the_llm(self):
        response, details = self.run_with_model(ALL_WEAK, model_answer(
            intent="TREND_ANALYSIS", types=["table", "line_chart"], prediction=True))
        self.assertEqual(details.classified_by, "llm")
        self.assertEqual(response["presentation_types"], ["table", "line_chart"])
        self.assertTrue(response["prediction_needed"])

    def test_llm_answers_below_its_threshold_are_ignored(self):
        response, details = self.run_with_model(WEAK_INTENT, model_answer(intent_conf=0.59, types_conf=0.59))
        self.assertEqual(details.llm_status, "used")
        self.assertEqual(details.classified_by, "rules")
        self.assertEqual(response["intent"], "DETAIL_LOOKUP")

    def test_missing_confidences_are_never_trusted(self):
        output = model_answer()
        for key in ("intent_confidence", "presentation_types_confidence", "prediction_confidence"):
            output.pop(key)
        _, details = self.run_with_model(WEAK_INTENT, output)
        self.assertEqual(details.classified_by, "rules")

    def test_formats_are_rederived_when_only_the_intent_comes_from_the_llm(self):
        response, _ = self.run_with_model(WEAK_INTENT, model_answer(types=["table"], types_conf=0.3))
        self.assertEqual(response["intent"], "PROPORTION")
        self.assertEqual(response["presentation_types"], ["table", "pie_chart", "bar_chart"])

    def test_formats_that_do_not_fit_the_intent_are_replaced(self):
        response, _ = self.run_with_model(WEAK_INTENT, model_answer(intent="TREND_ANALYSIS", types=["pie_chart"]))
        self.assertEqual(response["presentation_types"], ["table", "line_chart"])

    def test_malformed_llm_output_keeps_the_rule_answers(self):
        rules_only, _ = self.run_with_model(WEAK_INTENT, model_answer(intent_conf=0.0, types_conf=0.0))
        malformed = [
            ["PROPORTION"],
            {**model_answer(), "intent": "GENDER_SPLIT"},
            {k: v for k, v in model_answer().items() if k != "intent"},
            {**model_answer(), "presentation_types": []},
            {**model_answer(), "presentation_types": ["donut_chart"]},
            {**model_answer(), "presentation_types": [1]},
            {**model_answer(), "prediction_needed": "false"},
        ]
        for output in malformed:
            response, details = self.run_with_model(WEAK_INTENT, output)
            self.assertEqual(response, rules_only, output)
            self.assertTrue(details.llm_status.startswith("failed"), output)
        for error in (ValueError("Could not recover a JSON object"), llm.LLMUnavailable("no key"),
                      TimeoutError("provider timeout")):
            response, details = self.run_with_model(WEAK_INTENT, error=error)
            self.assertEqual(response, rules_only, error)
            self.assertEqual(details.classified_by, "rules")

    def test_declined_forecast_overrides_a_confident_llm(self):
        question = "Show monthly hires, no need for forecasting"
        with patch.object(vonara_rules, "rule_prediction", return_value=(True, 0.5, "SOFT")):
            response, _ = self.run_with_model(question, model_answer(prediction=True, prediction_conf=0.99))
        self.assertFalse(response["prediction_needed"])

    def test_only_instruction_overrides_the_llm(self):
        response, _ = self.run_with_model("Show only a pie chart of it", model_answer(types=["table", "pie_chart"]))
        self.assertEqual(response["presentation_types"], ["pie_chart"])

    def test_prompt_carries_only_the_question_and_uses_one_attempt(self):
        self.run_with_model(WEAK_INTENT, model_answer())
        system_prompt, user_prompt, kwargs = self.prompts[0]
        self.assertIn(f'"{WEAK_INTENT}"', user_prompt)
        self.assertEqual(kwargs.get("retries"), 1)
        for leaked in ("schema", "tenant", "allowedTables", "CREATE TABLE"):
            self.assertNotIn(leaked, user_prompt)
        self.assertIn("intent_confidence", system_prompt)

    def test_confidences_are_logged_not_returned(self):
        lines = []
        with patch.object(classifier, "log_step", side_effect=lambda message, level="INFO": lines.append(message)), \
                patch.object(llm, "call_llm_json", return_value=(model_answer(), {})):
            reply = self.client.post(URL, json={"nl_query": WEAK_INTENT})
        self.assertEqual(list(reply.json()), ["nl_query", "intent", "presentation_types", "prediction_needed"])
        self.assertNotIn("confidence", reply.text)
        self.assertNotIn("classified_by", reply.text)
        line = lines[-1]
        self.assertIn("intent=PROPORTION (llm 0.90; rules DETAIL_LOOKUP 0.50)", line)
        self.assertIn("prediction=False (rules 0.80, trigger NONE)", line)
        self.assertIn("classified_by=rules+llm", line)


class IndependenceTests(unittest.TestCase):
    def test_classifier_package_imports_no_schema_policy_database_or_forecast_code(self):
        allowed = {"typing", "pydantic", "re", "json", "dataclasses", "llm", "profiler"}
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

    def test_copied_stage8_lexicons_have_not_drifted(self):
        self.assertEqual({k.value: v for k, v in query_analyzer.INTENT_MARKERS.items()}, vonara_rules.INTENT_MARKERS)
        self.assertEqual(query_analyzer.PREDICTION_EXPLICIT, vonara_rules.PREDICTION_EXPLICIT)
        self.assertEqual(query_analyzer.PREDICTION_DECLINED.pattern, vonara_rules.PREDICTION_DECLINED.pattern)
        self.assertEqual(query_analyzer.WHAT_IF_MARKERS, vonara_rules.WHAT_IF_MARKERS)
        self.assertEqual([(p.pattern, r) for p, r in response_intent._NEUTRAL_PHRASES],
                         [(p.pattern, r) for p, r in vonara_rules._NEUTRAL_PHRASES])
        self.assertEqual(response_intent._PER_ROW_COUNT.pattern, vonara_rules._PER_ROW_COUNT.pattern)
        self.assertEqual(set(vonara_rules.INTENTS), {i.value for i in query_analyzer.QueryIntent} - {"UNKNOWN"})

    def test_rules_never_return_an_empty_or_duplicate_selection(self):
        with patch.object(llm, "is_available", return_value=False):
            for question in ("hello", "no table", "no table and no charts", "only", "chart chart chart",
                             "pie chart pie chart and a table table"):
                response = classifier.classify_intent(question)
                types = response["presentation_types"]
                self.assertTrue(types, question)
                self.assertEqual(len(types), len(set(types)), question)


if __name__ == "__main__":
    unittest.main()
