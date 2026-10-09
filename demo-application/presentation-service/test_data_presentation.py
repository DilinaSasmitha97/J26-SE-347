"""Checks for the data presentation layer (POST /api/v4/render)."""
import ast
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
import llm
import summarization
from data_presentation import build_views

URL = "/api/v4/render"
ALL_TYPES = ["table", "single_value", "bar_chart", "pie_chart", "line_chart", "summary"]


def result(columns, rows, **extra):
    return {"columns": [{"name": c} for c in columns], "rows": rows, "rowCount": len(rows),
            "truncated": False, "masking": {"columns": [], "maskedCells": 0}, **extra}


GENDER = result(["gender", "headcount"], [["Female", 42], ["Male", 51]])
MONTHLY = result(["month", "hires"], [[f"2024-{m:02d}-01", m + 3] for m in range(1, 13)])
SCALAR = result(["headcount"], [[93]])
RECORDS = result(["first_name", "work_email", "hire_date"],
                 [["A", "a***@example.com", "2023-01-02"], ["B", "b***@example.com", "2023-04-05"]],
                 masking={"columns": [{"name": "work_email", "piiType": "EMAIL"}], "maskedCells": 2})


def views_by_type(payload, types=ALL_TYPES, intent=None, question=""):
    return {v["type"]: v for v in build_views(payload, intent, types, question)["views"]}


class RulesOnlySummary(unittest.TestCase):
    """Deterministic summaries unless a test mocks the LLM."""

    def setUp(self):
        patcher = patch.object(llm, "is_available", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)


