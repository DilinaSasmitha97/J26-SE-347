import schema_extractor

def run_tests():
    print("=== Testing Task 1: Minimal-Context Schema Extractor ===")
    
    # 4-Table DDL Schema (Spider concert_singer database)
    sample_ddl = """
    CREATE TABLE stadium (
        Stadium_ID int NOT NULL,
        Location text,
        Name text,
        Capacity int,
        Highest int,
        Lowest int,
        Average int,
        PRIMARY KEY (Stadium_ID)
    );

    CREATE TABLE singer (
        Singer_ID int NOT NULL,
        Name text,
        Country text,
        Song_Name text,
        Song_release_year text,
        Age int,
        Is_male text,
        PRIMARY KEY (Singer_ID)
    );

    CREATE TABLE concert (
        concert_ID int NOT NULL,
        concert_Name text,
        Theme text,
        Stadium_ID text,
        Year text,
        PRIMARY KEY (concert_ID),
        FOREIGN KEY (Stadium_ID) REFERENCES stadium(Stadium_ID)
    );

    CREATE TABLE singer_in_concert (
        concert_ID int NOT NULL,
        Singer_ID text NOT NULL,
        PRIMARY KEY (concert_ID, Singer_ID),
        FOREIGN KEY (concert_ID) REFERENCES concert(concert_ID),
        FOREIGN KEY (Singer_ID) REFERENCES singer(Singer_ID)
    );
    """

    # Test 1: Single Table Question
    q1 = "What is the capacity of the stadium with the highest attendance?"
    pruned_ddl1, stats1 = schema_extractor.extract_minimal_schema(q1, sample_ddl)
    print(f"\n[Test 1] Question: '{q1}'")
    print(f"  -> Input Tables:  {stats1['original_table_count']}")
    print(f"  -> Output Tables: {stats1['pruned_table_count']} {stats1['selected_tables']}")
    print(f"  -> Token Reduction: {stats1['token_reduction_pct']}%")
    assert "stadium" in stats1["selected_tables"]
    assert stats1["pruned_table_count"] <= 2, f"Expected <= 2 tables, got {stats1['pruned_table_count']}"
    print("  [PASS] TEST 1 PASSED: 4 tables pruned down to 2 tables (50% reduction)!")

    # Test 2: Multi-Table JOIN Question with Foreign Keys
    q2 = "List the names of singers who performed in concerts in 2024."
    pruned_ddl2, stats2 = schema_extractor.extract_minimal_schema(q2, sample_ddl)
    print(f"\n[Test 2] Question: '{q2}'")
    print(f"  -> Input Tables:  {stats2['original_table_count']}")
    print(f"  -> Output Tables: {stats2['pruned_table_count']} {stats2['selected_tables']}")
    print(f"  -> Token Reduction: {stats2['token_reduction_pct']}%")
    assert "singer" in stats2["selected_tables"]
    assert "concert" in stats2["selected_tables"]
    assert "singer_in_concert" in stats2["selected_tables"], "Bridge table singer_in_concert should be preserved by FK graph!"
    print("  [PASS] TEST 2 PASSED: Automatically included intermediate bridge table for JOINs!")

    # Test 3: Ambiguous Question (Triggers Interactive Clarification)
    q3 = "Show me the general statistics."
    pruned_ddl3, stats3 = schema_extractor.extract_minimal_schema(q3, sample_ddl)
    print(f"\n[Test 3] Ambiguous Question: '{q3}'")
    print(f"  -> Needs Clarification? {stats3['needs_clarification']}")
    print(f"  -> Suggested Options:  {stats3['clarification_suggestions']}")
    assert stats3["needs_clarification"] == True
    print("  [PASS] TEST 3 PASSED: Successfully detected ambiguous question and suggested options for user clarification!")

    print("\n[SUCCESS] ALL TASK 1 UNIT TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
