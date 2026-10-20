"""Bounded tenant repair. Unsupported SQL always produces a non-executable result.

Only a single SELECT over registered physical tables is currently supported.
The verifier reparses serialized SQL and proves mandatory conjuncts per alias;
it does not trust the rewriter's change log or flat inspector filter summaries.
"""

import json
import re
from pathlib import Path

from sqlglot import exp
from inspector import parse_sql, SQLInspectorError

REGISTRY = json.loads(Path(__file__).with_name("tenant_registry.json").read_text())


class IsolationError(Exception):
    def __init__(self, code, message, status="CANNOT_REPAIR"):
        super().__init__(message)
        self.code, self.status = code, status


def tenant_value(value):
    # Do not round large BIGINT identifiers through floating point or accept SQL.
    text = str(value)
    if isinstance(value, bool) or not re.fullmatch(r"[1-9][0-9]{0,18}", text):
        raise IsolationError("INVALID_TENANT_CONTEXT", "A positive integer tenantId is required.", "BLOCKED")
    if int(text) > 9223372036854775807:
        raise IsolationError("INVALID_TENANT_CONTEXT", "tenantId exceeds the supported BIGINT range.", "BLOCKED")
    return text


def unwrap(node):
    while isinstance(node, exp.Paren):
        node = node.this
    return node


def conjuncts(node):
    node = unwrap(node)
    if isinstance(node, exp.And):
        return conjuncts(node.left) + conjuncts(node.right)
    return [node] if node is not None else []


def sources_for(tree):
    if not isinstance(tree, exp.Select) or tree.args.get("with_"):
        raise IsolationError("UNSUPPORTED_QUERY_SHAPE", "Only a single SELECT without CTEs or set operations can currently be verified.")
    if any(node is not tree for node in tree.find_all(exp.Query)):
        raise IsolationError("UNSUPPORTED_QUERY_SHAPE", "Nested queries require a dedicated isolation verifier and are not executed.")
    if any(tree.find_all(exp.Placeholder, exp.Parameter)):
        raise IsolationError("UNBOUND_PARAMETERS", "Submitted SQL must not contain parameters or session variables.")
    if any(tree.find_all(exp.Anonymous)):
        raise IsolationError("UNSUPPORTED_FUNCTION", "Custom or unrecognized SQL functions require an explicit isolation rule.")
    # Nonstandard source modifiers and SELECT INTO are outside this rule set.
    if tree.args.get("into"):
        raise IsolationError("UNSUPPORTED_QUERY_SHAPE", "SELECT INTO is not supported.")
    from_clause = tree.args.get("from_")
    if not from_clause or not isinstance(from_clause.this, exp.Table):
        raise IsolationError("UNKNOWN_SOURCE", "The query must read registered physical tables.")
    entries = [(from_clause.this, None)]
    for join in tree.args.get("joins") or []:
        side, kind = str(join.side).upper(), str(join.kind).upper()
        if side not in ("", "LEFT") or kind not in ("", "INNER", "CROSS", "OUTER"):
            raise IsolationError("UNSUPPORTED_JOIN", "Only inner, cross and left joins are supported.")
        if join.args.get("using") or join.args.get("method") or not isinstance(join.this, exp.Table):
            raise IsolationError("UNSUPPORTED_JOIN", "NATURAL, USING and derived-source joins cannot currently be repaired.")
        if side == "LEFT" and not join.args.get("on"):
            raise IsolationError("UNSUPPORTED_JOIN", "A left join must have an explicit ON condition.")
        entries.append((join.this, join if side == "LEFT" else None))
    sources = []
    aliases = set()
    for table, guard_join in entries:
        if any(value for key, value in table.args.items() if key not in ("this", "alias")):
            raise IsolationError("UNSUPPORTED_SOURCE", "Qualified databases and table modifiers require explicit ownership configuration.")
        if not isinstance(table.this, exp.Identifier):
            raise IsolationError("UNKNOWN_SOURCE", "Table functions are not registered tenant sources.")
        name, alias = table.name.lower(), table.alias_or_name
        if name not in REGISTRY:
            raise IsolationError("UNKNOWN_TENANT_OWNERSHIP", f"No trusted tenant ownership rule exists for '{name}'.")
        if alias.lower() in aliases or (table.args.get("alias") and table.args["alias"].args.get("columns")):
            raise IsolationError("AMBIGUOUS_SOURCE", "Duplicate aliases or table column aliases are not supported.")
        aliases.add(alias.lower())
        sources.append({"table": name, "alias": alias, "column": REGISTRY[name], "join": guard_join})
    if len(list(tree.find_all(exp.Table))) != len(sources):
        raise IsolationError("UNSUPPORTED_QUERY_SHAPE", "Not every physical source could be resolved.")
    return sources


