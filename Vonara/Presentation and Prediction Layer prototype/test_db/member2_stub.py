"""
Stand-in for Member 2's read pipeline, for integration testing only.

Reproduces the OUTPUT CONTRACT of Member 2's `/api/query`
(security_validation_layer_js: query-executor.js -> pii-masker.js), so
Component 4 is exercised against exactly what it will receive:

  - rows as ARRAYS aligned to a `columns` list (mysql2 `rowsAsArray`)
  - DATE/DATETIME as strings (mysql2 `dateStrings: true`)
  - DECIMAL - every SUM/AVG over money - as strings (mysql2 default)
  - `rowCount` / `truncated` from the row cap
  - PII masked with the same partial strategies (n****@x.com, +9477*****67,
    N**** P*****) and reported under `masking.columns`

This is NOT a security layer. Its SELECT check exists only so a typo in a
fixture cannot reach the database as a write; the real AST validation,
tenant rewriting and NER-based classification live in Members 2 and 3. The
queries also run as a SELECT-only MySQL account inside a READ ONLY
transaction, as Member 2's executor does.
"""

import json
import re
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import db_config

MAX_ROWS = 1000
TIMEOUT_MS = 5000
MASK = "*"

_PII_CONFIG_PATH = Path(__file__).resolve().parent / "pii_columns.json"
_READ_ONLY_RE = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


class StubQueryError(RuntimeError):
    pass


def load_pii_schema() -> dict:
    data = json.loads(_PII_CONFIG_PATH.read_text(encoding="utf-8"))
    return data.get(db_config.database_name(), {})


# ==========================================================================
# Execution (query-executor.js)
# ==========================================================================


def _wire(value):
    """Render a PyMySQL value the way mysql2 serialises it to JSON."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, timedelta):
        total = int(value.total_seconds())
        return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def execute(sql: str, conn=None, max_rows: int = MAX_ROWS) -> dict:
    """Run one SELECT read-only and return Member 2's executor result shape."""
    body = sql.strip().rstrip(";")
    if not _READ_ONLY_RE.match(body) or ";" in body:
        raise StubQueryError("Fixture SQL must be a single SELECT/WITH statement.")

    own = conn is None
    conn = conn or db_config.reader_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {int(TIMEOUT_MS)}")
            cur.execute("START TRANSACTION READ ONLY")
            started = time.perf_counter()
            cur.execute(body)
            raw_rows = cur.fetchall()
            elapsed = (time.perf_counter() - started) * 1000.0
            fields = getattr(getattr(cur, "_result", None), "fields", None) or []
            names = [d[0] for d in cur.description or []]
        conn.rollback()
    finally:
        if own:
            conn.close()

    columns = []
    for i, name in enumerate(names):
        field = fields[i] if i < len(fields) else None
        # orgTable/orgName are empty for expressions (SUM(x), DATE_FORMAT(...)).
        org_table = _text(getattr(field, "org_table", "")) if field else ""
        org_name = _text(getattr(field, "org_name", "")) if field else ""
        columns.append({
            "name": name,
            "sourceTable": org_table or None,
            "sourceColumn": org_name or None,
        })

    rows = [[_wire(v) for v in row] for row in raw_rows]
    return {
        "statementType": "SELECT",
        "columns": columns,
        "rows": rows[:max_rows],
        "rowCount": len(rows),
        "truncated": len(rows) > max_rows,
        "elapsedMs": round(elapsed, 1),
    }


def _text(value) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


# ==========================================================================
# Classification + masking (pii-classifier.js / pii-masker.js, declared-PII path)
# ==========================================================================


def classify(result: dict, pii_schema: dict) -> list:
    """Declared-schema classification: a column is PII when its SOURCE column is."""
    out = []
    for col in result["columns"]:
        table, column = col.get("sourceTable"), col.get("sourceColumn")
        declared = (pii_schema.get(table) or {}).get(column) if table and column else None
        pii_type = declared if declared and declared != "NONE" else None
        out.append({"name": col["name"], "piiType": pii_type,
                    "source": "DECLARED" if pii_type else "NONE"})
    return out


def _mask_all(text: str) -> str:
    return MASK * min(max(len(text), 3), 12)


def _mask_digits(text: str, head: int, tail: int) -> str:
    total = sum(ch.isdigit() for ch in text)
    seen, out = 0, []
    for ch in text:
        if not ch.isdigit():
            out.append(ch)
            continue
        seen += 1
        out.append(ch if seen <= head or seen > total - tail else MASK)
    return "".join(out)


def _partial(value: str, pii_type: str):
    if pii_type == "EMAIL":
        at = value.rfind("@")
        return value[0] + MASK * (at - 1) + value[at:] if at >= 1 else None
    if pii_type == "PHONE":
        if sum(ch.isdigit() for ch in value) < 7:
            return None
        return _mask_digits(value, 4 if value.strip().startswith("+") else 3, 2)
    if pii_type == "PERSON":
        return re.sub(r"[^\W\d_][\w'-]*", lambda m: m.group(0)[0] + MASK * (len(m.group(0)) - 1), value)
    return None


def mask_value(value, pii_type: str, mode: str = "partial"):
    if value is None or str(value).strip() == "":
        return value
    text = str(value)
    if mode == "redact":
        return f"[{pii_type}]"
    masked = _partial(text, pii_type)
    return _mask_all(text) if masked is None else masked


def mask(result: dict, classification: list, mode: str = "partial") -> dict:
    plan = [(c["name"], c["piiType"]) for c in classification]
    masked_cells = 0
    rows = []
    for row in result["rows"]:
        new_row = []
        for value, (_, pii_type) in zip(row, plan):
            if pii_type:
                out = mask_value(value, pii_type, mode)
                masked_cells += out != value
                new_row.append(out)
            else:
                new_row.append(value)
        rows.append(new_row)
    return {
        **result,
        "rows": rows,
        "masking": {
            "mode": mode,
            "columns": [{"name": n, "piiType": t, "strategy": mode} for n, t in plan if t],
            "maskedCells": masked_cells,
        },
    }


def query(sql: str, conn=None, mode: str = "partial") -> dict:
    """The full read pipeline: execute -> classify -> mask, JSON round-tripped."""
    result = execute(sql, conn=conn)
    classification = classify(result, load_pii_schema())
    masked = mask(result, classification, mode=mode)
    masked["classification"] = classification
    # Round-trip through JSON so the payload is exactly what crosses HTTP.
    return json.loads(json.dumps(masked))
