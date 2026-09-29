import sqlite3
from refinement_loop import sanitize_sql_keyword_spacing, execute_refinement_loop, dry_run_validate

def test_glued_alias_keyword_spacing():
    # 1. Alias with digits followed by ON/JOIN/WHERE
    assert sanitize_sql_keyword_spacing("SELECT * FROM Student S JOIN Pets P2ON S.id = P2.id") == \
           "SELECT * FROM Student S JOIN Pets P2 ON S.id = P2.id"

    assert sanitize_sql_keyword_spacing("FROM Student AS T1JOIN Has_Pet") == \
           "FROM Student AS T1 JOIN Has_Pet"

    assert sanitize_sql_keyword_spacing("JOIN countries AS T2ON T1.ContId = T2.Continent") == \
           "JOIN countries AS T2 ON T1.ContId = T2.Continent"

    assert sanitize_sql_keyword_spacing("JOIN car_names AS T3ON T1.Id = T3.MakeId") == \
           "JOIN car_names AS T3 ON T1.Id = T3.MakeId"

    assert sanitize_sql_keyword_spacing("SELECT * FROM cars_data AS T1WHERE T1.Year = 1970") == \
           "SELECT * FROM cars_data AS T1 WHERE T1.Year = 1970"

def test_preserves_legitimate_identifiers_and_literals():
    # 2. English words ending in ON (LOCATION, PERSON, ACTION) must NOT be split
    query = "SELECT location, person_action FROM stadium WHERE description = 'P2ON THE ROAD';"
    assert sanitize_sql_keyword_spacing(query) == query

    # Real table names ending in ON
    query2 = "SELECT * FROM station JOIN region ON station.id = region.id"
    assert sanitize_sql_keyword_spacing(query2) == query2

    # String literals containing glued keywords must NOT be touched
    query3 = "SELECT * FROM t WHERE text = 'AS T1JOIN';"
    assert sanitize_sql_keyword_spacing(query3) == query3

def test_compiler_gated_execution():
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE Student (StuID INT, Fname TEXT, Age INT);")
    cursor.execute("CREATE TABLE Pets (PetID INT, PetType TEXT);")
    cursor.execute("CREATE TABLE Has_Pet (StuID INT, PetID INT);")

    # A. Valid query must pass completely untouched (0 refinement attempts, 0 sanitizer modifications)
    valid_sql = "SELECT S.Fname FROM Student S JOIN Has_Pet HP ON S.StuID = HP.StuID;"
    res_sql, is_valid, attempts, stats = execute_refinement_loop(
        nl_query="Find student names with pets",
        initial_sql=valid_sql,
        schema_meta="CREATE TABLE Student ...",
        db_conn=conn
    )
    assert is_valid is True
    assert res_sql == valid_sql
    assert attempts == 0
    assert stats.get("healed") is False
    assert stats.get("healed_by_sanitizer") is not True

    # B. Query with glued P2ON fails initial EXPLAIN, but is healed instantly by sanitizer with 0 LLM calls
    broken_sql = "SELECT S.Fname FROM Student S JOIN Has_Pet HP ON S.StuID = HP.StuID JOIN Pets P2ON HP.PetID = P2.PetID;"
    res_sql, is_valid, attempts, stats = execute_refinement_loop(
        nl_query="Find student names with pets",
        initial_sql=broken_sql,
        schema_meta="CREATE TABLE Student ...",
        db_conn=conn
    )
    assert is_valid is True
    assert "P2 ON" in res_sql
    assert attempts == 0
    assert stats.get("healed") is True
    assert stats.get("healed_by_sanitizer") is True

    conn.close()

if __name__ == "__main__":
    test_glued_alias_keyword_spacing()
    test_preserves_legitimate_identifiers_and_literals()
    test_compiler_gated_execution()
    print("ALL SYNTAX SANITIZER TESTS PASSED!")
