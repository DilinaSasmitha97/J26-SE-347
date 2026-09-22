import os
import pyodbc
import sqlite3
from dotenv import load_dotenv
from profiler import time_block, log_step

load_dotenv()

def get_db_connection(profiler=None):
    """
    Connect to Microsoft SQL Server using settings from environment variables.
    Will attempt to use ODBC Driver 17, with a fallback to the standard SQL Server driver.
    """
    server = os.getenv("DB_SERVER", "MSI\\SQLEXPRESS")
    database_name = os.getenv("DB_NAME", "NemsuERPNew")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    
    # Priority 1: ODBC Driver 17 for SQL Server
    # Priority 2: Standard SQL Server driver (fallback)
    drivers = ["ODBC Driver 17 for SQL Server", "SQL Server"]
    conn = None
    
    for driver in drivers:
        if user and password:
            auth_part = f"UID={user};PWD={password};"
        else:
            auth_part = "Integrated Security=True;"
            
        conn_str = (
            f"DRIVER={{{driver}}};"
            f"Server={server};"
            f"Database={database_name};"
            f"{auth_part}"
            f"MultipleActiveResultSets=true;"
            f"TrustServerCertificate=yes;"
            f"Encrypt=no;"
            f"Command Timeout=0;"
        )
        try:
            with time_block(f"SQL Server Connect Attempt ({driver})", parent_summary=profiler.categories if profiler else None, category="Database Connection"):
                conn = pyodbc.connect(conn_str)
            log_step(f"Successfully connected using driver: {driver}")
            break
        except pyodbc.Error as e:
            log_step(f"Connection failed for driver '{driver}': {e}", level="WARN")
            pass
            
    if not conn:
        raise Exception("Could not connect to the database with any driver. Please verify your connection details.")
        
    return conn


