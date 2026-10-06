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

    def test_format_grounding_hints_silent_protection(self):
        # 1. Direct match ('france' -> 'France') must be SILENT (empty string) to prevent prompt poisoning
        direct_matches = [
            {"term": "france", "table": "COUNTRIES", "column": "CountryName", "value": "France", "match_type": "exact_cell_value"}
        ]
        silent_hints = self.resolver.format_grounding_hints(direct_matches)
        self.assertEqual(silent_hints, "")

        # 2. Discrepancy match ('houses' -> 'HSE') must be formatted as non-coercive domain translation note
        discrepancy_matches = [
            {"term": "houses", "table": "Properties", "column": "property_type_code", "value": "HSE", "match_type": "abbreviation_mapping"}
        ]
        disc_hints = self.resolver.format_grounding_hints(discrepancy_matches)
        self.assertIn("Schema Value Grounding", disc_hints)
        self.assertIn("Properties.property_type_code = 'HSE'", disc_hints)
        self.assertNotIn("COUNTRIES", disc_hints)

    def test_disambiguation_multi_word_entity(self):
        # Multi-word entity whose column is non-obvious ('amc hornet sportabout (sw)' in column 'Make')
        matches = [
            {"term": "amc hornet sportabout (sw)", "table": "CAR_NAMES", "column": "Make", "value": "amc hornet sportabout (sw)", "match_type": "exact_cell_value"}
        ]
        hints = self.resolver.format_grounding_hints(matches)
        self.assertIn("Schema Value Grounding", hints)
        self.assertIn("CAR_NAMES.Make", hints)

    def test_active_probing_lookup(self):
        # Insert a record that represents an active lookup
        val = self.resolver.active_probe_column(self.conn, "CAR_NAMES", "Make", "amc hornet")
        self.assertIsNotNone(val)
        self.assertEqual(val, "amc hornet sportabout (sw)")

if __name__ == "__main__":
    unittest.main()
