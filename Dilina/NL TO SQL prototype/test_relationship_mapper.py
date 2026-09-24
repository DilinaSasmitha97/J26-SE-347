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
        self.assertIn("Multi-Hop Relational Join Paths", hints)
        self.assertIn("car_makers", hints.lower())

if __name__ == "__main__":
    unittest.main()
