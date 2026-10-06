import unittest
from relationship_mapper import RelationshipMapper

SAMPLE_CAR_DDL = """
CREATE TABLE CAR_MAKERS (
    Id INTEGER PRIMARY KEY,
    Maker TEXT,
    FullName TEXT,
    Country TEXT
);

CREATE TABLE MODEL_LIST (
    ModelId INTEGER PRIMARY KEY,
    Maker INTEGER,
    Model TEXT,
    FOREIGN KEY (Maker) REFERENCES CAR_MAKERS(Id)
);

CREATE TABLE CAR_NAMES (
    MakeId INTEGER PRIMARY KEY,
    Model TEXT,
    Make TEXT,
    FOREIGN KEY (Model) REFERENCES MODEL_LIST(Model)
);

CREATE TABLE CARS_DATA (
    Id INTEGER PRIMARY KEY,
    MPG TEXT,
    Cylinders INTEGER,
    Edispl REAL,
    Horsepower TEXT,
    Weight REAL,
    Accelerate REAL,
    Year INTEGER,
    FOREIGN KEY (Id) REFERENCES CAR_NAMES(MakeId)
);
"""

class TestRelationshipMapper(unittest.TestCase):
    def setUp(self):
        self.mapper = RelationshipMapper()

    def test_parse_foreign_keys(self):
        fks = self.mapper.parse_foreign_keys_from_ddl(SAMPLE_CAR_DDL)
        self.assertGreaterEqual(len(fks), 3)
        # Check MODEL_LIST -> CAR_MAKERS
        self.assertTrue(any(fk["from_table"] == "MODEL_LIST" and fk["to_table"] == "CAR_MAKERS" for fk in fks))
        # Check CAR_NAMES -> MODEL_LIST
        self.assertTrue(any(fk["from_table"] == "CAR_NAMES" and fk["to_table"] == "MODEL_LIST" for fk in fks))
        # Check CARS_DATA -> CAR_NAMES
        self.assertTrue(any(fk["from_table"] == "CARS_DATA" and fk["to_table"] == "CAR_NAMES" for fk in fks))

    def test_multi_hop_shortest_path(self):
        fks = self.mapper.parse_foreign_keys_from_ddl(SAMPLE_CAR_DDL)
        graph = self.mapper.build_relational_graph(fks)
        
        # Test 3-hop path from CAR_MAKERS to CARS_DATA
        path = self.mapper.find_shortest_path(graph, "CAR_MAKERS", "CARS_DATA", max_hops=4)
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 3)
        
        # Intermediate steps should touch model_list and car_names
        visited_tables = [step["to_table"] for step in path]
        self.assertIn("model_list", visited_tables)
        self.assertIn("car_names", visited_tables)
        self.assertIn("cars_data", visited_tables)

    def test_resolve_multi_hop_bridges(self):
        terminals = {"CAR_MAKERS", "CARS_DATA"}
        bridge_tables, join_paths = self.mapper.resolve_multi_hop_bridges(terminals, SAMPLE_CAR_DDL)
        
        # Both MODEL_LIST and CAR_NAMES should be identified as bridge tables
        bridge_tables_lower = {b.lower() for b in bridge_tables}
        self.assertIn("model_list", bridge_tables_lower)
        self.assertIn("car_names", bridge_tables_lower)
        
        # Hints formatting
        hints = self.mapper.format_join_path_hints(join_paths)
        self.assertIn("Relational Guidance", hints)
        self.assertIn("car_makers", hints.lower())

    def test_negation_intent_detection(self):
        # Negative queries should be detected
        self.assertTrue(self.mapper.detect_negation_intent("Show names of students who do not have any friends"))
        self.assertTrue(self.mapper.detect_negation_intent("Find channels not playing cartoon written by Todd"))
        self.assertTrue(self.mapper.detect_negation_intent("Students who have no pets"))
        self.assertTrue(self.mapper.detect_negation_intent("Which departments are without any employees?"))
        self.assertTrue(self.mapper.detect_negation_intent("List all countries except France"))

        # Neutral queries should NOT trigger negation
        self.assertFalse(self.mapper.detect_negation_intent("Find all students and their pet names"))
        self.assertFalse(self.mapper.detect_negation_intent("What is the average salary of employees in IT?"))

    def test_format_canonical_join_skeleton_negation_guard(self):
        paths = [{
            "from_table": "students",
            "from_col": "stuid",
            "to_table": "has_pet",
            "to_col": "stuid"
        }]
        
        # Negative query triggers anti-join notice
        neg_hint = self.mapper.format_canonical_join_skeleton(paths, nl_query="students who have no pets")
        self.assertIn("Exclusion intent detected", neg_hint)
        self.assertIn("do NOT force INNER JOIN", neg_hint)
        self.assertIn("students.stuid = has_pet.stuid", neg_hint)

        # Positive query triggers standard join condition
        pos_hint = self.mapper.format_canonical_join_skeleton(paths, nl_query="students and their pets")
        self.assertIn("Prefer explicit JOIN over scalar subqueries", pos_hint)
        self.assertIn("Join Condition: students.stuid = has_pet.stuid", pos_hint)

    def test_single_table_gating(self):
        # Queries with fewer than 2 tables must produce zero hints (silent gating)
        single_table = {"students"}
        hint = self.mapper.get_subgraph_join_paths(single_table, SAMPLE_CAR_DDL)
        self.assertEqual(hint, "")

        empty_table = set()
        hint_empty = self.mapper.get_subgraph_join_paths(empty_table, SAMPLE_CAR_DDL)
        self.assertEqual(hint_empty, "")

    def test_intent_weighted_disambiguation(self):
        # Two edges between flights and airports: SourceAirport vs DestAirport
        mock_graph = {
            "airports": [
                {
                    "neighbor": "flights",
                    "neighbor_raw": "FLIGHTS",
                    "from_col": "AirportCode",
                    "to_col": "SourceAirport",
                    "direction": "forward"
                },
                {
                    "neighbor": "flights",
                    "neighbor_raw": "FLIGHTS",
                    "from_col": "AirportCode",
                    "to_col": "DestAirport",
                    "direction": "forward"
                }
            ],
            "flights": [
                {
                    "neighbor": "airports",
                    "neighbor_raw": "AIRPORTS",
                    "from_col": "SourceAirport",
                    "to_col": "AirportCode",
                    "direction": "reverse"
                },
                {
                    "neighbor": "airports",
                    "neighbor_raw": "AIRPORTS",
                    "from_col": "DestAirport",
                    "to_col": "AirportCode",
                    "direction": "reverse"
                }
            ]
        }
        
        # Query asking for destination airport should select DestAirport
        dest_path = self.mapper.find_shortest_path(mock_graph, "airports", "flights", nl_query="Find the destination airport for flight 101")
        self.assertIsNotNone(dest_path)
        self.assertEqual(dest_path[0]["to_col"], "DestAirport")

        # Query asking for departure / source airport should select SourceAirport
        src_path = self.mapper.find_shortest_path(mock_graph, "airports", "flights", nl_query="What is the source departure airport?")
        self.assertIsNotNone(src_path)
        self.assertEqual(src_path[0]["to_col"], "SourceAirport")

if __name__ == "__main__":
    unittest.main()