class FormatTests(RulesOnlySummary):
    def test_views_follow_the_classifier_order(self):
        reply = build_views(GENDER, "PROPORTION", ["pie_chart", "table", "bar_chart"])
        self.assertEqual([v["type"] for v in reply["views"]], ["pie_chart", "table", "bar_chart"])
        self.assertEqual(reply["source"], "classification")
        self.assertTrue(all(v["available"] for v in reply["views"]))

    def test_gender_distribution_in_every_format(self):
        views = views_by_type(GENDER, intent="PROPORTION")
        for kind in ("table", "bar_chart", "pie_chart", "summary"):
            self.assertTrue(views[kind]["available"], kind)
        self.assertIn("2 rows", views["single_value"]["reason"])
        self.assertIn("date or period", views["line_chart"]["reason"])
        pie = views["pie_chart"]["block"]["spec"]
        self.assertEqual(pie["mark"]["type"], "arc")
        self.assertEqual(pie["data"]["values"], [{"gender": "Female", "headcount": 42},
                                                 {"gender": "Male", "headcount": 51}])

    def test_single_value(self):
        views = views_by_type(SCALAR)
        self.assertTrue(views["single_value"]["available"])
        self.assertEqual(views["single_value"]["block"]["display_value"], "93")
        for kind in ("bar_chart", "pie_chart", "line_chart"):
            self.assertFalse(views[kind]["available"], kind)

    def test_line_chart_over_time_uses_iso_dates(self):
        views = views_by_type(MONTHLY)
        line = views["line_chart"]["block"]["spec"]
        self.assertEqual(line["mark"]["type"], "line")
        self.assertEqual(line["encoding"]["x"]["type"], "temporal")
        self.assertEqual(line["data"]["values"][0], {"month": "2024-01-01", "hires": 4})
        self.assertFalse(views["pie_chart"]["available"])  # a date is not a category

    def test_year_numbers_become_dates_not_milliseconds(self):
        yearly = result(["hire_year", "hires"], [[y, y - 2010] for y in range(2015, 2025)])
        line = views_by_type(yearly)["line_chart"]["block"]["spec"]
        self.assertEqual(line["data"]["values"][0]["hire_year"], "2015-01-01")

    def test_grouped_series_draw_one_line_and_bar_colour_per_group(self):
        grouped = result(["month", "department", "hires"],
                         [[f"2024-{m:02d}-01", d, m] for m in range(1, 5) for d in ("HR", "IT")])
        views = views_by_type(grouped)
        self.assertEqual(views["line_chart"]["block"]["spec"]["encoding"]["color"]["field"], "department")
        self.assertEqual(views["bar_chart"]["block"]["spec"]["encoding"]["x"]["field"], "department")

    def test_two_categories_give_grouped_bars(self):
        two = result(["department", "gender", "n"], [["HR", "F", 3], ["HR", "M", 2], ["IT", "F", 4], ["IT", "M", 6]])
        bar = views_by_type(two)["bar_chart"]["block"]["spec"]
        self.assertEqual(bar["encoding"]["color"]["field"], "gender")
        self.assertEqual(bar["encoding"]["xOffset"]["field"], "gender")

    def test_pie_limits(self):
        many = result(["job_title", "n"], [[f"Title {i}", i + 1] for i in range(12)])
        self.assertIn("12 categories", views_by_type(many)["pie_chart"]["reason"])
        negative = result(["department", "net_change"], [["HR", -3], ["IT", 5], ["Ops", 2]])
        self.assertIn("negative", views_by_type(negative)["pie_chart"]["reason"])
        single = result(["department", "headcount"], [["HR", 7]])
        self.assertIn("one category", views_by_type(single)["pie_chart"]["reason"])

    def test_bar_keeps_the_top_25_of_many_categories(self):
        many = result(["job_title", "n"], [[f"Title {i}", i] for i in range(40)])
        view = views_by_type(many)["bar_chart"]
        self.assertEqual(len(view["block"]["spec"]["data"]["values"]), 25)
        self.assertEqual(view["block"]["spec"]["data"]["values"][0], {"job_title": "Title 39", "n": 39})
        self.assertTrue(any("top 25 of 40" in note for note in view["notes"]))

    def test_repeated_categories_are_summed(self):
        repeated = result(["department", "salary"], [["HR", 10], ["HR", 5], ["IT", 7]])
        view = views_by_type(repeated)["bar_chart"]
        self.assertEqual(view["block"]["spec"]["data"]["values"], [{"department": "HR", "salary": 15},
                                                                   {"department": "IT", "salary": 7}])
        self.assertTrue(any("summed" in note for note in view["notes"]))

    def test_masked_string_decimals_and_duplicate_columns(self):
        payload = result(["department", "avg_salary", "avg_salary"], [["HR", "52000.50", "1"], ["IT", "71000.25", "2"]])
        views = views_by_type(payload)
        values = views["bar_chart"]["block"]["spec"]["data"]["values"]
        self.assertEqual(values[0]["avg_salary"], 52000.5)
        self.assertEqual([c["name"] for c in views["table"]["block"]["columns"]], ["department", "avg_salary", "avg_salary_2"])

    def test_records_table_marks_masked_columns(self):
        table = views_by_type(RECORDS, ["table"])["table"]["block"]
        masked = {c["name"]: c["masked"] for c in table["columns"]}
        self.assertEqual(masked, {"first_name": False, "work_email": True, "hire_date": False})
        self.assertEqual(table["rows"][0]["work_email"], "a***@example.com")

    def test_empty_result(self):
        views = views_by_type(result(["department", "n"], []))
        self.assertTrue(views["table"]["available"])
        self.assertEqual([c["name"] for c in views["table"]["block"]["columns"]], ["department", "n"])
        for kind in ("single_value", "bar_chart", "pie_chart", "line_chart", "summary"):
            self.assertFalse(views[kind]["available"], kind)

    def test_chart_specs_carry_only_plotted_fields(self):
        payload = result(["department", "hire_date", "n"], [["HR", "2024-01-02", 1], ["IT", "2024-02-03", 2]])
        for kind in ("bar_chart", "pie_chart"):
            spec = views_by_type(payload)[kind]["block"]["spec"]
            for point in spec["data"]["values"]:
                self.assertEqual(set(point), {"department", "n"}, kind)


class DataShapeFallbackTests(RulesOnlySummary):
    def test_formats_are_chosen_from_the_data_without_a_classification(self):
        cases = [(SCALAR, ["single_value"]), (MONTHLY, ["table", "line_chart"]),
                 (GENDER, ["table", "bar_chart", "pie_chart"]), (RECORDS, ["table"])]
        for payload, expected in cases:
            reply = build_views(payload, None, None)
            self.assertEqual(reply["source"], "data")
            self.assertEqual([v["type"] for v in reply["views"]], expected)


