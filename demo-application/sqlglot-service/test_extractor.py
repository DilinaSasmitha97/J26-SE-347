import unittest
import sqlite3

from extractor import extract_columns
from inspector import parse_sql
from rewriter import isolate_sql


class OutputAliasTests(unittest.TestCase):
    def columns(self, sql):
        return extract_columns(parse_sql(sql))

    def test_joined_aggregate_order_alias_is_not_a_physical_column(self):
        columns = self.columns("""
            SELECT d.department_name, COUNT(e.employee_id) AS employee_count
            FROM employees e JOIN departments d
              ON e.department_id=d.department_id AND e.tenant_id=d.tenant_id
            WHERE e.tenant_id=101 AND e.employment_status='ACTIVE'
            GROUP BY d.department_id,d.department_name ORDER BY employee_count DESC
        """)
        self.assertIn({"table": None, "column": "employee_count", "referenceType": "OUTPUT_ALIAS"}, columns)
        self.assertIn({"table": "employees", "column": "employee_id"}, columns)
        self.assertIn({"table": "departments", "column": "department_name"}, columns)

    def test_same_name_in_where_remains_a_physical_reference(self):
        columns = self.columns("SELECT COUNT(e.id) AS employee_count FROM employees e WHERE employee_count=1 ORDER BY employee_count")
        self.assertIn({"table": None, "column": "employee_count"}, columns)
        self.assertIn({"table": None, "column": "employee_count", "referenceType": "OUTPUT_ALIAS"}, columns)

    def test_qualified_and_undeclared_order_names_are_not_exempt(self):
        for sql in ["SELECT COUNT(e.id) AS employee_count FROM employees e ORDER BY e.employee_count",
                    "SELECT e.id FROM employees e ORDER BY employee_count"]:
            with self.subTest(sql=sql):
                self.assertFalse(any(c.get("referenceType") == "OUTPUT_ALIAS" for c in self.columns(sql)))

    def test_duplicate_aliases_are_not_exempt(self):
        columns = self.columns("SELECT COUNT(id) AS total,SUM(id) AS total FROM employees ORDER BY total")
        self.assertFalse(any(c.get("referenceType") == "OUTPUT_ALIAS" for c in columns))

    def test_aliases_are_local_to_the_select_that_owns_order_by(self):
        columns = self.columns("SELECT id FROM (SELECT COUNT(id) AS total FROM employees ORDER BY total) x ORDER BY total")
        self.assertIn({"table": None, "column": "total"}, columns)
        self.assertIn({"table": None, "column": "total", "referenceType": "OUTPUT_ALIAS"}, columns)

    def test_denied_source_column_is_still_visible_under_aggregate_alias(self):
        columns = self.columns("SELECT COUNT(e.nic_number) AS employee_count FROM employees e ORDER BY employee_count")
        self.assertIn({"table": "employees", "column": "nic_number"}, columns)

    def test_department_count_repair_preserves_tenant_equality_join_results(self):
        sql = """SELECT d.department_name, COUNT(e.employee_id) AS employee_count
                 FROM employees e JOIN departments d
                   ON e.department_id=d.department_id AND e.tenant_id=d.tenant_id
                 WHERE e.tenant_id=101 AND e.employment_status='ACTIVE'
                 GROUP BY d.department_id,d.department_name ORDER BY employee_count DESC"""
        result = isolate_sql(sql, 101, dialect="sqlite")
        self.assertEqual(result["status"], "REPAIRED", result)
        self.assertIn("d.tenant_id = 101", result["finalSql"])
        db = sqlite3.connect(":memory:")
        self.addCleanup(db.close)
        db.executescript("""
            CREATE TABLE employees(employee_id INT,department_id INT,tenant_id INT,employment_status TEXT);
            CREATE TABLE departments(department_id INT,tenant_id INT,department_name TEXT);
            INSERT INTO employees VALUES (1,10,101,'ACTIVE'),(2,10,101,'ACTIVE'),(3,10,102,'ACTIVE');
            INSERT INTO departments VALUES (10,101,'Our HR'),(10,102,'Other HR');
        """)
        original_rows = db.execute(sql).fetchall()
        final_rows = db.execute(result["parameterizedSql"], result["parameters"]).fetchall()
        self.assertEqual(original_rows, [("Our HR", 2)])
        self.assertEqual(final_rows, original_rows)


if __name__ == "__main__":
    unittest.main()
