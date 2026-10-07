"""
Build the independent intent benchmark from the Spider dev set (Stage 5).

Spider (Yu et al., 2018, "Spider: A Large-Scale Human-Labeled Dataset for
Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task", EMNLP;
CC BY-SA 4.0) pairs natural-language questions written by its annotators with
gold SQL. The questions were not written for this component, which is the
point: every earlier intent test set was written by the component's author.

Labels are derived from the GOLD SQL by the fixed rules in `derive_labels`,
not from the question text and not from the classifier. The rules were written
and this file frozen before the classifier was run on any Spider question.
Where the SQL cannot decide between two labels (a grouped count could be shown
as a table or a chart) both are accepted, and the case records which rule
decided it, so the leniency is visible.

Split: the 20 databases are shuffled with a fixed seed and dealt into DEV and
TEST by question count, so the paraphrase pairs Spider has for most queries
never cross the split. DEV may be used to change the classifier; TEST is
reported once with the frozen code.

Source copy: `Dilina/NL TO SQL prototype/predictions_detailed.json` on branch
`dilina-nl-to-sql-prototype-stage-7-database-probing` (Member 1's evaluation of
the 1,032 Spider dev questions). Only db_id, difficulty, question and gold SQL
are kept.

Run:  python benchmark_data/prepare_spider_intent.py <path to predictions_detailed.json>
"""

import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "spider_dev_intent.json"
SEED = 2026

_AGG = re.compile(r"\b(count|sum|avg|max|min)\s*\(")
_SET_OP = re.compile(r"\b(union|intersect|except)\b")


def _strip_subqueries(sql: str) -> str:
    """Replace every parenthesised SELECT with SUBQ, innermost first."""
    prev = None
    while prev != sql:
        prev = sql
        sql = re.sub(r"\(\s*select\b[^()]*\)", " SUBQ ", sql)
        # A subquery may itself contain function parentheses: collapse those
        # inside a select-paren by repeating until stable.
        sql = re.sub(r"\(\s*select\b([^()]*\([^()]*\))+[^()]*\)", " SUBQ ", sql)
    return sql


def _split_select_list(select_list: str) -> list:
    items, depth, cur = [], 0, ""
    for ch in select_list:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        items.append(cur.strip())
    return items


def sql_features(gold_sql: str) -> dict:
    sql = re.sub(r"'[^']*'|\"[^\"]*\"", "'lit'", gold_sql.lower())
    sql = re.sub(r"\s+", " ", sql).strip().rstrip(";")
    top = _strip_subqueries(sql)
    m = re.match(r"select (distinct )?(.*?) from ", top)
    select_items = _split_select_list(m.group(2)) if m else []
    agg_items = [s for s in select_items if _AGG.search(s)]
    limit = re.search(r"\blimit (\d+)", top)
    where = top.split(" where ", 1)[1] if " where " in top else ""
    return {
        "set_op": bool(_SET_OP.search(top)),
        "n_select": len(select_items),
        "n_agg": len(agg_items),
        "only_minmax": bool(agg_items) and all(re.match(r"(max|min)\s*\(", s) for s in agg_items),
        "count_per_group": any(re.match(r"count\s*\(", s) for s in agg_items),
        "group_by": " group by " in top,
        "having": " having " in top,
        "order_by": " order by " in top,
        "limit": int(limit.group(1)) if limit else 0,
        "where_equality": bool(re.search(r"= 'lit'", where)),
    }


