"""
Regression tests for the Member 2 -> Component 4 input boundary.

The payloads here are copied from the shape `query-executor.js` + `pii-masker.js`
actually emit (mysql2 with `dateStrings: true`, DECIMAL as string, rows as
arrays). Runnable with plain `python test_input_adapter.py` or under pytest.
"""

import sys
from datetime import date, datetime
from decimal import Decimal

import pipeline
from input_adapter import (
    FORMAT_EMPTY,
    FORMAT_MEMBER2_COLUMNAR,
    FORMAT_ROW_DICTS,
    InputFormatError,
    adapt_result,
)

_FAILURES = []


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def _member2_monthly(n=24, truncated=False):
    """A monthly SUM result exactly as Member 2's /api/query returns it."""
    rows = []
    for t in range(n):
        year, month = 2024 + t // 12, t % 12 + 1
        rows.append([f"{year}-{month:02d}-01", f"{3500 + 140 * t + (t % 3) * 55:.2f}"])
    return {
        "statementType": "SELECT",
        "columns": [
            {"name": "month", "sourceTable": None, "sourceColumn": None},
            {"name": "total_amount", "sourceTable": None, "sourceColumn": None},
        ],
        "rows": rows,
        "rowCount": n + (5 if truncated else 0),
        "truncated": truncated,
        "elapsedMs": 3.1,
        "masking": {"mode": "partial", "columns": [], "maskedCells": 0},
    }


def test_columnar_conversion():
    print("\n[1] Member 2 columnar result -> row dicts")
    adapted = adapt_result(_member2_monthly())
    check(adapted.source_format == FORMAT_MEMBER2_COLUMNAR, "detected as Member 2 columnar")
    check(adapted.columns == ["month", "total_amount"], "column order preserved")
    check(len(adapted.rows) == 24 and adapted.rows_received == 24, "all rows converted")
    check(adapted.rows[0] == {"month": "2024-01-01", "total_amount": "3500.00"},
          "values passed through in wire form")
    check(not adapted.truncated and not adapted.warnings, "clean input raises no warnings")


def test_duplicate_columns():
    print("\n[2] Duplicate column names (rowsAsArray keeps a.id and b.id)")
    payload = {
        "columns": [{"name": "id"}, {"name": "id"}, {"name": "id_2"}, {"name": "amount"}],
        "rows": [[1, 7, "x", "10.00"], [2, 8, "y", "12.50"]],
        "rowCount": 2,
    }
    adapted = adapt_result(payload)
    check(len(set(adapted.columns)) == 4, "every column survives the dict conversion")
    check(adapted.rows[0]["id"] == 1, "first duplicate keeps its name")
    renamed = [k for k, v in adapted.renamed_columns.items() if v == "id"]
    check(len(renamed) == 1 and adapted.rows[0][renamed[0]] == 7,
          "second duplicate renamed and keeps its own value")
    check(adapted.rows[1]["id_2"] == "y", "a genuine 'id_2' column is not overwritten")
    check("DUPLICATE_COLUMN_NAMES_RENAMED" in adapted.warnings, "rename is reported")


def test_masking_and_truncation():
    print("\n[3] Masking metadata and truncation")
    payload = {
        "columns": [{"name": "full_name"}, {"name": "email"}, {"name": "salary"}],
        "rows": [["N**** P*****", "n****@example.com", "85000.00"]],
        "rowCount": 1,
        "masking": {"mode": "partial", "maskedCells": 2, "columns": [
            {"name": "full_name", "piiType": "PERSON", "strategy": "partial"},
            {"name": "email", "piiType": "EMAIL", "strategy": "partial"},
        ]},
    }
    adapted = adapt_result(payload)
    check(adapted.masked_columns == {"full_name": "PERSON", "email": "EMAIL"},
          "masked columns and their PII types recorded")
    check("MASKED_COLUMNS_PRESENT" in adapted.warnings, "masking is surfaced")

    cut = adapt_result(_member2_monthly(truncated=True))
    check(cut.truncated and "INPUT_TRUNCATED" in cut.warnings,
          "row-cap truncation is flagged, not silently analysed")
    check(cut.row_count == 29 and cut.rows_received == 24, "true count kept beside delivered count")


def test_driver_types_and_legacy():
    print("\n[4] Native driver types and the legacy contract")
    native = adapt_result({
        "columns": ["d", "ts", "amount", "n"],
        "rows": [[date(2024, 3, 1), datetime(2024, 3, 1, 9, 30), Decimal("12.50"), 4]],
    })
    check(native.rows[0] == {"d": "2024-03-01", "ts": "2024-03-01 09:30:00",
                             "amount": "12.50", "n": 4},
          "date/datetime/Decimal normalised to mysql2 wire form")

    legacy = adapt_result([{"invoice_date": "2024-01-01", "amount": 10.0}])
    check(legacy.source_format == FORMAT_ROW_DICTS and len(legacy.rows) == 1,
          "list of dicts still accepted")
    envelope = adapt_result({"raw_results": [{"a": 1}]})
    check(envelope.source_format == FORMAT_ROW_DICTS, "{raw_results: [...]} still accepted")
    check(adapt_result(None).source_format == FORMAT_EMPTY
          and adapt_result([]).source_format == FORMAT_EMPTY, "empty input is not an error")

    for bad, label in ((42, "a scalar"), ({"columns": ["a"], "rows": [{"a": 1}]}, "dict rows in columnar form"),
                       ([["a", 1]], "array rows without columns")):
        try:
            adapt_result(bad)
            check(False, f"rejects {label}")
        except InputFormatError:
            check(True, f"rejects {label}")


def test_pipeline_equivalence():
    print("\n[5] Pipeline gives the same answer for both formats")
    columnar = _member2_monthly()
    as_dicts = [dict(zip(["month", "total_amount"], r)) for r in columnar["rows"]]
    query = "Show my monthly expenses and predict the next 3 months"

    a = pipeline.run(query, rows=columnar, use_llm=False, enable_cache=False)
    b = pipeline.run(query, rows=as_dicts, use_llm=False, enable_cache=False)

    fa, fb = a["prediction"]["stage_4_forecast"], b["prediction"]["stage_4_forecast"]
    check(a["input"]["source_format"] == FORMAT_MEMBER2_COLUMNAR, "envelope records the input format")
    check(a["result_profile"]["temporal_column"] == "month"
          and a["result_profile"]["measure_columns"] == ["total_amount"],
          "string dates and DECIMAL strings are typed correctly")
    check(fa["generated"] and fa["points"] == fb["points"], "identical forecast from both formats")
    check(a["summary"]["text"] == b["summary"]["text"], "identical summary from both formats")

    print("\n[6] DECIMAL strings render as numbers, not text")
    query = "What is the total amount spent on travel?"
    as_float = pipeline.run(query, rows=[{"total_travel": 48250.5}],
                            use_llm=False, enable_cache=False)["response"]["answer"]
    as_string = pipeline.run(query, rows={"columns": [{"name": "total_travel"}],
                                          "rows": [["48250.50"]], "rowCount": 1},
                             use_llm=False, enable_cache=False)["response"]["answer"]
    check(as_string["value_type"] == "number", "a DECIMAL-string total is typed as a number")
    check(as_string["display_value"] == as_float["display_value"]
          and as_string["label"] == as_float["label"],
          "answer label and display match the float path")


def main() -> int:
    test_columnar_conversion()
    test_duplicate_columns()
    test_masking_and_truncation()
    test_driver_types_and_legacy()
    test_pipeline_equivalence()
    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} check(s) failed:")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