def extract_schema_as_create_statements(conn, profiler=None) -> str:
    """
    Extracts the database schema (tables, columns, datatypes, PKs, FKs) 
    and formats them strictly as CREATE TABLE SQL statements including schema prefixes.
    Caches output to local erp_schema_cache.sql for instant 0.001s loading.
    """
    cache_path = os.path.join(os.path.dirname(__file__), "erp_schema_cache.sql")
    if os.path.exists(cache_path):
        log_step(f"Loaded ERP schema DDL instantly from local cache: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()

    cursor = conn.cursor()
    
    # 1. Get all Base Tables with their Schema Name
    with time_block("DB Query: Discover Base Tables", parent_summary=profiler.categories if profiler else None, category="Schema Extraction - Table Discovery"):
        cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG=DB_NAME()")
        tables = [(row[0], row[1]) for row in cursor.fetchall()]
    
    log_step(f"Found {len(tables)} base tables to extract schema for.")
    schema_statements = []
    
    with time_block(f"DB Query: Extract Schema Details for {len(tables)} Tables", parent_summary=profiler.categories if profiler else None, category="Schema Extraction - Column & Constraint Metadata"):
        for idx, (schema, table) in enumerate(tables, 1):
            with time_block(f"Table [{schema}].[{table}] ({idx}/{len(tables)}) metadata fetch", parent_summary=profiler.categories if profiler else None, category="Schema Extraction - Per Table Overhead"):
                # 2. Get Columns and Data Types filtered by Schema and Table
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                    ORDER BY ORDINAL_POSITION
                """, schema, table)
                columns = cursor.fetchall()
                
                # 3. Get Primary Keys filtered by Schema and Table
                cursor.execute("""
                    SELECT ccu.COLUMN_NAME
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                    JOIN INFORMATION_SCHEMA.CONSTRAINT_COLUMN_USAGE ccu 
                        ON tc.CONSTRAINT_NAME = ccu.CONSTRAINT_NAME 
                        AND tc.TABLE_SCHEMA = ccu.TABLE_SCHEMA
                    WHERE tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ? AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                """, schema, table)
                pks = [row[0] for row in cursor.fetchall()]
                
                # 4. Get Foreign Keys (including referenced schema name)
                cursor.execute("""
                    SELECT 
                        col_fk.name as FK_Column,
                        SCHEMA_NAME(tab_pk.schema_id) as PK_Schema,
                        tab_pk.name as PK_Table,
                        col_pk.name as PK_Column
                    FROM sys.foreign_key_columns fkc
                    INNER JOIN sys.tables tab_fk ON tab_fk.object_id = fkc.parent_object_id
                    INNER JOIN sys.columns col_fk ON col_fk.column_id = fkc.parent_column_id AND col_fk.object_id = tab_fk.object_id
                    INNER JOIN sys.tables tab_pk ON tab_pk.object_id = fkc.referenced_object_id
                    INNER JOIN sys.columns col_pk ON col_pk.column_id = fkc.referenced_column_id AND col_pk.object_id = tab_pk.object_id
                    WHERE SCHEMA_NAME(tab_fk.schema_id) = ? AND tab_fk.name = ?
                """, schema, table)
                fks = cursor.fetchall()
                
                # 5. Format into a CREATE TABLE statement with schema prefix
                create_stmt = f"CREATE TABLE [{schema}].[{table}] (\n"
                col_defs = []
                
                for col in columns:
                    col_name = col[0]
                    data_type = col[1]
                    max_len = col[2]
                    is_nullable = "NULL" if col[3] == "YES" else "NOT NULL"
                    
                    type_str = data_type
                    if type_str in ['varchar', 'nvarchar', 'char', 'nchar']:
                        length = "MAX" if max_len == -1 else str(max_len)
                        type_str += f"({length})"
                        
                    col_defs.append(f"    [{col_name}] {type_str} {is_nullable}")
                    
                if pks:
                    pk_cols = ", ".join([f"[{pk}]" for pk in pks])
                    col_defs.append(f"    PRIMARY KEY ({pk_cols})")
                    
                for fk in fks:
                    col_defs.append(f"    FOREIGN KEY ([{fk[0]}]) REFERENCES [{fk[1]}].[{fk[2]}]([{fk[3]}])")
                    
                create_stmt += ",\n".join(col_defs)
                create_stmt += "\n);"
                schema_statements.append(create_stmt)
        
    full_ddl = "\n\n".join(schema_statements)
    
    # Save cache file for instant future runs
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            f.write(full_ddl)
        log_step(f"Saved ERP schema DDL cache to: {cache_path}")
    except Exception as e:
        log_step(f"Warning: Could not save DDL cache: {e}", level="WARN")

    return full_ddl

def get_sqlite_connection(db_path: str, profiler=None):
    """
    Connect to a local SQLite database file.
    """
    with time_block(f"Connect to SQLite DB ({os.path.basename(db_path)})", parent_summary=profiler.categories if profiler else None, category="SQLite Connection"):
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"SQLite database file not found at: {db_path}")
        conn = sqlite3.connect(db_path, isolation_level=None)
        return conn

def extract_sqlite_schema_as_create_statements(conn, profiler=None) -> str:
    """
    Extracts the database schema for SQLite.
    SQLite conveniently stores the exact CREATE TABLE statement in the sqlite_master catalog.
    """
    with time_block("Extract SQLite Master Schema", parent_summary=profiler.categories if profiler else None, category="SQLite Schema Extraction"):
        cursor = conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        
        schema_statements = []
        for row in cursor.fetchall():
            if row[0]:  # Sometimes sql can be None for internal tables
                stmt = row[0].strip()
                if not stmt.endswith(';'):
                    stmt += ';'
                schema_statements.append(stmt)
                
        return "\n\n".join(schema_statements)
def execute_query(sql_query: str, max_rows: int = 100):
    """
    Executes a SQL query against the configured database and returns
    column headers and row data as JSON-serializable dictionaries.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql_query)
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = []
        if columns:
            for row in cursor.fetchmany(max_rows):
                row_dict = {}
                for col_name, val in zip(columns, row):
                    if val is not None and not isinstance(val, (int, float, bool, str)):
                        row_dict[col_name] = str(val)
                    else:
                        row_dict[col_name] = val
                rows.append(row_dict)
        return columns, rows
    finally:
        conn.close()


def get_cached_or_live_schema(force_refresh: bool = False) -> str:
    """
    Returns full DDL schema from local erp_schema_cache.sql cache or extracts from live DB.
    """
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "erp_schema_cache.sql")
    if not force_refresh and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
            
    conn = get_db_connection()
    try:
        schema = extract_schema_as_create_statements(conn)
        return schema
    finally:
        conn.close()

