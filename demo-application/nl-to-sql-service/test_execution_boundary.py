import unittest
from unittest.mock import patch

from fastapi import HTTPException
import api


class ExecutionBoundaryTests(unittest.TestCase):
    def test_direct_execution_is_refused_before_translation_or_database_access(self):
        with patch.object(api.main, "translate") as translate, patch.object(api.database, "get_db_connection") as connect:
            with self.assertRaises(HTTPException) as raised:
                api.ask_database(api.AskRequest(question="Show employees", execute_query=True))
            self.assertEqual(raised.exception.status_code, 403)
            self.assertEqual(raised.exception.detail["error_code"], "GATEWAY_EXECUTION_REQUIRED")
            translate.assert_not_called()
            connect.assert_not_called()

    def test_legacy_translation_only_route_returns_no_database_rows(self):
        with patch.object(api.main, "translate", return_value=("SELECT id FROM employees", {})), \
                patch.object(api.database, "get_cached_or_live_schema", return_value="CREATE TABLE employees(id INT)"), \
                patch.object(api.database, "get_db_connection") as connect:
            result = api.ask_database(api.AskRequest(question="Show employees", execute_query=False))
            self.assertEqual(result.rows, [])
            self.assertEqual(result.row_count, 0)
            connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
