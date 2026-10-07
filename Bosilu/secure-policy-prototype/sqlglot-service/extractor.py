# extractor.py

from typing import Any, Dict, List, Optional

from sqlglot import exp

from inspector import (
    get_statement_type,
    normalize_sql,
)


def build_alias_map(expression: exp.Expression) -> Dict[str, str]:
    """
    Build alias -> real table mapping.

    Example:

        FROM employees e

    produces:

        {
            "e": "employees",
            "employees": "employees"
        }
    """

    alias_map = {}

    for table in expression.find_all(exp.Table):
        table_name = table.name
        alias = table.alias

        # Real table name maps to itself
        alias_map[table_name] = table_name

        # Alias maps to real table
        if alias:
            alias_map[alias] = table_name

    return alias_map


def resolve_table_name(
    table_reference: Optional[str],
    alias_map: Dict[str, str]
) -> Optional[str]:
    """
    Convert alias to real table name.

    Example:
        e -> employees
    """

    if not table_reference:
        return None

    return alias_map.get(
        table_reference,
        table_reference
    )


def extract_tables(
    expression: exp.Expression
) -> List[Dict[str, Any]]:
    """
    Extract tables and their aliases.

    Example output:

    [
        {
            "name": "employees",
            "alias": "e"
        }
    ]
    """

    tables = []

    seen = set()

    for table in expression.find_all(exp.Table):

        table_name = table.name
        alias = table.alias or None

        key = (
            table_name,
            alias
        )

        if key in seen:
            continue

        seen.add(key)

        tables.append({
            "name": table_name,
            "alias": alias
        })

    return tables


def extract_columns(
    expression: exp.Expression
) -> List[Dict[str, Any]]:
    """
    Extract all referenced columns.

    Aliases are resolved to real table names.

    Example:

        SELECT e.name
        FROM employees e

    returns:

    [
        {
            "table": "employees",
            "column": "name"
        }
    ]
    """

    alias_map = build_alias_map(expression)

    columns = []

    seen = set()

    for column in expression.find_all(exp.Column):

        table_reference = column.table or None

        resolved_table = resolve_table_name(
            table_reference,
            alias_map
        )

        column_name = column.name

        key = (
            resolved_table,
            column_name
        )

        if key in seen:
            continue

        seen.add(key)

        columns.append({
            "table": resolved_table,
            "column": column_name
        })

    return columns


def extract_literal_value(
    node: exp.Expression
) -> Any:
    """
    Convert SQLGlot literal values to normal Python values.

    Examples:
        101      -> 101
        'Colombo' -> "Colombo"
        TRUE      -> True
    """

    if isinstance(node, exp.Literal):
        try:
            return node.to_py()
        except Exception:
            return node.this

    if isinstance(node, exp.Boolean):
        return bool(node.this)

    if isinstance(node, exp.Null):
        return None

    # If it is not a literal, return SQL representation
    return node.sql()