def resolve_column(column, sources):
    if not isinstance(column, exp.Column):
        return None
    if column.table:
        return next((s for s in sources if s["alias"].lower() == column.table.lower()), None)
    if len(sources) == 1:
        return sources[0]
    if any(s["column"].lower() == column.name.lower() for s in sources):
        raise IsolationError("AMBIGUOUS_TENANT_COLUMN", "Qualify tenant ownership columns with their table aliases.")
    return None


def tenant_column(column, sources):
    source = resolve_column(column, sources)
    return source if source and column.name.lower() == source["column"].lower() else None


def literal_equality(node, sources):
    node = unwrap(node)
    if not isinstance(node, exp.EQ):
        return None
    for column, value in ((node.left, node.right), (node.right, node.left)):
        source = tenant_column(column, sources)
        if source and isinstance(unwrap(value), exp.Literal):
            return source, unwrap(value)
    return None


def predicate_for(tree, source):
    if source["join"] is not None:
        return source["join"].args.get("on")
    where = tree.args.get("where")
    return where.this if where else None


def has_guard(tree, source, sources, expected):
    for term in conjuncts(predicate_for(tree, source)):
        match = literal_equality(term, sources)
        if match and match[0] is source and str(match[1].this) == expected:
            return True
    return False


def filter_predicates(tree):
    where = tree.args.get("where")
    return ([where.this] if where else []) + [j.args["on"] for j in tree.args.get("joins") or [] if j.args.get("on")]


def validate_rules(rules, sources, expected):
    referenced_tables = {source["table"] for source in sources}
    for rule in rules:
        table = str(rule.get("table", "")).lower()
        column = str(rule.get("column") or rule.get("field") or "").lower()
        if not table or not column or "value" not in rule or rule["value"] is None or "valueFrom" in rule:
            raise IsolationError("INVALID_POLICY", "Every row rule needs a table, column and resolved value.", "BLOCKED")
        if table not in REGISTRY:
            # A policy may authorize more tables than this statement reads.
            # Unknown ownership is an execution concern only for actual sources;
            # sources_for still refuses every unregistered referenced table.
            if table not in referenced_tables:
                continue
            raise IsolationError("UNKNOWN_TENANT_OWNERSHIP", f"No ownership rule exists for policy table '{table}'.", "BLOCKED")
        if column == REGISTRY[table]:
            if str(rule.get("operator", "=")).upper() != "=" or str(rule["value"]) != expected:
                raise IsolationError("POLICY_USER_TENANT_MISMATCH", "Tenant policy conflicts with the supplied authenticated tenant.", "BLOCKED")