class SummaryTests(unittest.TestCase):
    def test_deterministic_without_a_key(self):
        with patch.object(llm, "is_available", return_value=False):
            block = views_by_type(GENDER, ["summary"])["summary"]["block"]
        self.assertEqual(block["mode"], "DETERMINISTIC")
        self.assertIn("93", block["text"])
        self.assertTrue(block["verification"]["passed"])
        self.assertNotIn("rejected_narration", block)

    def test_verified_ai_narration_is_used(self):
        narration = "Across 2 rows, headcount totals 93.00: Male leads with 51.00 and Female has 42.00."
        with patch.object(llm, "is_available", return_value=True), \
                patch.object(llm, "call_llm_json", return_value=({"summary": narration}, {})):
            block = views_by_type(GENDER, ["summary"])["summary"]["block"]
        self.assertEqual((block["mode"], block["text"]), ("LLM_VERIFIED", narration))

    def test_ai_narration_with_an_invented_number_falls_back_to_facts(self):
        with patch.object(llm, "is_available", return_value=True), \
                patch.object(llm, "call_llm_json", return_value=({"summary": "Headcount totals 120."}, {})):
            block = views_by_type(GENDER, ["summary"])["summary"]["block"]
        self.assertEqual(block["mode"], "LLM_REJECTED")
        self.assertNotIn("120", block["text"])
        self.assertIn("93", block["text"])
        self.assertNotIn("rejected_narration", block)

    def test_ai_narration_can_be_switched_off(self):
        with patch.dict(os.environ, {"PRESENTATION_LLM_SUMMARY": "false"}), \
                patch.object(llm, "is_available", return_value=True), \
                patch.object(llm, "call_llm_json") as transport:
            block = views_by_type(GENDER, ["summary"])["summary"]["block"]
        transport.assert_not_called()
        self.assertEqual(block["mode"], "DETERMINISTIC")


class EndpointTests(RulesOnlySummary):
    def setUp(self):
        super().setUp()
        self.client = TestClient(api.app)

    def test_render_contract(self):
        reply = self.client.post(URL, json={"member2_result": GENDER, "user_query": "Gender split",
                                            "intent": "PROPORTION", "presentation_types": ["table", "pie_chart"]})
        body = reply.json()
        self.assertEqual(body["status"], "SUCCESS")
        self.assertEqual([v["type"] for v in body["views"]], ["table", "pie_chart"])
        self.assertEqual(body["views"][1]["block"]["spec"]["title"], "Share of Headcount by Gender")

    def test_classification_is_optional(self):
        body = self.client.post(URL, json={"member2_result": SCALAR}).json()
        self.assertEqual((body["source"], [v["type"] for v in body["views"]]), ("data", ["single_value"]))

    def test_request_validation(self):
        bad = [
            {"member2_result": GENDER, "presentation_types": ["donut_chart"]},
            {"member2_result": GENDER, "presentation_types": ["table", "table"]},
            {"member2_result": GENDER, "presentation_types": []},
            {"member2_result": GENDER, "intent": "GENDER_SPLIT"},
            {"member2_result": GENDER, "raw_results": [{"x": 1}]},
            {"presentation_types": ["table"]},
        ]
        for body in bad:
            self.assertEqual(self.client.post(URL, json=body).status_code, 422, body)

    def test_malformed_result_is_reported(self):
        body = self.client.post(URL, json={"member2_result": {"columns": "x", "rows": 5}}).json()
        self.assertEqual((body["status"], body["error_code"]), ("ERROR", "INPUT_FORMAT_ERROR"))


class IndependenceTests(unittest.TestCase):
    def test_no_forecasting_anomaly_or_whatif_code(self):
        banned = {"prediction", "anomaly", "whatif", "strategies", "pipeline", "query_analyzer"}
        for source in Path(__file__).with_name("data_presentation").glob("*.py"):
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module.split(".")[0]]
                for name in names:
                    self.assertNotIn(name, banned, f"{source.name} imports {name}")


if __name__ == "__main__":
    unittest.main()
