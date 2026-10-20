import sqlite3
import unittest

from rewriter import isolate_sql, verify_isolation, IsolationError, REGISTRY


class TenantIsolationTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE employees(id INTEGER, tenant_id INTEGER, first_name TEXT,
                                   department_id INTEGER, supervisor_id INTEGER, city TEXT);
            CREATE TABLE departments(id INTEGER, tenant_id INTEGER, name TEXT);
            CREATE TABLE tenants(id INTEGER, name TEXT);
            INSERT INTO employees VALUES
                (1,101,'Alice',10,2,'Colombo'), (2,101,'Bob',20,3,'Kandy'),
                (3,102,'Foreign',20,1,'Colombo');
            INSERT INTO departments VALUES (10,101,'Local'), (20,102,'Foreign');
            INSERT INTO tenants VALUES (101,'Our tenant'),(102,'Other tenant');
        """)

    def repaired(self, sql, rules=None):
        result = isolate_sql(sql, 101, rules, "sqlite")
        self.assertEqual(result["finalVerification"], "PASS", result)
        # The parameterized execution must produce the same result as the SQL
        # that passed policy verification; this is not a string-presence test.
        actual = self.db.execute(result["parameterizedSql"], result["parameters"]).fetchall()
        self.assertEqual(actual, self.db.execute(result["finalSql"]).fetchall())
        verified = isolate_sql(result["finalSql"], 101, rules, "sqlite", repair=False)
        self.assertEqual(verified["status"], "UNCHANGED_VERIFIED", verified)
        self.assertEqual(verified["parameterizedSql"], result["parameterizedSql"])
        return result, actual

    def test_missing_wrong_and_correct_filters(self):
        for suffix, status in [("", "REPAIRED"), (" WHERE tenant_id=102", "REPAIRED"),
                               (" WHERE 101=tenant_id", "UNCHANGED_VERIFIED")]:
            with self.subTest(suffix=suffix):
                result, rows = self.repaired("SELECT first_name FROM employees" + suffix)
                self.assertEqual(result["status"], status)
                self.assertEqual(rows, [("Alice",), ("Bob",)])

    def test_wrong_tenant_does_not_change_business_value(self):
        result, rows = self.repaired("SELECT first_name FROM employees WHERE tenant_id=102 AND department_id=102")
        self.assertIn("department_id = 102", result["finalSql"])
        self.assertEqual(rows, [])
        self.assertEqual(result["findings"][0]["status"], "WRONG_TENANT")

    def test_partial_inner_join_and_policy_coverage(self):
        # Registry requires departments isolation even if a caller omits its rule.
        result, rows = self.repaired("SELECT e.first_name,d.name FROM employees e JOIN departments d ON d.id=e.department_id WHERE e.tenant_id=101")
        self.assertEqual(rows, [("Alice", "Local")])
        self.assertEqual([c["alias"] for c in result["changes"]], ["d"])

    def test_unused_unregistered_policy_table_does_not_block_gender_query(self):
        self.db.execute("ALTER TABLE employees ADD COLUMN gender TEXT")
        self.db.execute("UPDATE employees SET gender = CASE WHEN id=1 THEN 'FEMALE' ELSE 'MALE' END")
        rules = [{"table": table, "field": "tenant_id", "operator": "=", "value": 101}
                 for table in ("employees", "departments", "workforce_capacity")]
        sql = "SELECT gender, COUNT(*) AS count FROM employees WHERE tenant_id = 101 GROUP BY gender;"
        result, rows = self.repaired(sql, rules)
        self.assertEqual(result["status"], "UNCHANGED_VERIFIED")
        self.assertEqual(result["changes"], [])
        self.assertEqual(rows, [("FEMALE", 1), ("MALE", 1)])
        # The independent verifier must also ignore unrelated policy sources.
        verify_isolation(result["finalSql"], "sqlite", "101", rules)

    def test_referenced_unregistered_policy_table_remains_blocked(self):
        rules = [{"table": "workforce_capacity", "column": "tenant_id", "value": 101}]
        for sql in ["SELECT COUNT(*) FROM workforce_capacity WHERE tenant_id=101",
                    "SELECT e.id FROM employees e JOIN workforce_capacity w ON w.department_id=e.department_id"]:
            with self.subTest(sql=sql):
                result = isolate_sql(sql, 101, rules)
                self.assertEqual(result["reasonCode"], "UNKNOWN_TENANT_OWNERSHIP")
                self.assertIsNone(result["finalSql"])
                self.assertNotIn("parameterizedSql", result)

    def test_unused_policy_table_does_not_skip_referenced_row_restrictions(self):
        rules = [{"table": "workforce_capacity", "column": "tenant_id", "value": 101},
                 {"table": "employees", "column": "department_id", "value": 10}]
        result = isolate_sql("SELECT first_name FROM employees WHERE tenant_id=101", 101, rules)
        self.assertEqual(result["reasonCode"], "ROW_FILTER_MISMATCH")
        self.assertIsNone(result["finalSql"])

    def test_left_join_keeps_unmatched_and_hides_foreign_department(self):
        result, rows = self.repaired("SELECT e.first_name,d.name FROM employees e LEFT JOIN departments d ON d.id=e.department_id ORDER BY e.id")
        self.assertEqual(rows, [("Alice", "Local"), ("Bob", None)])
        self.assertEqual(result["changes"][1]["placement"], "JOIN_ON")

    def test_self_join_protects_each_occurrence(self):
        _, rows = self.repaired("SELECT e.first_name,s.first_name FROM employees e JOIN employees s ON s.id=e.supervisor_id WHERE e.tenant_id=101")
        self.assertEqual(rows, [("Alice", "Bob")])

    def test_boolean_precedence_and_weak_correct_tenant_condition(self):
        for condition in ["city='Colombo' OR first_name='Bob'", "tenant_id=101 OR city='Colombo'"]:
            with self.subTest(condition=condition):
                _, rows = self.repaired("SELECT first_name FROM employees WHERE " + condition)
                self.assertEqual(rows, [("Alice",), ("Bob",)])

    def test_aggregate_window_and_limit_consume_only_tenant_rows(self):
        _, rows = self.repaired("SELECT COUNT(*) FROM employees")
        self.assertEqual(rows, [(2,)])
        _, rows = self.repaired("SELECT first_name,COUNT(*) OVER () FROM employees ORDER BY id DESC LIMIT 1")
        self.assertEqual(rows, [("Bob", 2)])

    def test_tenant_directory_uses_id(self):
        _, rows = self.repaired("SELECT name FROM tenants WHERE id=102")
        self.assertEqual(rows, [("Our tenant",)])

    def test_unsupported_inputs_are_non_executable(self):
        cases = [
            "SELECT first_name FROM employees WHERE tenant_id=102 OR city='Colombo'",
            "SELECT first_name FROM employees WHERE tenant_id IN (101,102)",
            "SELECT first_name FROM employees WHERE NOT tenant_id=101",
            "SELECT e.first_name FROM employees e JOIN employees s ON s.id=e.id WHERE tenant_id=101",
            "SELECT (SELECT COUNT(*) FROM departments) FROM employees WHERE tenant_id=101",
            "WITH x AS (SELECT id FROM employees) SELECT id FROM x",
            "SELECT id FROM employees UNION SELECT id FROM employees",
            "SELECT e.id FROM employees e RIGHT JOIN departments d ON e.department_id=d.id",
            "SELECT e.id FROM employees e NATURAL JOIN departments d",
            "SELECT e.id FROM employees e JOIN departments d USING(id)",
            "SELECT id FROM other_schema.employees",
            "SELECT id FROM employees WHERE tenant_id=?",
            "SELECT id FROM employees WHERE tenant_id=@tenant",
            "SELECT tenant_id,COUNT(*) FROM employees GROUP BY tenant_id HAVING tenant_id=102",
            "SELECT id FROM unknown_table",
            "SELECT custom_lookup(id) FROM employees",
            "SELECT id FROM employees; SELECT id FROM departments",
            "DELETE FROM employees",
        ]
        for sql in cases:
            with self.subTest(sql=sql):
                result = isolate_sql(sql, 101)
                self.assertNotEqual(result["finalVerification"], "PASS", result)
                self.assertIsNone(result["finalSql"])
                self.assertNotIn("parameterizedSql", result)
                self.assertFalse(result["applied"])

    def test_context_and_policy_conflicts_block(self):
        for tenant in [None, True, 0, -1, "101 OR 1=1", "9223372036854775808"]:
            with self.subTest(tenant=tenant):
                self.assertEqual(isolate_sql("SELECT id FROM employees", tenant)["status"], "BLOCKED")
        result = isolate_sql("SELECT id FROM employees", 101, [{"table": "employees", "column": "tenant_id", "value": 102}])
        self.assertEqual(result["reasonCode"], "POLICY_USER_TENANT_MISMATCH")

    def test_additional_row_rules_are_not_repaired_or_bypassed(self):
        rules = [{"table": "employees", "column": "department_id", "value": 10}]
        for condition in ["", " WHERE department_id=20", " WHERE department_id=10 OR city='Colombo'"]:
            result = isolate_sql("SELECT first_name FROM employees" + condition, 101, rules)
            self.assertEqual(result["reasonCode"], "ROW_FILTER_MISMATCH", result)
            self.assertIsNone(result["finalSql"])
        _, rows = self.repaired("SELECT first_name FROM employees WHERE department_id=10", rules)
        self.assertEqual(rows, [("Alice",)])

    def test_additional_row_rule_required_per_self_join_alias(self):
        sql = "SELECT e.id,s.id FROM employees e JOIN employees s ON s.id=e.supervisor_id WHERE e.department_id=10"
        result = isolate_sql(sql, 101, [{"table": "employees", "column": "department_id", "value": 10}])
        self.assertEqual(result["reasonCode"], "ROW_FILTER_MISMATCH")

    def test_verifier_does_not_repair_missing_or_wrong_guards(self):
        for sql in ["SELECT id FROM employees", "SELECT id FROM employees WHERE tenant_id=102",
                    "SELECT e.id,s.id FROM employees e CROSS JOIN employees s WHERE e.tenant_id=101"]:
            with self.subTest(sql=sql):
                with self.assertRaises(IsolationError):
                    verify_isolation(sql, "mysql", "101", [])

    def test_registry_and_bigint_bindings(self):
        for table in REGISTRY:
            with self.subTest(table=table):
                result = isolate_sql(f"SELECT COUNT(*) FROM {table}", "9007199254740993")
                self.assertEqual(result["finalVerification"], "PASS", result)
                self.assertEqual(result["parameters"], ["9007199254740993"])


if __name__ == "__main__":
    unittest.main()
