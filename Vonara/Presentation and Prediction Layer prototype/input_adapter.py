"""
Input adapter - the boundary between Member 2's security layer and Component 4.

Member 2's read pipeline (validate -> execute read-only -> classify -> mask)
returns a COLUMNAR result, not the list of dicts the rest of this component
works on:

    {
      "statementType": "SELECT",
      "columns": [{"name": "month", "sourceTable": null, "sourceColumn": null},
                  {"name": "total_amount", "sourceTable": "expenses", ...}],
      "rows": [["2024-01-01", "3419.57"], ...],        # arrays, not dicts
      "rowCount": 24, "truncated": false,
      "masking": {"mode": "partial",
                  "columns": [{"name": "email", "piiType": "EMAIL",
                               "strategy": "partial"}],
                  "maskedCells": 12}
    }

Three properties of that payload matter downstream and are handled here, once,
so no other module has to know the wire format:

  1. Rows are arrays because the executor uses `rowsAsArray` to keep duplicate
     column names (`a.id`, `b.id` both arrive as "id"). Converting to dicts
     naively would silently drop one of them, so duplicates are renamed.
  2. mysql2 returns DECIMAL (every SUM/AVG over money) as a string and, with
     `dateStrings`, dates as strings. Values are passed through unchanged -
     `result_profiler` already parses numeric-like and date-like strings - but
     in-process Python drivers hand over Decimal/date objects, which are
     normalised to the same wire representation so both paths profile alike.
  3. `truncated` means the executor cut the result at its row cap. A forecast
     or total computed over a truncated result describes the cap, not the data,
     so the adapter surfaces it as a warning rather than letting it pass unseen.

The legacy list-of-dicts shape (and a `{"raw_results": [...]}` envelope) is
still accepted, so existing callers and the synthetic benchmarks keep working.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

FORMAT_MEMBER2_COLUMNAR = "MEMBER2_COLUMNAR"
FORMAT_ROW_DICTS = "ROW_DICTS"
FORMAT_EMPTY = "EMPTY"


class InputFormatError(ValueError):
    """The payload is not any result shape this component understands."""


@dataclass
class AdaptedInput:
    rows: list = field(default_factory=list)            # list[dict], column order kept
    columns: list = field(default_factory=list)         # final (deduplicated) names
    source_format: str = FORMAT_EMPTY
    row_count: int = 0                                  # rows the query produced
    rows_received: int = 0                              # rows actually delivered
    truncated: bool = False
    masked_columns: dict = field(default_factory=dict)  # name -> piiType
    renamed_columns: dict = field(default_factory=dict) # new name -> original name
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        """Envelope section: what arrived, without repeating the rows."""
        return {
            "source_format": self.source_format,
            "columns": self.columns,
            "row_count": self.row_count,
            "rows_received": self.rows_received,
            "truncated": self.truncated,
            "masked_columns": self.masked_columns,
            "renamed_columns": self.renamed_columns,
            "warnings": self.warnings,
        }


def _normalise_value(value):
    """Map driver-native types onto the representation mysql2 puts on the wire."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", errors="replace")
    return value


def _dedupe(names: list) -> tuple:
    """
    Make column names unique, keeping the first occurrence unchanged.

    `SELECT a.id, b.id` arrives as ["id", "id"]; the second becomes "id_2".
    Every name that appears in the result is reserved up front, so a rename
    can never take the name of a real column further along ("id", "id",
    "id_2" yields "id", "id_3", "id_2"). Returns (unique_names, {renamed: original}).
    """
    cleaned = [str(raw) if raw not in (None, "") else "column" for raw in names]
    taken = set(cleaned)
    used = set()
    out, renamed = [], {}
    for name in cleaned:
        if name not in used:
            used.add(name)
            out.append(name)
            continue
        suffix = 2
        while f"{name}_{suffix}" in taken or f"{name}_{suffix}" in used:
            suffix += 1
        candidate = f"{name}_{suffix}"
        used.add(candidate)
        out.append(candidate)
        renamed[candidate] = name
    return out, renamed


def _adapt_columnar(payload: dict) -> AdaptedInput:
    columns = payload.get("columns") or []
    raw_rows = payload.get("rows") or []
    names = [c.get("name") if isinstance(c, dict) else c for c in columns]

    result = AdaptedInput(source_format=FORMAT_MEMBER2_COLUMNAR)
    result.columns, result.renamed_columns = _dedupe(names)
    if result.renamed_columns:
        result.warnings.append("DUPLICATE_COLUMN_NAMES_RENAMED")

    width = len(result.columns)
    ragged = False
    for raw in raw_rows:
        if not isinstance(raw, (list, tuple)):
            raise InputFormatError(
                "Columnar result rows must be arrays aligned to `columns`."
            )
        if len(raw) != width:
            ragged = True
        result.rows.append(
            {name: _normalise_value(raw[i]) if i < len(raw) else None
             for i, name in enumerate(result.columns)}
        )
    if ragged:
        result.warnings.append("RAGGED_ROWS")

    result.rows_received = len(result.rows)
    result.row_count = int(payload.get("rowCount", result.rows_received) or 0)
    result.truncated = bool(payload.get("truncated")) or result.row_count > result.rows_received
    if result.truncated:
        result.warnings.append("INPUT_TRUNCATED")

    # A masked column keeps its (possibly renamed) position, so map by index
    # rather than by name when the names were deduplicated.
    masking = payload.get("masking") or {}
    for entry in masking.get("columns") or []:
        original = entry.get("name")
        pii_type = entry.get("piiType") or "UNKNOWN"
        for final, orig in zip(result.columns, names):
            if orig == original and final not in result.masked_columns:
                result.masked_columns[final] = pii_type
    if result.masked_columns:
        result.warnings.append("MASKED_COLUMNS_PRESENT")
    return result


def _adapt_row_dicts(rows: list) -> AdaptedInput:
    result = AdaptedInput(source_format=FORMAT_ROW_DICTS if rows else FORMAT_EMPTY)
    for row in rows:
        if not isinstance(row, dict):
            raise InputFormatError("Row-oriented results must be a list of dicts.")
        result.rows.append({k: _normalise_value(v) for k, v in row.items()})
        for key in row:
            if key not in result.columns:
                result.columns.append(key)
    result.rows_received = result.row_count = len(result.rows)
    return result


def adapt_result(payload) -> AdaptedInput:
    """
    Normalise any supported result payload into row dicts plus metadata.

    Accepts:
      - Member 2's columnar result (`columns` + array `rows` [+ `masking`])
      - a plain list of row dicts (legacy contract, synthetic benchmarks)
      - `{"raw_results": [...]}` (legacy REST envelope)
      - None / empty list (empty result set)
    """
    if payload is None:
        return AdaptedInput()
    if isinstance(payload, list):
        return _adapt_row_dicts(payload)
    if isinstance(payload, dict):
        if "columns" in payload and "rows" in payload:
            return _adapt_columnar(payload)
        if "raw_results" in payload:
            return _adapt_row_dicts(payload.get("raw_results") or [])
    raise InputFormatError(
        "Unsupported result payload: expected Member 2's {columns, rows} result "
        "or a list of row dicts."
    )
