"""
MySQL compatibility for the SQLite test backend (Stage 6).

The fixtures are written in MySQL, the dialect Member 2's executor runs. To run
them unchanged without a MySQL server, this module:

  register(conn)      adds DATE_FORMAT, YEAR, MONTH, DAY, QUARTER, WEEKDAY,
                      DAYOFWEEK and CONCAT with MySQL's semantics
  rewrite(sql)        turns DATE_SUB/DATE_ADD(x, INTERVAL n UNIT), which SQLite
                      cannot parse, into a registered function call
  column_sources()    works out each result column's source table and column
                      from the SQL. MySQL's driver reports these (orgTable /
                      orgName); SQLite's does not, and Member 2's declared-PII
                      classifier depends on them - without this, nothing would
                      be masked and every test would still pass. Like MySQL,
                      only a plain column reference has a source; an expression
                      such as CONCAT(full_name, ...) has none.
  wire(value)         renders a value as mysql2 serialises it: dates as text,
                      DECIMAL results as strings

Test infrastructure only. It is not a SQL translator for production use.
"""

import calendar
import re
from datetime import date, datetime, timedelta

_MONTHS = list(calendar.month_name)[1:]


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value if isinstance(value, datetime) else datetime(value.year, value.month, value.day)
    text = str(value)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:19] if " " in text else text[:10], fmt)
        except ValueError:
            continue
    return None


def _date_format(value, fmt):
    d = _as_date(value)
    if d is None or fmt is None:
        return None
    out, i = [], 0
    while i < len(fmt):
        ch = fmt[i]
        if ch == "%" and i + 1 < len(fmt):
            code = fmt[i + 1]
            out.append({
                "Y": f"{d.year:04d}", "y": f"{d.year % 100:02d}", "m": f"{d.month:02d}",
                "c": str(d.month), "d": f"{d.day:02d}", "e": str(d.day),
                "H": f"{d.hour:02d}", "i": f"{d.minute:02d}", "s": f"{d.second:02d}",
                "M": _MONTHS[d.month - 1], "b": _MONTHS[d.month - 1][:3], "%": "%",
            }.get(code, "%" + code))
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _part(fn):
    def inner(value):
        d = _as_date(value)
        return None if d is None else fn(d)
    return inner


def _concat(*args):
    if any(a is None for a in args):
        return None                      # MySQL: CONCAT with a NULL is NULL
    return "".join(str(int(a)) if isinstance(a, float) and a.is_integer() else str(a)
                   for a in args)


def _shift(value, amount, unit, sign):
    d = _as_date(value)
    if d is None or amount is None:
        return None
    n = int(amount) * sign
    unit = str(unit).upper()
    if unit == "DAY":
        d = d + timedelta(days=n)
    elif unit == "WEEK":
        d = d + timedelta(weeks=n)
    elif unit in ("MONTH", "YEAR"):
        months = n * (12 if unit == "YEAR" else 1)
        y, m = divmod(d.month - 1 + months, 12)
        year, month = d.year + y, m + 1
        d = d.replace(year=year, month=month, day=min(d.day, calendar.monthrange(year, month)[1]))
    else:
        return None
    return d.strftime("%Y-%m-%d")


