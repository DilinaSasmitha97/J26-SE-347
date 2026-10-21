"""Validate proposals without modifying runtime config or connecting to a DB.

Run with the existing SQLGlot service virtualenv Python.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
APP = ROOT.parents[1]
sys.path.insert(0, str(APP / "sqlglot-service"))
import rewriter


def read(name):
    return json.loads(ROOT.joinpath(name).read_text(encoding="utf-8"))


inventory = read("schema-inventory.json")
tables = inventory["tables"]
schema = read("schema-allowlist.entry.json")["enterprise_hrms_alpha"]
assert len(tables) == 68 and sum(len(t["columns"]) for t in tables.values()) == 601
assert sum(len(t["foreign_keys"]) for t in tables.values()) == 138
assert set(schema) == set(tables)
assert all(schema[n] == [c["name"] for c in t["columns"]] for n, t in tables.items())
all_columns = {f"{n}.{c['name']}" for n, t in tables.items() for c in t["columns"]}
enum_domains = {f"{n}.{c['name']}": re.findall(r"'([^']*)'", re.search(r"enum\((.*?)\)", c["definition"])[1]) for n, t in tables.items() for c in t["columns"] if c["definition"].startswith("enum(")}
for path in ROOT.glob("*.json"):
    read(path.name)
variants = ["01-employee", "02-manager", "03-admin"]
summary = {}
for key in variants:
    policy, rules, user = (read(key + suffix + ".json") for suffix in (".policy", ".rules", ".user"))
    allowed = set(policy["allowedTables"])
    assert allowed <= set(tables)
    assert len(allowed) == len(policy["allowedTables"])
    assert policy["allowedOperations"] == ["SELECT"]
    assert policy["role"] == user["role"]
    assert set(policy["deniedColumns"]) <= all_columns
    assert all(c.split(".")[0] in allowed for c in policy["deniedColumns"])
    for rule in policy["rowRules"]:
        assert rule["table"] in allowed
        assert f"{rule['table']}.{rule['field']}" in all_columns
        assert rule["operator"] == "="
        assert ("valueFrom" in rule) != ("value" in rule)
        if "valueFrom" in rule:
            assert rule["valueFrom"] in user
        assert f"{rule['table']}.{rule['field']}" not in policy["deniedColumns"]
    assert rules["role"] == policy["role"]
    assert rules["context"] == {k: v for k, v in user.items() if k not in ("userId", "role")}
    assert len(rules["rules"]) == 9
    assert all(isinstance(r, str) and r.strip() for r in rules["rules"])
    assert ROOT.joinpath(key + ".rules.json").stat().st_size < 3000
    derived = {n for n, t in tables.items() if "class=TENANT_DERIVED;" in t["comment"]}
    assert not allowed.intersection(derived)
    summary[key] = {"allowed_tables": len(allowed), "denied_tables": 68-len(allowed), "denied_columns": len(policy["deniedColumns"]), "row_rules": len(policy["rowRules"])}

node = subprocess.run(["node", str(ROOT / "validate_node.cjs")], text=True, capture_output=True, check=True)
node_data = json.loads(node.stdout)

# Override only this process's registry to assess proposed direct-table rules.
# No file is changed. Global and inherited sources remain intentionally absent.
runtime_registry = dict(rewriter.REGISTRY)
proposed = {n: "tenant_id" for n in tables if "tenant_id" in schema[n]}
assert len(proposed) == 51
rewriter.REGISTRY = proposed
checks = []


def check(key, name, sql, expected_pass):
    result = rewriter.isolate_sql(sql, 101, node_data["resolved"][key], dialect="mysql", repair=True)
    passed = result["status"] in {"REPAIRED", "UNCHANGED_VERIFIED"}
    assert passed == expected_pass, (name, result)
    checks.append({"variant": key, "name": name, "expected_pass": expected_pass, "status": result["status"], "reason": result.get("reasonCode"), "passed": True})


check("01-employee", "self_guard_with_tenant_repair", "SELECT e.full_name FROM employees e WHERE e.employee_id=1001", True)
check("01-employee", "other_employee_blocked", "SELECT e.full_name FROM employees e WHERE e.tenant_id=101 AND e.employee_id=1002", False)
check("01-employee", "missing_self_guard_blocked", "SELECT e.full_name FROM employees e WHERE e.tenant_id=101", False)
check("01-employee", "optional_self_guard_blocked", "SELECT e.full_name FROM employees e WHERE e.tenant_id=101 AND (e.employee_id=1001 OR 1=1)", False)
check("01-employee", "left_join_guards", "SELECT e.full_name,p.net_pay FROM employees e LEFT JOIN payroll_records p ON p.tenant_id=e.tenant_id AND p.employee_id=e.employee_id AND p.employee_id=1001 WHERE e.employee_id=1001", True)
check("01-employee", "draft_review_blocked", "SELECT r.overall_rating FROM performance_reviews r WHERE r.employee_id=1001 AND r.review_status='DRAFT'", False)
check("01-employee", "confidential_document_blocked", "SELECT d.document_type FROM employee_documents_metadata d WHERE d.employee_id=1001 AND d.is_confidential=1", False)
check("02-manager", "department_guard", "SELECT e.full_name FROM employees e WHERE e.department_id=10", True)
check("02-manager", "other_department_blocked", "SELECT e.full_name FROM employees e WHERE e.department_id=11", False)
check("02-manager", "missing_department_guard_blocked", "SELECT e.full_name FROM employees e", False)
check("02-manager", "missing_finalized_status_blocked", "SELECT r.overall_rating FROM performance_reviews r WHERE r.department_id=10", False)
check("02-manager", "project_owner_guard", "SELECT p.project_name FROM projects p WHERE p.owning_department_id=10", True)
check("03-admin", "tenant_root_correct_key", "SELECT t.company_name FROM tenants t", True)
check("03-admin", "recruitment_composite_join", "SELECT c.candidate_source,COUNT(DISTINCT a.application_id) AS applications FROM candidates c JOIN applications a ON a.tenant_id=c.tenant_id AND a.candidate_id=c.candidate_id GROUP BY c.candidate_source", True)
check("03-admin", "inherited_source_unregistered", "SELECT c.amount FROM payroll_components c JOIN payroll_records p ON p.payroll_record_id=c.payroll_record_id", False)
check("03-admin", "shared_source_unsupported", "SELECT c.country_name FROM countries c", False)
rewriter.REGISTRY = runtime_registry

out = {
    "source_sha256": inventory["sha256"], "schema_tables": 68, "schema_columns": 601, "declared_foreign_keys": 138,
    "enum_domains_in_schema": len(enum_domains), "variants": summary,
    "structural_checks": "PASS: JSON parseability, policy table/column identifiers, row-rule fields/claims, compact role/context alignment, nine short rules per file, each under 3 KB, derived tables denied",
    "application_claim_resolution": "PASS: actual resolvePolicyValues helper resolves policies; compact rules context matches all referenced user claims",
    "application_access_checks": node_data["access_checks"], "isolated_direct_ownership_checks": checks,
    "limitations": ["No runtime files changed; isolation checks use a process-local 51-direct-table registry derived from the dump.", "Shared/derived sources remain unsupported, as documented; positive checks are not live end-to-end readiness claims.", "No database connection, SQL execution, LLM generation, NER or masking verification was performed."],
}
ROOT.joinpath("validation-results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"variants": summary, "structural_checks": "PASS", "access_checks": len(node_data["access_checks"]), "isolated_ownership_checks": len(checks)}, indent=2))
