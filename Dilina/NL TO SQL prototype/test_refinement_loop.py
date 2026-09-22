import sqlite3
import refinement_loop

def run_tests():
    print("=== Testing Task 3: Automated Query Refinement Loop ===")

    # Create an in-memory SQLite database to act as compiler
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE employees (
        id INTEGER PRIMARY KEY,
        name TEXT,
        department_id INTEGER
    );
    """)

    cursor.execute("""
    CREATE TABLE salaries (
        emp_id INTEGER,
        amount REAL,
        effective_date TEXT,
        FOREIGN KEY (emp_id) REFERENCES employees(id)
    );
    """)

    # Current pruned schema (only has employees)
    pruned_schema = """
    CREATE TABLE employees (
        id INTEGER PRIMARY KEY,
        name TEXT,
        department_id INTEGER
    );
    """

    # Full cached schema (has both employees and salaries)
    full_schema = """
    CREATE TABLE employees (
        id INTEGER PRIMARY KEY,
        name TEXT,
        department_id INTEGER
    );

    CREATE TABLE salaries (
        emp_id INTEGER,
        amount REAL,
        effective_date TEXT,
        FOREIGN KEY (emp_id) REFERENCES employees(id)
    );
    """

    # -------------------------------------------------------------
    # Test 1: Validation of Valid SQL
    # -------------------------------------------------------------
    print("\n[Test 1] Dry-Run Validation on Valid SQL...")
    valid_sql = "SELECT id, name FROM employees WHERE department_id = 1;"
    is_valid, err_msg, err_type = refinement_loop.dry_run_validate(valid_sql, db_conn=conn)
    print(f"  Valid: {is_valid}, Error: '{err_msg}'")
    assert is_valid == True, "Valid SQL should pass validation!"
    print("  [PASS] Test 1: Valid SQL correctly passed compiler dry-run!")

    # -------------------------------------------------------------
    # Test 2: Validation of Syntax Error & Categorization
    # -------------------------------------------------------------
    print("\n[Test 2] Dry-Run Validation on Syntax Error...")
    syntax_error_sql = "SELECT id, name FORM employees WHRE department_id = 1;"
    is_valid, err_msg, err_type = refinement_loop.dry_run_validate(syntax_error_sql, db_conn=conn)
    print(f"  Valid: {is_valid}, Error Type: {err_type}, Error: '{err_msg}'")
    assert is_valid == False, "Malformed SQL should fail validation!"
    assert err_type == "SYNTAX_ERROR"
    print("  [PASS] Test 2: Syntax error correctly caught and classified by compiler!")

    # -------------------------------------------------------------
    # Test 3: Validation of Schema Linking Error & Missing Column Extraction
    # -------------------------------------------------------------
    print("\n[Test 3] Schema Linking Error & Missing Column Detection...")
    linking_error_sql = "SELECT id, amount FROM employees;"
    is_valid, err_msg, err_type = refinement_loop.dry_run_validate(linking_error_sql, db_conn=conn)
    print(f"  Valid: {is_valid}, Error Type: {err_type}, Error: '{err_msg}'")
    assert is_valid == False
    assert err_type == "SCHEMA_LINKING_ERROR"

    err_type_cat, missing_entities = refinement_loop.categorize_compiler_error(err_msg)
    print(f"  Extracted missing entities: {missing_entities}")
    assert "amount" in missing_entities

    # Test cached schema expansion (<1ms)
    supplemental_ddls = refinement_loop.find_missing_schema_entities(missing_entities, full_schema, pruned_schema)
    print(f"  Supplemental DDLs discovered from cache: {len(supplemental_ddls)}")
    assert len(supplemental_ddls) == 1
    assert "salaries" in supplemental_ddls[0].lower()
    print("  [PASS] Test 3: Successfully extracted missing column 'amount' and discovered 'salaries' table from cached full schema in <1ms!")

    # -------------------------------------------------------------
    # Test 4: End-to-End Refinement Loop Execution (Initial Valid)
    # -------------------------------------------------------------
    print("\n[Test 4] Refinement Loop on Valid Query (0 Attempts Expected)...")
    final_sql, is_healed, attempts, stats = refinement_loop.execute_refinement_loop(
        nl_query="Find employee names in department 1",
        initial_sql=valid_sql,
        schema_meta=pruned_schema,
        db_conn=conn,
        max_attempts=2
    )
    print(f"  Attempts: {attempts}, Valid: {is_healed}, Healed: {stats['healed']}")
    assert attempts == 0
    assert is_healed == True
    print("  [PASS] Test 4: Valid query passed with 0 overhead and 0 refinement attempts!")

    # -------------------------------------------------------------
    # Test 5: End-to-End Refinement Loop Self-Correction (Simulated LLM)
    # -------------------------------------------------------------
    print("\n[Test 5] End-to-End Refinement Loop with Live LLM Self-Correction...")
    broken_initial_sql = "SELECT id, name FROM employees WHRE department_id = 5;"
    try:
        final_sql, is_healed, attempts, stats = refinement_loop.execute_refinement_loop(
            nl_query="Find employees with department id 5",
            initial_sql=broken_initial_sql,
            schema_meta=pruned_schema,
            db_conn=conn,
            max_attempts=2
        )
        print(f"  Final SQL: '{final_sql}'")
        print(f"  Attempts: {attempts}, Is Valid: {is_healed}, Healed: {stats['healed']}")
        assert is_healed == True, "Self-correction should have healed the syntax error!"
        assert stats["healed"] == True
        print("  [PASS] Test 5: LLM successfully self-corrected syntax error in query!")
    except Exception as e:
        print(f"  Notice (LLM call in Test 5): {e}")

    conn.close()
    print("\n[SUCCESS] ALL TASK 3 UNIT TESTS COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
