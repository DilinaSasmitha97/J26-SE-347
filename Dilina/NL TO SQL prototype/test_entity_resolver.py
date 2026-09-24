import unittest
import sqlite3
from entity_resolver import ContextualEntityResolver

class TestEntityResolver(unittest.TestCase):
    def setUp(self):
        self.resolver = ContextualEntityResolver()
        # Set up an in-memory SQLite database
        self.conn = sqlite3.connect(":memory:")
        cursor = self.conn.cursor()
        
        # Create test tables
        cursor.execute("""
        CREATE TABLE COUNTRIES (
            CountryId INTEGER PRIMARY KEY,
            CountryName TEXT
        );
        """)
        cursor.execute("INSERT INTO COUNTRIES VALUES (1, 'France'), (2, 'USA'), (3, 'Germany');")
        
        cursor.execute("""
        CREATE TABLE Properties (
            property_id INTEGER PRIMARY KEY,
            property_type_code TEXT,
            property_name TEXT
        );
        """)
        cursor.execute("INSERT INTO Properties VALUES (101, 'HSE', 'Maple Villa'), (102, 'APT', 'Sunset Heights');")

        cursor.execute("""
        CREATE TABLE CAR_NAMES (
            MakeId INTEGER PRIMARY KEY,
            Make TEXT,
            Model TEXT
        );
        """)
        cursor.execute("INSERT INTO CAR_NAMES VALUES (1, 'amc hornet sportabout (sw)', 'amc hornet');")
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_extract_candidate_terms(self):
        query = "How many car makers are there in 'france' that produced amc hornet sportabout (sw)?"
        terms = self.resolver.extract_candidate_terms(query)
        self.assertIn("france", [t.lower() for t in terms])
        self.assertIn("amc hornet sportabout (sw)", [t.lower() for t in terms])

    def test_resolve_exact_cell_value(self):
        query = "How many car makers are there in france?"
        matches, grounded_tables = self.resolver.resolve_grounded_entities(
            nl_query=query,
            db_conn=self.conn,
            tables_to_scan=["COUNTRIES"]
        )
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["table"], "COUNTRIES")
        self.assertEqual(matches[0]["column"], "CountryName")
        self.assertEqual(matches[0]["value"], "France")
        self.assertIn("COUNTRIES", grounded_tables)

    def test_resolve_abbreviation_mapping(self):
        query = "Show all properties that are houses"
        matches, grounded_tables = self.resolver.resolve_grounded_entities(
            nl_query=query,
            db_conn=self.conn,
            tables_to_scan=["Properties"]
        )
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["column"], "property_type_code")
        self.assertEqual(matches[0]["value"], "HSE")
        self.assertIn("Properties", grounded_tables)

    def test_resolve_substring_cell_value(self):
        query = "How much does the car accelerate that makes amc hornet sportabout (sw)?"
        matches, grounded_tables = self.resolver.resolve_grounded_entities(
            nl_query=query,
            db_conn=self.conn,
            tables_to_scan=["CAR_NAMES"]
        )
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["column"], "Make")
        self.assertEqual(matches[0]["value"], "amc hornet sportabout (sw)")

    def test_format_grounding_hints(self):
        matches = [
            {"term": "france", "table": "COUNTRIES", "column": "CountryName", "value": "France"},
            {"term": "houses", "table": "Properties", "column": "property_type_code", "value": "HSE"}
        ]
        hints = self.resolver.format_grounding_hints(matches)
        self.assertIn("Contextual Entity & Cell-Value Groundings", hints)
        self.assertIn("COUNTRIES.CountryName = 'France'", hints)
        self.assertIn("Properties.property_type_code = 'HSE'", hints)

if __name__ == "__main__":
    unittest.main()