def verify_row_rules(tree, sources, rules):
    operators = {"=": exp.EQ, "!=": exp.NEQ, "<>": exp.NEQ, ">": exp.GT, ">=": exp.GTE, "<": exp.LT, "<=": exp.LTE}
    for rule in rules:
        table = str(rule["table"]).lower()
        column = str(rule.get("column") or rule.get("field")).lower()
        applicable_sources = [source for source in sources if source["table"] == table]
        if not applicable_sources:
            continue
        if column == REGISTRY[table]:
            continue
        operator = operators.get(str(rule.get("operator", "=")).upper())
        for source in applicable_sources:
            # WHERE is restrictive for all rows. For a nullable joined source,
            # its own ON can also restrict the rows it contributes.
            where = tree.args.get("where")
            terms = conjuncts(where.this if where else None)
            if source["join"] is not None:
                terms += conjuncts(source["join"].args.get("on"))
            found = False
            for term in terms:
                term = unwrap(term)
                if operator and isinstance(term, operator) and isinstance(term.left, exp.Column) and isinstance(term.right, exp.Literal):
                    if resolve_column(term.left, sources) is source and term.left.name.lower() == column and str(term.right.this) == str(rule["value"]):
                        found = True
            if not found:
                raise IsolationError("ROW_FILTER_MISMATCH", f"Required filter for {source['alias']}.{column} is missing or cannot be verified.", "BLOCKED")


def verify_isolation(sql, dialect, expected, rules):
    """Fresh parse and positive guard proof; never uses rewrite metadata."""
    tree = parse_sql(sql, dialect)
    sources = sources_for(tree)
    validate_rules(rules, sources, expected)
    for source in sources:
        if not has_guard(tree, source, sources, expected):
            raise IsolationError("UNVERIFIED_TENANT_SOURCE", f"No mandatory tenant guard was verified for alias '{source['alias']}'.")
    verify_row_rules(tree, sources, rules)
    return tree, sources