def register(conn) -> None:
    conn.create_function("DATE_FORMAT", 2, _date_format, deterministic=True)
    conn.create_function("YEAR", 1, _part(lambda d: d.year), deterministic=True)
    conn.create_function("MONTH", 1, _part(lambda d: d.month), deterministic=True)
    conn.create_function("DAY", 1, _part(lambda d: d.day), deterministic=True)
    conn.create_function("QUARTER", 1, _part(lambda d: (d.month - 1) // 3 + 1), deterministic=True)
    conn.create_function("WEEKDAY", 1, _part(lambda d: d.weekday()), deterministic=True)  # Mon=0
    conn.create_function("DAYOFWEEK", 1, _part(lambda d: (d.weekday() + 1) % 7 + 1),
                         deterministic=True)                                         # Sun=1
    conn.create_function("CONCAT", -1, _concat, deterministic=True)
    conn.create_function("MYSQL_DATE_SUB", 3, lambda v, n, u: _shift(v, n, u, -1),
                         deterministic=True)
    conn.create_function("MYSQL_DATE_ADD", 3, lambda v, n, u: _shift(v, n, u, 1),
                         deterministic=True)


def _split_top_level(text: str) -> list:
    parts, depth, cur = [], 0, ""
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def rewrite(sql: str) -> str:
    """DATE_SUB/DATE_ADD(x, INTERVAL n UNIT) -> MYSQL_DATE_SUB/ADD(x, n, 'UNIT')."""
    pattern = re.compile(r"\bDATE_(SUB|ADD)\s*\(", re.IGNORECASE)
    while True:
        m = pattern.search(sql)
        if not m:
            return sql
        start, depth, i = m.end(), 1, m.end()
        while i < len(sql) and depth:
            depth += {"(": 1, ")": -1}.get(sql[i], 0)
            i += 1
        inner = sql[start:i - 1]
        args = _split_top_level(inner)
        iv = re.match(r"\s*INTERVAL\s+(.+?)\s+(DAY|WEEK|MONTH|YEAR)\s*$", args[-1],
                      re.IGNORECASE | re.DOTALL) if len(args) == 2 else None
        if not iv:
            raise ValueError(f"Unsupported DATE_{m.group(1)} form: {sql[m.start():i]}")
        call = (f"MYSQL_DATE_{m.group(1).upper()}({args[0].strip()}, {iv.group(1)}, "
                f"'{iv.group(2).upper()}')")
        sql = sql[:m.start()] + call + sql[i:]


def _table_aliases(sql: str) -> dict:
    """{alias_or_name: table} for the FROM and JOIN clauses (lower case)."""
    aliases = {}
    keywords = {"where", "join", "on", "group", "order", "limit", "inner", "left", "right",
                "outer", "cross", "having", "union", "as"}
    for m in re.finditer(r"\b(?:from|join)\s+([a-z_][\w]*)(?:\s+(?:as\s+)?([a-z_]\w*))?",
                         sql, re.IGNORECASE):
        table = m.group(1).lower()
        alias = (m.group(2) or "").lower()
        aliases[table] = table
        if alias and alias not in keywords:
            aliases[alias] = table
    return aliases


def schema_columns(ddl: str) -> dict:
    """{table: {column, ...}} from CREATE TABLE statements (lower case)."""
    out = {}
    for m in re.finditer(r"create\s+table\s+(\w+)\s*\((.*?)\)\s*;", ddl, re.IGNORECASE | re.DOTALL):
        cols = set()
        for line in m.group(2).splitlines():
            first = line.strip().split(" ")[0].lower()
            if first and first not in ("primary", "index", "key", "unique", "foreign", "constraint"):
                cols.add(first)
        out[m.group(1).lower()] = cols
    return out


def column_sources(sql: str, column_names: list, columns_by_table: dict = None) -> list:
    """
    (sourceTable, sourceColumn) for each result column, or (None, None) for an
    expression - the same information MySQL returns as orgTable / orgName.
    An unqualified column in a join is resolved through `columns_by_table`.
    """
    m = re.match(r"\s*select\s+(?:distinct\s+)?(.*?)\s+from\s", sql, re.IGNORECASE | re.DOTALL)
    if not m or re.search(r"\b(union|intersect|except)\b", sql, re.IGNORECASE):
        return [(None, None)] * len(column_names)
    aliases = _table_aliases(sql)
    tables = list(dict.fromkeys(aliases.values()))
    items = _split_top_level(m.group(1))
    out = []
    for item in items:
        ref = re.match(r"\s*(?:([a-z_]\w*)\.)?([a-z_]\w*)\s*(?:(?:as\s+)?[a-z_]\w*)?\s*$",
                       item, re.IGNORECASE)
        if not ref:
            out.append((None, None))
            continue
        qualifier, column = (ref.group(1) or "").lower(), ref.group(2).lower()
        if qualifier:
            out.append((aliases.get(qualifier), column))
        elif len(tables) == 1:
            out.append((tables[0], column))
        else:
            owners = [t for t in tables if column in (columns_by_table or {}).get(t, ())]
            out.append((owners[0], column) if len(owners) == 1 else (None, column))
    if len(out) != len(column_names):
        return [(None, None)] * len(column_names)    # SELECT * or an unparsed list
    return out


def wire(value):
    """A value as mysql2 serialises it: DECIMAL-like floats become strings."""
    if isinstance(value, float):
        if value.is_integer():
            return f"{value:.2f}"
        rounded = round(value, 2)
        return f"{value:.2f}" if abs(value - rounded) < 1e-9 else f"{value:.6f}"
    return value
