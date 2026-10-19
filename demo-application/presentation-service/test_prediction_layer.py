"""Checks for the prediction layer (POST /api/v4/predict)."""
import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import api
import llm
from prediction_layer import prediction_mode, run_prediction

URL = "/api/v4/predict"


def table(columns, rows, truncated=False, row_count=None):
    return {"columns": [{"name": c} for c in columns], "rows": rows,
            "rowCount": row_count if row_count is not None else len(rows),
            "truncated": truncated, "masking": {"columns": [], "maskedCells": 0}}


def monthly(values, start_year=2023):
    return table(["month", "hires"], [[f"{start_year + i // 12}-{i % 12 + 1:02d}-01", v] for i, v in enumerate(values)])


TREND = monthly([100 + 4 * i for i in range(24)])
SPIKE = monthly([100 + 4 * i + (60 if i == 15 else 0) for i in range(24)])


class RulesOnly(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(llm, "is_available", return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)


class ModeTests(unittest.TestCase):
    def test_mode_follows_the_classification(self):
        self.assertEqual(prediction_mode("TREND_ANALYSIS", True), "FORECAST")
        self.assertEqual(prediction_mode("ANOMALY_DETECTION", False), "ANOMALY_ONLY")
        self.assertEqual(prediction_mode("ANOMALY_DETECTION", True), "FORECAST")
        self.assertIsNone(prediction_mode("PROPORTION", False))

    def test_unrequested_prediction_is_refused(self):
        with self.assertRaises(ValueError):
            run_prediction(TREND, "PROPORTION", False, "Gender split")


class ForecastTests(RulesOnly):
    def test_confidence_bounded_forecast_with_default_horizon(self):
        r = run_prediction(TREND, "TREND_ANALYSIS", True, "Forecast monthly hires")
        self.assertEqual((r["mode"], r["readiness"]["verdict"]), ("FORECAST", "READY"))
        self.assertEqual(r["strategy"]["strategy"], "TEMPORAL_FORECAST")
        self.assertTrue(r["forecast"]["generated"])
        self.assertEqual(r["horizon"], {"value": 3, "unit": "NONE", "source": "INFERRED"})
        points = r["forecast"]["points"]
        self.assertEqual(len(points), 3)
        for p in points:
            self.assertLessEqual(p["lower_bound"], p["predicted"])
            self.assertLessEqual(p["predicted"], p["upper_bound"])
        widths = [p["upper_bound"] - p["lower_bound"] for p in points]
        self.assertEqual(widths, sorted(widths), "the band widens with the horizon")
        self.assertEqual(r["forecast"]["confidence_level"], 0.95)
        self.assertTrue(r["model"]["model"] and r["model"]["reason"])

    def test_horizon_from_the_question(self):
        r = run_prediction(TREND, "TREND_ANALYSIS", True, "Forecast monthly hires for the next 6 months")
        self.assertEqual(r["horizon"]["source"], "EXPLICIT")
        self.assertEqual(len(r["forecast"]["points"]), 6)

    def test_a_kpi_forecast_request_is_promoted_to_a_temporal_forecast(self):
        r = run_prediction(TREND, "KPI_SINGLE_VALUE", True, "How many hires will we have next month?")
        self.assertEqual(r["strategy"]["strategy"], "TEMPORAL_FORECAST")
        self.assertTrue(r["strategy"]["promoted_by_explicit_request"])

    def test_grouped_comparison_projects_each_category(self):
        grouped = table(["month", "department", "hires"],
                        [[f"2024-{m:02d}-01", d, m * (2 if d == "IT" else 1)] for m in range(1, 13) for d in ("HR", "IT")])
        r = run_prediction(grouped, "COMPARISON", True, "Compare hires by department and forecast")
        self.assertEqual(r["strategy"]["strategy"], "CATEGORY_TRAJECTORY")
        self.assertTrue(r["strategy_result"]["executed"])

    def test_forecast_chart_layers_history_forecast_and_band(self):
        r = run_prediction(TREND, "TREND_ANALYSIS", True, "Forecast monthly hires")
        spec = r["chart"]["spec"]
        self.assertIn("layer", spec)
        self.assertIn("R1_FORECAST_MEAN", spec["_meta"]["extension_rules_applied"])
        self.assertIn("R2_CONFIDENCE_BAND", spec["_meta"]["extension_rules_applied"])
        self.assertEqual(spec["layer"][0]["data"]["values"][0], {"month": "2023-01-01", "hires": 100})

    def test_unified_summary_holds_verified_forecast_claims(self):
        r = run_prediction(TREND, "TREND_ANALYSIS", True, "Forecast monthly hires")
        dimensions = {c["dimension"] for c in r["summary"]["claims"]}
        self.assertEqual({"HISTORICAL", "PREDICTIVE"} <= dimensions, True, dimensions)
        self.assertTrue(r["summary"]["verification"]["passed"])
        self.assertEqual(r["summary"]["mode"], "DETERMINISTIC")


class ReadinessTests(RulesOnly):
    def test_too_few_points_are_refused_with_a_reason(self):
        r = run_prediction(monthly([5, 6, 7]), "TREND_ANALYSIS", True, "Forecast hires")
        self.assertFalse(r["readiness"]["is_ready"])
        self.assertFalse(r["forecast"]["generated"])
        self.assertIn("at least", r["forecast"]["skipped_reason"])
        self.assertIsNone(r["chart"])

    def test_an_empty_result_explains_that_no_history_was_returned(self):
        r = run_prediction(table(["hire_year", "hires"], []), "TREND_ANALYSIS", True, "Predict yearly hires for the next 2 years")
        self.assertEqual(r["readiness"]["verdict"], "INSUFFICIENT_POINTS")
        self.assertIn("returned no rows", r["readiness"]["reason"])
        self.assertIn("future dates", r["forecast"]["skipped_reason"])
        self.assertFalse(r["forecast"]["generated"])

    def test_truncated_input_is_refused(self):
        r = run_prediction(table(TREND["columns"] and ["month", "hires"], TREND["rows"], truncated=True, row_count=500),
                           "TREND_ANALYSIS", True, "Forecast hires")
        self.assertEqual(r["readiness"]["verdict"], "TRUNCATED")
        self.assertFalse(r["forecast"]["generated"])

    def test_no_time_axis_means_no_temporal_forecast(self):
        categories = table(["department", "headcount"], [["HR", 5], ["IT", 9], ["Ops", 4]])
        r = run_prediction(categories, "TREND_ANALYSIS", True, "Forecast headcount")
        self.assertFalse(r["forecast"]["generated"])
        self.assertFalse(r["readiness"]["is_ready"])


class SarimaStabilityTests(unittest.TestCase):
    def test_a_diverged_sarima_fit_is_detected(self):
        import prediction
        values = [500.0 + 10 * i for i in range(40)]
        sane = [v + 3 for v in values]
        exploded = sane[:20] + [1e16] + sane[21:]
        self.assertFalse(prediction._sarima_diverged(values, sane, 13))
        self.assertTrue(prediction._sarima_diverged(values, exploded, 13))
        self.assertFalse(prediction._sarima_diverged(values, [1e16] * 13 + sane[13:], 13), "start-up span is ignored")

    def test_project_series_falls_back_instead_of_returning_an_exploded_band(self):
        import prediction
        values = [700.0 + 5 * i + (600 if i % 12 == 2 else 0) for i in range(57)]
        unstable = ([v + 1 for v in values[:13]] + [1e16 * (-1) ** i for i in range(13, 37)] + values[37:],
                    [1355.0] * 3, None, None)
        with patch.object(prediction, "_fit_sarima", return_value=unstable):
            result = prediction.project_series(values, "SARIMA", 3)
        self.assertEqual(result["model"], "EXPONENTIAL_SMOOTHING")
        self.assertIn("numerically unstable", result["fallback_note"])
        self.assertLess(max(result["upper"]), 10 * max(values))


class AnomalyTests(RulesOnly):
    def test_injected_spike_is_found_by_iqr_and_zscore(self):
        r = run_prediction(SPIKE, "TREND_ANALYSIS", True, "Forecast monthly hires")
        historical = r["anomalies"]["historical_anomalies"]
        self.assertEqual([a["value"] for a in historical], [220])
        self.assertEqual(set(historical[0]["detected_by"]), {"IQR", "ZSCORE"})
        self.assertIn("R3_ANOMALY_MARKERS", r["chart"]["spec"]["_meta"]["extension_rules_applied"])

    def test_anomaly_only_mode_checks_history_without_a_forecast(self):
        r = run_prediction(SPIKE, "ANOMALY_DETECTION", False, "Any unusual spikes in monthly hires?")
        self.assertEqual(r["mode"], "ANOMALY_ONLY")
        self.assertEqual(r["readiness"]["verdict"], "NOT_REQUESTED")
        self.assertFalse(r["forecast"]["generated"])
        self.assertEqual(len(r["anomalies"]["historical_anomalies"]), 1)
        self.assertEqual(r["anomalies"]["predictive_warnings"], [])
        self.assertEqual(r["chart"]["spec"]["title"], "Hires: anomalies")

    def test_record_lists_are_not_screened_for_anomalies(self):
        records = table(["hire_date", "salary"], [[f"2024-{m:02d}-01", 1000 + m] for m in range(1, 13)])
        r = run_prediction(records, "DETAIL_LOOKUP", True, "List hires and forecast")
        self.assertFalse(r["anomalies"]["evaluated"])


class SummaryTests(unittest.TestCase):
    def test_ai_summary_with_an_invented_forecast_number_falls_back(self):
        with patch.object(llm, "is_available", return_value=True), \
                patch.object(llm, "call_llm_json", return_value=({"summary": "Hires will reach 999 next month."}, {})):
            r = run_prediction(TREND, "TREND_ANALYSIS", True, "Forecast monthly hires")
        self.assertEqual(r["summary"]["mode"], "LLM_REJECTED")
        self.assertNotIn("999", r["summary"]["text"])
        self.assertNotIn("rejected_narration", r["summary"])


class EndpointTests(RulesOnly):
    def setUp(self):
        super().setUp()
        self.client = TestClient(api.app)

    def test_predict_contract(self):
        body = self.client.post(URL, json={"member2_result": TREND, "user_query": "Forecast hires",
                                           "intent": "TREND_ANALYSIS", "prediction_needed": True}).json()
        self.assertEqual(body["status"], "SUCCESS")
        for key in ("mode", "strategy", "readiness", "model", "forecast", "anomalies", "chart", "summary"):
            self.assertIn(key, body)

    def test_neither_forecast_nor_anomaly_is_rejected(self):
        body = self.client.post(URL, json={"member2_result": TREND, "intent": "PROPORTION",
                                           "prediction_needed": False}).json()
        self.assertEqual((body["status"], body["error_code"]), ("ERROR", "PREDICTION_NOT_REQUESTED"))

    def test_request_validation(self):
        good = {"member2_result": TREND, "intent": "TREND_ANALYSIS", "prediction_needed": True}
        for bad in ({**good, "intent": "FORECAST"}, {**good, "prediction_needed": "yes"},
                    {**good, "scenario_text": "Increase by 10%"}, {k: v for k, v in good.items() if k != "intent"}):
            self.assertEqual(self.client.post(URL, json=bad).status_code, 422, bad)


class IndependenceTests(unittest.TestCase):
    def test_no_what_if_simulation(self):
        for source in Path(__file__).with_name("prediction_layer").glob("*.py"):
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module.split(".")[0]]
                for name in names:
                    self.assertNotIn(name, {"whatif", "scenario_language", "pipeline"}, f"{source.name} imports {name}")


if __name__ == "__main__":
    unittest.main()