def extract_simple_condition(
    condition: exp.Expression,
    alias_map: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """
    Extract a simple condition such as:

        e.tenant_id = 101
        e.department_id > 2
        e.region = 'Colombo'

    Returns a clean dictionary.
    """

    operator_map = {
        exp.EQ: "=",
        exp.NEQ: "!=",
        exp.GT: ">",
        exp.GTE: ">=",
        exp.LT: "<",
        exp.LTE: "<=",
    }

    for expression_type, operator in operator_map.items():

        if isinstance(condition, expression_type):

            left = condition.left
            right = condition.right

            # Standard case:
            # column OP value
            if isinstance(left, exp.Column):

                table_reference = left.table or None

                table_name = resolve_table_name(
                    table_reference,
                    alias_map
                )

                return {
                    "table": table_name,
                    "column": left.name,
                    "operator": operator,
                    "value": extract_literal_value(right)
                }

            # Reverse case:
            # value OP column
            if isinstance(right, exp.Column):

                table_reference = right.table or None

                table_name = resolve_table_name(
                    table_reference,
                    alias_map
                )

                reverse_operator_map = {
                    "=": "=",
                    "!=": "!=",
                    ">": "<",
                    ">=": "<=",
                    "<": ">",
                    "<=": ">="
                }

                return {
                    "table": table_name,
                    "column": right.name,
                    "operator": reverse_operator_map[operator],
                    "value": extract_literal_value(left)
                }

    return None


def flatten_and_conditions(
    node: exp.Expression
) -> List[exp.Expression]:
    """
    Flatten:

        a = 1 AND b = 2 AND c = 3

    into:

        [
            a = 1,
            b = 2,
            c = 3
        ]

    This is intentionally simple.
    OR handling can be added later.
    """

    if isinstance(node, exp.And):

        return (
            flatten_and_conditions(node.left)
            +
            flatten_and_conditions(node.right)
        )

    return [node]


def extract_filters(
    expression: exp.Expression
) -> List[Dict[str, Any]]:
    """
    Extract simple WHERE filters.

    Example:

        WHERE e.tenant_id = 101
          AND e.department_id = 1

    returns:

    [
        {
            "table": "employees",
            "column": "tenant_id",
            "operator": "=",
            "value": 101
        },
        {
            "table": "employees",
            "column": "department_id",
            "operator": "=",
            "value": 1
        }
    ]
    """

    alias_map = build_alias_map(expression)

    filters = []

    where = expression.args.get("where")

    if not where:
        return filters

    where_expression = where.this

    conditions = flatten_and_conditions(
        where_expression
    )

    for condition in conditions:

        extracted = extract_simple_condition(
            condition,
            alias_map
        )

        if extracted:
            filters.append(extracted)
        else:
            # Keep unsupported conditions visible
            # instead of silently ignoring them.
            filters.append({
                "type": "UNSUPPORTED",
                "raw": condition.sql()
            })

    return filters


def extract_join_condition(
    condition: exp.Expression,
    alias_map: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """
    Extract a column-to-column join condition.

    Example:

        c.employee_id = e.id

    returns:

    {
        "left": {
            "table": "children",
            "column": "employee_id"
        },
        "right": {
            "table": "employees",
            "column": "id"
        },
        "operator": "="
    }
    """

    if not isinstance(condition, exp.EQ):
        return None

    left = condition.left
    right = condition.right

    if not (
        isinstance(left, exp.Column)
        and isinstance(right, exp.Column)
    ):
        return None

    left_table = resolve_table_name(
        left.table or None,
        alias_map
    )

    right_table = resolve_table_name(
        right.table or None,
        alias_map
    )

    return {
        "left": {
            "table": left_table,
            "column": left.name
        },
        "right": {
            "table": right_table,
            "column": right.name
        },
        "operator": "="
    }


def extract_joins(
    expression: exp.Expression
) -> List[Dict[str, Any]]:
    """
    Extract JOIN information.

    Example:

        JOIN children c
        ON c.employee_id = e.id

    returns information about:
        - joined table
        - alias
        - join type
        - ON relationship
    """

    alias_map = build_alias_map(expression)

    joins = []

    for join in expression.find_all(exp.Join):

        joined_table = join.this

        table_name = None
        alias = None

        if isinstance(joined_table, exp.Table):
            table_name = joined_table.name
            alias = joined_table.alias or None

        join_type = (
            join.args.get("kind")
            or "INNER"
        )

        if isinstance(join_type, str):
            join_type = join_type.upper()

        on_expression = join.args.get("on")

        relationships = []

        if on_expression:

            conditions = flatten_and_conditions(
                on_expression
            )

            for condition in conditions:

                relationship = extract_join_condition(
                    condition,
                    alias_map
                )

                if relationship:
                    relationships.append(
                        relationship
                    )
                else:
                    relationships.append({
                        "type": "UNSUPPORTED",
                        "raw": condition.sql()
                    })

        joins.append({
            "table": table_name,
            "alias": alias,
            "type": join_type,
            "conditions": relationships
        })

    return joins


def extract_sql_info(
    expression: exp.Expression
) -> Dict[str, Any]:
    """
    Main extraction function.

    This converts the SQLGlot AST into clean JSON-friendly data
    for the Node.js security middleware.
    """

    return {
        "statementType": get_statement_type(
            expression
        ),

        "normalizedSql": normalize_sql(
            expression
        ),

        "tables": extract_tables(
            expression
        ),

        "columns": extract_columns(
            expression
        ),

        "filters": extract_filters(
            expression
        ),

        "joins": extract_joins(
            expression
        )
    }


# ---------------------------------------------------------
# Manual testing
# ---------------------------------------------------------

if __name__ == "__main__":

    from inspector import (
        parse_sql,
        SQLInspectorError
    )

    test_sql = """
    SELECT
        e.name,
        c.name
    FROM employees e
    JOIN children c
        ON c.employee_id = e.id
    WHERE e.tenant_id = 101
      AND e.department_id = 1;
    """

    try:

        expression = parse_sql(
            test_sql
        )

        result = extract_sql_info(
            expression
        )

        import json

        print("\n==============================")
        print("SQL EXTRACTION RESULT")
        print("==============================\n")

        print(
            json.dumps(
                result,
                indent=2,
                default=str
            )
        )

    except SQLInspectorError as error:

        print("\nSQL EXTRACTION FAILED")
        print(error)