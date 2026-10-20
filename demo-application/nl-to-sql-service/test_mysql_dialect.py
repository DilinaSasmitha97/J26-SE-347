"""MySQL support in the engine's dialect detection and compiler dry run."""
import os
import sqlite3
import unittest
from pathlib import Path

import prompts
import refinement_loop as R


class FakePyMySQLConnection:
    """Stands in for pymysql.connections.Connection without a server."""


FakePyMySQLConnection.__module__ = "pymysql.connections"


class DialectTests(unittest.TestCase):
    def test_connection_dialect(self):
        self.assertEqual(R.connection_dialect(None), "sqlite")
        self.assertEqual(R.connection_dialect(sqlite3.connect(":memory:")), "sqlite")
        self.assertEqual(R.connection_dialect(FakePyMySQLConnection()), "mysql")
        self.assertEqual(R.connection_dialect(object()), "mssql")

    def test_the_prompt_names_mysql(self):
        self.assertEqual(prompts.get_dialect_display_name(R.connection_dialect(FakePyMySQLConnection())), "MySQL")

    def test_mysql_errors_are_categorised(self):
        self.assertEqual(R.categorize_compiler_error("(1054, \"Unknown column 'e.salary' in 'field list'\")"),
                         ("SCHEMA_LINKING_ERROR", ["salary"]))
        self.assertEqual(R.categorize_compiler_error("(1146, \"Table 'hr.employee' doesn't exist\")"),
                         ("SCHEMA_LINKING_ERROR", ["employee"]))
        self.assertEqual(R.categorize_compiler_error("(1064, 'You have an error in your SQL syntax; check the manual')")[0],
                         "SYNTAX_ERROR")


def _mysql_connection():
    try:
        import pymysql
        from dotenv import dotenv_values
    except ImportError:
        return None
    env = dotenv_values(Path(__file__).resolve().parent.parent / ".env")
    if not env.get("MYSQL_DATABASE") or not env.get("MYSQL_USER"):
        return None
    try:
        return pymysql.connect(host=env.get("MYSQL_HOST", "127.0.0.1"), port=int(env.get("MYSQL_PORT") or 3306),
                               user=env["MYSQL_USER"], password=env.get("MYSQL_PASSWORD") or "",
                               database=env["MYSQL_DATABASE"], connect_timeout=3)
    except Exception:
        return None


class LiveMySQLDryRunTests(unittest.TestCase):
    """Runs against the database in demo-application/.env when it is reachable."""

    @classmethod
    def setUpClass(cls):
        cls.conn = _mysql_connection()
        if cls.conn is None:
            raise unittest.SkipTest("MySQL from demo-application/.env is not reachable")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_valid_mysql_passes_the_dry_run(self):
        self.assertEqual(R.dry_run_validate("SELECT COUNT(*) AS headcount FROM employees WHERE tenant_id = 101", self.conn),
                         (True, "", ""))
        self.assertTrue(R.dry_run_validate(
            "SELECT DATE_FORMAT(hire_date, '%Y-%m-01') AS m, COUNT(*) FROM employees WHERE tenant_id = 101 GROUP BY m", self.conn)[0])

    def test_sql_server_syntax_and_unknown_names_fail_with_a_category(self):
        valid, message, kind = R.dry_run_validate("SELECT COUNT(*) FROM employees WHERE hire_date > DATEADD(MONTH, 6, GETDATE())", self.conn)
        self.assertFalse(valid)
        self.assertTrue(message)
        self.assertEqual(R.dry_run_validate("SELECT salary FROM employees", self.conn)[2], "SCHEMA_LINKING_ERROR")
        self.assertEqual(R.dry_run_validate("SELECT 1 FROM employee_typo", self.conn)[2], "SCHEMA_LINKING_ERROR")

    def test_the_dry_run_does_not_execute_or_change_anything(self):
        # EXPLAIN plans the statement; a write is not even attempted (read-only login).
        valid, _, _ = R.dry_run_validate("SELECT * FROM employees WHERE tenant_id = 101", self.conn)
        self.assertTrue(valid)


if __name__ == "__main__":
    unittest.main()