def isolate_sql(sql, tenant_id, rules=None, dialect="mysql", repair=True):
    rules = rules or []
    result = {"status": "CANNOT_REPAIR", "applied": False, "method": "DETERMINISTIC_AST", "originalSql": sql,
              "finalSql": None, "changes": [], "findings": [], "finalVerification": "FAIL"}
    try:
        if dialect not in ("mysql", "sqlite"):
            raise IsolationError("UNSUPPORTED_DIALECT", "Only MySQL and SQLite are supported by this integration.")
        expected = tenant_value(tenant_id)
        tree = parse_sql(sql, dialect)
        sources = sources_for(tree)
        validate_rules(rules, sources, expected)
        for clause_name in ("having", "qualify"):
            clause = tree.args.get(clause_name)
            if clause and any(tenant_column(column, sources) for column in clause.find_all(exp.Column)):
                raise IsolationError("UNSUPPORTED_TENANT_EXPRESSION", "Tenant ownership conditions in HAVING or QUALIFY require a separate repair rule.")
        # Inspect Boolean context before changing anything. Only standalone
        # column/literal tenant equalities can have their values replaced.
        for predicate in filter_predicates(tree):
            mandatory = conjuncts(predicate)
            for node in predicate.walk():
                if not isinstance(node, exp.Column) or not tenant_column(node, sources):
                    continue
                parent = node.parent
                match = literal_equality(parent, sources)
                if match:
                    source, value = match
                    ancestor = parent
                    while ancestor is not predicate and ancestor.parent is not None:
                        ancestor = ancestor.parent
                        if not isinstance(ancestor, (exp.And, exp.Or, exp.Paren)):
                            raise IsolationError("AMBIGUOUS_TENANT_EXPRESSION", "Negated or computed tenant conditions cannot safely be repaired.")
                    if str(value.this) != expected:
                        if not any(parent is term for term in mandatory):
                            raise IsolationError("AMBIGUOUS_TENANT_EXPRESSION", "A conflicting tenant value inside a Boolean expression cannot safely be replaced.")
                        if not repair:
                            raise IsolationError("WRONG_TENANT", f"Alias '{source['alias']}' uses the wrong tenant.")
                        result["changes"].append({"alias": source["alias"], "table": source["table"], "action": "REPLACE_WRONG_TENANT", "previousValue": value.this})
                        value.replace(exp.Literal.number(expected))
                elif isinstance(parent, exp.EQ) and tenant_column(parent.left, sources) and tenant_column(parent.right, sources):
                    continue  # relationship equality; still needs both guards
                else:
                    raise IsolationError("UNSUPPORTED_TENANT_EXPRESSION", "Tenant restrictions must use simple equality; other tenant expressions are not repaired.")
        for source in sources:
            protected = has_guard(tree, source, sources, expected)
            corrected = any(change["alias"] == source["alias"] and change["action"] == "REPLACE_WRONG_TENANT" for change in result["changes"])
            result["findings"].append({"scopeId": "root", "table": source["table"], "alias": source["alias"],
                                       "column": source["column"], "status": "WRONG_TENANT" if corrected else "VERIFIED" if protected else "MISSING"})
            if not protected:
                if not repair:
                    raise IsolationError("MISSING_TENANT_FILTER", f"Alias '{source['alias']}' has no mandatory tenant guard.")
                guard = exp.EQ(this=exp.column(source["column"], table=source["alias"]), expression=exp.Literal.number(expected))
                old = predicate_for(tree, source)
                combined = exp.and_(old.copy(), guard) if old is not None else guard
                if source["join"] is not None:
                    source["join"].set("on", combined)
                else:
                    tree.set("where", exp.Where(this=combined))
                result["changes"].append({"alias": source["alias"], "table": source["table"], "action": "ADD_MISSING_TENANT_FILTER",
                                          "placement": "JOIN_ON" if source["join"] is not None else "WHERE"})
        final_sql = tree.sql(dialect=dialect)
        verified_tree, verified_sources = verify_isolation(final_sql, dialect, expected, rules)
        # Every introduced binding has the same trusted value. No caller-owned
        # placeholders are accepted, so serialization order cannot mix values.
        parameters = []
        for predicate in filter_predicates(verified_tree):
            for equality in list(predicate.find_all(exp.EQ)):
                match = literal_equality(equality, verified_sources)
                if match and str(match[1].this) == expected:
                    match[1].replace(exp.Placeholder())
                    parameters.append(expected)
        parameterized_sql = verified_tree.sql(dialect=dialect)
        rebound = parse_sql(parameterized_sql, dialect)
        placeholders = list(rebound.find_all(exp.Placeholder))
        if len(placeholders) != len(parameters):
            raise IsolationError("INVALID_TENANT_BINDINGS", "Tenant parameter binding count could not be verified.")
        for placeholder in placeholders:
            placeholder.replace(exp.Literal.number(expected))
        # Normalize correct quoted numeric tenant literals before comparison.
        literal_tree = parse_sql(final_sql, dialect)
        literal_sources = sources_for(literal_tree)
        for predicate in filter_predicates(literal_tree):
            for equality in predicate.find_all(exp.EQ):
                match = literal_equality(equality, literal_sources)
                if match and str(match[1].this) == expected:
                    match[1].replace(exp.Literal.number(expected))
        if rebound.sql(dialect=dialect) != literal_tree.sql(dialect=dialect):
            raise IsolationError("INVALID_TENANT_BINDINGS", "Bound SQL does not match the verified query.")
        result.update(status="REPAIRED" if result["changes"] else "UNCHANGED_VERIFIED", applied=bool(result["changes"]),
                      finalSql=final_sql, parameterizedSql=parameterized_sql, parameters=parameters,
                      finalVerification="PASS", reasonCode=None,
                      message="Tenant isolation repaired and independently verified." if result["changes"] else "Tenant isolation verified for every table alias.",
                      rowFiltersVerified=True)
    except IsolationError as error:
        result.update(status=error.status, reasonCode=error.code, message=str(error), applied=False, changes=[])
    except SQLInspectorError as error:
        result.update(reasonCode="SQL_PARSE_FAILED", message=str(error))
    return result