def derive_labels(gold_sql: str) -> dict:
    """
    Acceptable response shapes and analytical intents implied by the gold SQL.

    Rules, in order (the first that applies decides):
      SET_OP      UNION / INTERSECT / EXCEPT at top level -> a list of rows
      LIMIT_1     ORDER BY ... LIMIT 1 -> one record (which X has the most)
      GROUPED     GROUP BY -> one value per group (a table or a chart); with
                  no aggregate selected (HAVING as a filter) -> a list of rows
      SCALAR      only aggregates, no GROUP BY -> one figure (or a few)
      MIXED_AGG   aggregates beside plain columns, no GROUP BY -> one row
      TOP_N       ORDER BY ... LIMIT n > 1 -> a ranked list
      ORDERED     ORDER BY, no LIMIT -> a sorted list
      LOOKUP      plain SELECT -> rows; when it selects one column filtered by
                  equality to a literal it may well be one value, so a single
                  answer is accepted too
    SHORT_SUMMARY and MIXED_SUMMARY are never acceptable: a Spider question
    asks for data, never for prose or a report.
    """
    f = sql_features(gold_sql)
    single, table, chart = "SINGLE_ANSWER", "TABLE_CONTENT", "CHART"
    if f["set_op"]:
        rule, shape, intent = "SET_OP", [table], ["DETAIL_LOOKUP"]
    elif f["limit"] == 1:
        rule = "LIMIT_1"
        shape = [single] if f["n_select"] <= 2 else [single, table]
        intent = ["RANKING"]
    elif f["group_by"]:
        rule, shape = "GROUPED", [table, chart]
        if f["n_agg"] == 0:
            # GROUP BY ... HAVING used only to filter: the result is a list of
            # names with no measure, which has nothing to chart.
            shape = [table]
            intent = ["DETAIL_LOOKUP", "COMPARISON"]
        elif f["count_per_group"]:
            intent = ["COMPARISON", "DISTRIBUTION", "PROPORTION"]
        else:
            intent = ["COMPARISON"]
        if f["order_by"] and f["limit"] > 1:
            intent.append("RANKING")
    elif f["n_select"] and f["n_agg"] == f["n_select"]:
        rule = "SCALAR"
        shape = [single] if f["n_agg"] == 1 else [single, table]
        intent = ["KPI_SINGLE_VALUE"] + (["RANKING"] if f["only_minmax"] else [])
    elif f["n_agg"]:
        rule, shape, intent = "MIXED_AGG", [single, table], ["KPI_SINGLE_VALUE", "RANKING"]
    elif f["order_by"] and f["limit"] > 1:
        rule, shape, intent = "TOP_N", [table, chart], ["RANKING"]
    elif f["order_by"]:
        rule, shape, intent = "ORDERED", [table], ["DETAIL_LOOKUP", "RANKING"]
    else:
        rule, intent = "LOOKUP", ["DETAIL_LOOKUP"]
        shape = [table, single] if (f["n_select"] == 1 and f["where_equality"]) else [table]
    return {"rule": rule, "shape": shape, "intent": intent,
            "rows": "ONE" if shape == [single] else ("MANY" if single not in shape else "EITHER")}


def split_databases(questions: list) -> dict:
    counts = {}
    for q in questions:
        counts[q["db_id"]] = counts.get(q["db_id"], 0) + 1
    dbs = sorted(counts)
    random.Random(SEED).shuffle(dbs)
    split, totals = {}, {"DEV": 0, "TEST": 0}
    for db in dbs:
        side = "DEV" if totals["DEV"] <= totals["TEST"] else "TEST"
        split[db] = side
        totals[side] += counts[db]
    return split


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if src is None or not src.exists():
        print(__doc__)
        return 1
    raw = json.loads(src.read_text(encoding="utf-8"))
    split = split_databases(raw)
    cases = []
    for item in raw:
        labels = derive_labels(item["gold_sql"])
        cases.append({"id": f"SP{item['index']:04d}", "split": split[item["db_id"]],
                      "db_id": item["db_id"], "difficulty": item["difficulty"],
                      "question": item["question"], "gold_sql": item["gold_sql"], **labels})
    OUT.write_text(json.dumps({
        "source": "Spider dev set (Yu et al., 2018), CC BY-SA 4.0; copied from Member 1's "
                  "predictions_detailed.json (branch dilina-nl-to-sql-prototype-stage-7-"
                  "database-probing). Labels derived from gold SQL by "
                  "prepare_spider_intent.derive_labels, frozen before the classifier was run.",
        "seed": SEED, "split_by_database": split, "cases": cases}, indent=1), encoding="utf-8")
    from collections import Counter
    print(f"Wrote {OUT.name}: {len(cases)} questions")
    print("split:", Counter(c["split"] for c in cases))
    print("rules:", Counter(c["rule"] for c in cases))
    print("rows:", Counter(c["rows"] for c in cases))
    return 0


if __name__ == "__main__":
    sys.exit(main())
