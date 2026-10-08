"""Translation input and full-process logging checks; no provider requests."""
import io
import json
import sqlite3
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
import api
import main


SCHEMA = "CREATE TABLE employees (id INT, tenant_id INT);"
SQL = "SELECT COUNT(*) FROM employees WHERE tenant_id = 101"


class TranslationTraceTests(unittest.TestCase):
    def test_received_json_rules_preserved_and_response_logged(self):
        rules = {"constraints": ["Filter by tenant_id = 101"], "extra": "Keep this field"}
        output = io.StringIO()
        with patch.object(api.database, "get_cached_or_live_schema", return_value=SCHEMA), \
             patch.object(api.database, "get_db_connection", return_value=None), \
             patch.object(api.main, "translate", return_value=(SQL, {"total_tokens": 7})) as engine, \
             redirect_stdout(output):
            response = TestClient(api.app).post("/api/v1/translate", json={"user_query": "Count employees", "injected_rules": rules})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(engine.call_args.kwargs["injected_rules"]), rules)
        self.assertEqual(engine.call_args.kwargs["nl_query"], "Count employees")
        self.assertEqual(response.json()["predicted_sql"], SQL)
        for stage in ("RECEIVED INPUT", "RULES FOR ENGINE PROMPT", "HTTP RESPONSE OUTPUT", "REQUEST END"):
            self.assertIn(stage, output.getvalue())
        self.assertIn('"extra": "Keep this field"', output.getvalue())
        self.assertIn(SQL, output.getvalue())

    def test_empty_and_legacy_rules_do_not_gain_constraints(self):
        for rules in (None, "Only count employees."):
            with self.subTest(rules=rules), \
                 patch.object(api.database, "get_cached_or_live_schema", return_value=SCHEMA), \
                 patch.object(api.database, "get_db_connection", return_value=None), \
                 patch.object(api.main, "translate", return_value=(SQL, {})) as engine, \
                 redirect_stdout(io.StringIO()):
                response = TestClient(api.app).post("/api/v1/translate", json={"user_query": "Count employees", "injected_rules": rules})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(engine.call_args.kwargs["injected_rules"], rules)

    def test_error_response_logged(self):
        output = io.StringIO()
        with patch.object(api.database, "get_cached_or_live_schema", return_value=SCHEMA), \
             patch.object(api.database, "get_db_connection", return_value=None), \
             patch.object(api.main, "translate", side_effect=RuntimeError("Mock translation failure")), \
             redirect_stdout(output):
            response = TestClient(api.app).post("/api/v1/translate", json={"user_query": "Count employees", "injected_rules": None})
        self.assertEqual(response.status_code, 500)
        self.assertIn("HTTP ERROR OUTPUT", output.getvalue())
        self.assertIn("Mock translation failure", output.getvalue())
        self.assertIn("REQUEST END", output.getvalue())

    def test_full_engine_trace_includes_model_and_refinement_inputs_outputs(self):
        conn = sqlite3.connect(":memory:")
        self.addCleanup(conn.close)
        conn.execute(SCHEMA)
        replies = ["SELECT missing FROM employees", SQL]
        def completion(**kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=replies.pop(0)))],
                usage=SimpleNamespace(prompt_tokens=3, completion_tokens=2, total_tokens=5))
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=completion)))
        output = io.StringIO()
        with patch.dict("os.environ", {"LLM_PROVIDER": "groq"}), \
             patch.object(main.llm, "get_client", return_value=client), \
             patch.object(main.entity_resolver, "resolve_grounded_entities", return_value=([], set())), \
             patch.object(main.entity_resolver, "format_grounding_hints", return_value=""), \
             patch.object(main.relationship_mapper, "get_subgraph_join_paths", return_value=""), \
             patch.object(main.schema_extractor, "extract_minimal_schema", return_value=(SCHEMA, {"selected_tables": ["employees"]})), \
             patch.object(main.exemplar_selector, "retrieve", return_value=[]), \
             patch.object(main.exemplar_selector, "format_exemplars", return_value=""), \
             redirect_stdout(output):
            final_sql, metadata = main.translate("Count employees", SCHEMA,
                injected_rules='{"constraints": ["Filter by tenant_id = 101"]}', db_conn=conn)
        self.assertEqual(final_sql, SQL)
        self.assertTrue(metadata["healed"])
        for stage in ("ENGINE INPUT", "FULL SCHEMA", "ENTITY GROUNDING OUTPUT", "RELATIONSHIP MAPPING OUTPUT",
                      "SCHEMA PRUNING STATS", "FINAL JOIN HINTS", "EXEMPLAR OUTPUT", "FINAL ENGINE PROMPT", "LLM REQUEST / FULL PROMPT",
                      "LLM RAW OUTPUT", "INITIAL SQL VALIDATION", "REFINEMENT SCHEMA EXPANSION",
                      "REFINEMENT ATTEMPT OUTPUT", "FINAL FULL SQL QUERY", "ENGINE OUTPUT METADATA"):
            self.assertIn(stage, output.getvalue())
        self.assertIn("SELECT missing FROM employees", output.getvalue())
        self.assertIn("Database Compiler Error", output.getvalue())
        self.assertIn(SQL, output.getvalue())


if __name__ == "__main__":
    unittest.main()
