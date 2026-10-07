import os
import re
import sqlite3

def convert_mysql_to_sqlite(mysql_sql_path: str, sqlite_db_path: str):
    """
    Converts MySQL 8.x DDL and INSERT statements from multitenant_hr_sample.sql
    into a fully populated, portable SQLite database for zero-config teammate testing.
    """
    print(f"Reading MySQL source: {mysql_sql_path}")
    with open(mysql_sql_path, "r", encoding="utf-8") as f:
        content = f.read()

    # If sqlite file already exists, remove it
    if os.path.exists(sqlite_db_path):
        os.remove(sqlite_db_path)

    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF;")
    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA journal_mode = MEMORY;")

    # Fix People's Bank single quote escaping for SQLite standard SQL
    content = content.replace("'People\\'s Bank'", "'People''s Bank'")
    content = content.replace("'People's Bank'", "'People''s Bank'")

    # Split into statements
    statements = content.split(";")
    success_count = 0
    error_count = 0

    for stmt in statements:
        # Strip comments from beginning of statement
        lines = []
        for line in stmt.splitlines():
            stripped = line.strip()
            if stripped.startswith("--") or stripped.startswith("/*"):
                continue
            lines.append(line)
        stmt = "\n".join(lines).strip()
        if not stmt:
            continue

        # Skip MySQL database-level statements
        if any(stmt.upper().startswith(x) for x in [
            "SET FOREIGN_KEY_CHECKS",
            "DROP DATABASE",
            "CREATE DATABASE",
            "USE "
        ]):
            continue

        # Clean MySQL table definitions
        if "CREATE TABLE" in stmt.upper():
            # Replace ENUM(...) with TEXT
            stmt = re.sub(r"ENUM\([^)]+\)", "TEXT", stmt, flags=re.IGNORECASE)
            # Replace ON UPDATE CURRENT_TIMESTAMP
            stmt = re.sub(r"ON UPDATE CURRENT_TIMESTAMP", "", stmt, flags=re.IGNORECASE)
            # Remove MySQL KEY index declarations inside CREATE TABLE
            tbl_lines = []
            for line in stmt.splitlines():
                stripped = line.strip()
                # Check for MySQL index lines like KEY idx_... (...)
                if re.match(r"^KEY\s+\w+\s*\(", stripped, re.IGNORECASE):
                    continue
                # Check for UNIQUE KEY uq_... (...) -> UNIQUE (...)
                uq_match = re.match(r"^UNIQUE KEY\s+\w+\s*(\([^)]+\))", stripped, re.IGNORECASE)
                if uq_match:
                    has_trailing_comma = stripped.endswith(",")
                    line = f"    UNIQUE {uq_match.group(1)}" + ("," if has_trailing_comma else "")
                tbl_lines.append(line)
            stmt = "\n".join(tbl_lines)
            # Fix any trailing comma before closing parenthesis
            stmt = re.sub(r",\s*\)", "\n)", stmt)

        try:
            cursor.execute(stmt)
            success_count += 1
        except Exception as e:
            error_count += 1
            print(f"Warning on statement: {e}\nSnippet: {stmt[:120]}...\n")

    conn.commit()
    print(f"Conversion complete! Executed {success_count} statements ({error_count} skipped/errors).")

    # Verify tables and row counts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"Created {len(tables)} tables: {', '.join(tables)}")

    total_rows = 0
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t};")
        count = cursor.fetchone()[0]
        total_rows += count
        print(f"  - Table '{t}': {count} rows")

    print(f"Total rows in SQLite database: {total_rows}")
    conn.close()
    print(f"SQLite DB successfully created at: {sqlite_db_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    src_sql = os.path.join(base_dir, "multitenant_hr_sample.sql")
    dst_db = os.path.join(base_dir, "multitenant_hr.db")
    convert_mysql_to_sqlite(src_sql, dst_db)
