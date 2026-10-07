# inspector.py

from typing import List, Optional

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError


class SQLInspectorError(Exception):
    """
    Custom error used when SQL inspection fails.
    """
    pass


def parse_sql(sql: str, dialect: str = "mysql") -> exp.Expression:
    """
    Parse a single SQL statement using SQLGlot.

    Parameters
    ----------
    sql : str
        Raw SQL string.
    dialect : str
        SQL dialect to use. Default is MySQL.

    Returns
    -------
    sqlglot.exp.Expression
        Parsed SQLGlot AST expression.

    Raises
    ------
    SQLInspectorError
        If SQL is empty, invalid, or contains multiple statements.
    """

    if not isinstance(sql, str):
        raise SQLInspectorError("SQL must be a string.")

    sql = sql.strip()

    if not sql:
        raise SQLInspectorError("SQL cannot be empty.")

    try:
        statements = sqlglot.parse(
            sql,
            read=dialect
        )

    except ParseError as error:
        raise SQLInspectorError(
            f"Invalid SQL syntax: {str(error)}"
        ) from error

    except Exception as error:
        raise SQLInspectorError(
            f"Failed to parse SQL: {str(error)}"
        ) from error

    # Remove any empty parsed expressions
    statements = [
        statement
        for statement in statements
        if statement is not None
    ]

    if len(statements) == 0:
        raise SQLInspectorError(
            "No valid SQL statement was found."
        )

    # For security middleware, it is safer to process
    # exactly one SQL statement at a time.
    if len(statements) > 1:
        raise SQLInspectorError(
            "Multiple SQL statements are not allowed."
        )

    return statements[0]


def get_statement_type(expression: exp.Expression) -> str:
    """
    Return the main SQL statement type.

    Examples:
        SELECT
        INSERT
        UPDATE
        DELETE
    """

    if expression is None:
        raise SQLInspectorError(
            "SQL expression cannot be None."
        )

    return expression.key.upper()


def is_select_statement(expression: exp.Expression) -> bool:
    """
    Check whether the parsed SQL statement is a SELECT query.
    """

    return isinstance(expression, exp.Select)


def get_raw_tables(expression: exp.Expression) -> List[exp.Table]:
    """
    Return all SQLGlot Table nodes found in the SQL.

    The extractor.py file can later convert these
    nodes into clean JSON.
    """

    if expression is None:
        return []

    return list(
        expression.find_all(exp.Table)
    )


def get_raw_columns(expression: exp.Expression) -> List[exp.Column]:
    """
    Return all SQLGlot Column nodes found in the SQL.
    """

    if expression is None:
        return []

    return list(
        expression.find_all(exp.Column)
    )


def get_where_expression(
    expression: exp.Expression
) -> Optional[exp.Where]:
    """
    Return the WHERE expression if one exists.

    Example:

        SELECT *
        FROM employees
        WHERE tenant_id = 101

    Returns the SQLGlot WHERE node.
    """

    if expression is None:
        return None

    return expression.args.get("where")


def get_raw_joins(expression: exp.Expression) -> List[exp.Join]:
    """
    Return all JOIN nodes from the SQL.
    """

    if expression is None:
        return []

    return list(
        expression.find_all(exp.Join)
    )


def normalize_sql(
    expression: exp.Expression,
    dialect: str = "mysql"
) -> str:
    """
    Convert the parsed AST back into normalized SQL.

    Useful later for:
    - testing
    - debugging
    - SQL rewriting
    """

    if expression is None:
        raise SQLInspectorError(
            "SQL expression cannot be None."
        )

    try:
        return expression.sql(
            dialect=dialect,
            pretty=False
        )

    except Exception as error:
        raise SQLInspectorError(
            f"Failed to normalize SQL: {str(error)}"
        ) from error


def inspect_basic(
    sql: str,
    dialect: str = "mysql"
) -> dict:
    """
    Basic inspection helper for testing inspector.py.

    This does NOT perform security checking.

    It only proves that SQLGlot can parse the query
    and identify basic SQL structures.

    extractor.py will later create the detailed
    JSON representation used by the Node.js middleware.
    """

    expression = parse_sql(
        sql,
        dialect=dialect
    )

    tables = get_raw_tables(expression)
    columns = get_raw_columns(expression)
    joins = get_raw_joins(expression)
    where_expression = get_where_expression(expression)

    return {
        "statementType": get_statement_type(expression),

        "isSelect": is_select_statement(expression),

        "normalizedSql": normalize_sql(
            expression,
            dialect=dialect
        ),

        "tableCount": len(tables),

        "columnCount": len(columns),

        "joinCount": len(joins),

        "hasWhere": where_expression is not None
    }


# ---------------------------------------------------------
# Manual test
# ---------------------------------------------------------

if __name__ == "__main__":

    test_sql = """
    SELECT e.name, c.name
    FROM employees e
    JOIN children c
        ON c.employee_id = e.id
    WHERE e.tenant_id = 101
      AND e.department_id = 1;
    """

    try:

        expression = parse_sql(test_sql)

        print("\n==============================")
        print("SQL PARSED SUCCESSFULLY")
        print("==============================")

        print("\nStatement type:")
        print(
            get_statement_type(expression)
        )

        print("\nNormalized SQL:")
        print(
            normalize_sql(expression)
        )

        print("\nTables:")
        for table in get_raw_tables(expression):

            print({
                "name": table.name,
                "alias": table.alias or None
            })

        print("\nColumns:")
        for column in get_raw_columns(expression):

            print({
                "table": column.table or None,
                "column": column.name
            })

        print("\nWHERE:")
        where_expression = get_where_expression(
            expression
        )

        if where_expression:
            print(where_expression.sql())
        else:
            print("No WHERE condition")

        print("\nJoins:")
        for join in get_raw_joins(expression):
            print(join.sql())

        print("\nBasic inspection:")
        print(
            inspect_basic(test_sql)
        )

        print("\nAST:")
        print(
            expression.dump()
        )

    except SQLInspectorError as error:

        print("\nSQL INSPECTION FAILED")
        print(error)