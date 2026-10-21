"""Extract structural metadata from the supplied schema-only MySQL dump."""
import hashlib
import json
import re
from pathlib import Path

SOURCE = Path(r"c:\Users\Bosilu\Documents\dumps\Dump20261021.sql")
OUT = Path(__file__).parent


def inspect():
    raw = SOURCE.read_bytes()
    text = raw.decode("utf-8-sig")
    blocks = re.findall(r"CREATE TABLE `([^`]+)` \((.*?)\) ENGINE=([^\r\n]*);", text, re.S)
    tables = {}
    for name, body, options in blocks:
        columns = []
        for line in body.splitlines():
            match = re.match(r"\s*`([^`]+)` (.*?)(?:,)?$", line)
            if match:
                columns.append({"name": match[1], "definition": match[2]})
        comment = re.search(r"COMMENT='(.*?)'", options)
        tables[name] = {
            "comment": comment[1] if comment else "",
            "columns": columns,
            "constraints": [line.strip().rstrip(",") for line in body.splitlines() if line.strip() and not line.lstrip().startswith("`")],
            "foreign_keys": [
                {"name": m[1], "columns": re.findall(r"`([^`]+)`", m[2]), "target": m[3], "target_columns": re.findall(r"`([^`]+)`", m[4])}
                for m in re.finditer(r"CONSTRAINT `([^`]+)` FOREIGN KEY \((.*?)\) REFERENCES `([^`]+)` \((.*?)\)", body)
            ],
        }
    inventory = {
        "source": str(SOURCE), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw),
        "table_count": len(tables), "column_count": sum(len(t["columns"]) for t in tables.values()),
        "foreign_key_count": sum(len(t["foreign_keys"]) for t in tables.values()),
        "insert_statement_count": len(re.findall(r"^INSERT INTO", text, re.M)),
        "tables": tables,
    }
    assert len(re.findall(r"^CREATE TABLE", text, re.M)) == len(tables)
    OUT.joinpath("schema-inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in inventory.items() if k != "tables"}, indent=2))
    for name, t in tables.items():
        print(f"\n{name}: {t['comment']}")
        print("  " + "; ".join(c["name"] + " " + c["definition"] for c in t["columns"]))
        for fk in t["foreign_keys"]:
            print("  FK " + ",".join(fk["columns"]) + " -> " + fk["target"] + "(" + ",".join(fk["target_columns"]) + ")")


if __name__ == "__main__":
    inspect()
