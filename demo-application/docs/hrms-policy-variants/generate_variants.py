"""Build reviewable policy/rule proposals; never edits runtime configuration."""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent
DATA = json.loads(ROOT.joinpath("schema-inventory.json").read_text(encoding="utf-8"))
TABLES = DATA["tables"]


def write(name, obj):
    ROOT.joinpath(name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def klass(t):
    return re.search(r"class=([^;]+)", t["comment"])[1]


SHARED = {n for n, t in TABLES.items() if klass(t) == "SHARED_REFERENCE"}
DERIVED = {n for n, t in TABLES.items() if klass(t) == "TENANT_DERIVED"}
DIRECT = set(TABLES) - SHARED - DERIVED

CATALOGS = set("tenants company_locations departments teams job_positions leave_policies work_shifts training_programs position_skill_requirements".split())
SELF_TABLES = set("employees employee_addresses employee_bank_accounts employee_contacts employee_contracts employee_documents_metadata employee_kpis employee_reporting_structure employee_skills employee_training certifications employment_history attendance_records attendance_adjustments overtime_records leave_balances leave_entitlements leave_requests payroll_records salary_history bonuses compensation_adjustments deductions performance_goals performance_reviews project_assignments promotion_history shift_assignments timesheets".split())
MANAGER_DEPT = {
    "departments": "department_id", "teams": "department_id", "department_managers": "department_id",
    "employees": "department_id", "employment_history": "department_id", "job_openings": "department_id",
    "payroll_records": "department_id", "performance_reviews": "department_id", "projects": "owning_department_id",
    "project_resource_allocations": "department_id", "workforce_capacity": "department_id",
}

BASE_DENY = set("employees.national_id_number employee_addresses.address_line1 employee_addresses.address_line2 employee_addresses.postal_code employee_bank_accounts.account_number employee_bank_accounts.branch_code employee_bank_accounts.account_holder_name employee_documents_metadata.file_name employee_documents_metadata.storage_uri employee_documents_metadata.content_sha256 leave_requests.reason_text leave_approvals.comments performance_reviews.manager_comments attendance_adjustments.reason compensation_adjustments.reason".split())
PRIVATE_EMPLOYEE = set("gender date_of_birth nationality_country_code marital_status termination_reason is_rehire_eligible".split())


def make_policy(number, role, allowed):
    denied = set(BASE_DENY)
    # All unlisted columns of an allowed table are accessible. Deny sensitive
    # fields explicitly, including fields that can be used only as predicates.
    if role != "ADMIN":
        for table in ("job_positions", "job_openings", "cost_centers", "projects", "project_assignments"):
            for col in TABLES[table]["columns"]:
                if "sensitivity=RESTRICTED" in col["definition"]:
                    denied.add(f"{table}.{col['name']}")
        denied.add("payroll_records.bank_account_id")
    if role == "EMPLOYEE":
        denied.add("employee_contacts.contact_value")
        denied.add("employees.is_rehire_eligible")
        denied.add("employees.termination_reason")
    if role == "MANAGER":
        denied.update("employees." + c for c in PRIVATE_EMPLOYEE)
        denied.add("employees.work_email")
        for col in TABLES["payroll_records"]["columns"]:
            if "sensitivity=RESTRICTED" in col["definition"]:
                denied.add("payroll_records." + col["name"])
    rules = [{"table": t, "field": "tenant_id", "operator": "=", "valueFrom": "tenantId"} for t in sorted(allowed & DIRECT)]
    if role == "EMPLOYEE":
        rules += [{"table": t, "field": "employee_id", "operator": "=", "valueFrom": "employeeId"} for t in sorted(SELF_TABLES)]
        rules += [{"table": "performance_reviews", "field": "review_status", "operator": "=", "value": "FINALIZED"}, {"table": "employee_documents_metadata", "field": "is_confidential", "operator": "=", "value": 0}]
    elif role == "MANAGER":
        rules += [{"table": t, "field": c, "operator": "=", "valueFrom": "departmentId"} for t, c in sorted(MANAGER_DEPT.items())]
        rules += [{"table": "performance_reviews", "field": "review_status", "operator": "=", "value": "FINALIZED"}]
    return {
        "policyId": f"hrms-{number}-{role.lower()}-v1", "version": "1.0", "role": role,
        "allowedOperations": ["SELECT"], "allowedTables": sorted(allowed),
        "deniedColumns": sorted(c for c in denied if c.split(".")[0] in allowed), "rowRules": rules,
    }


SHORT_COMMON = [
    "Return one MySQL 8 SELECT with requested columns only; no SELECT *, writes, CTEs, subqueries, set operations, cross-database names or placeholders. LIMIT 100 for details.",
    "Use supplied schema, exact enums and complete FK keys. INNER/LEFT JOIN ON only. Apply literal context.tenantId to every tenant alias, including tenants.tenant_id; right-side LEFT JOIN guards belong in ON.",
    "Shared catalogs have no tenant column. Block employee_dependents, employee_emergency_contacts, payroll_components and performance_scores until inherited ownership is supported. Never invent columns or IDs.",
    "Never expose national IDs, bank account/branch/holder details, address lines/postcodes, document filenames/URIs/hashes or sensitive narratives. Gateway policy checks enforce the full table/column restrictions.",
    "Avoid one-to-many double counting; distinguish people, events and snapshots. Use employment_history for historical assignments, payroll/review department snapshots for historical facts. timesheets has no department_id.",
    "Annual salary is not paid payroll. Do not add payroll summaries to bonus/overtime/component details. Keep currencies separate; USD=amount/units_per_usd for matching month. Convert minutes to hours with /60.0.",
    "Use explicit date ranges, confirm as-of interval boundaries, preserve NULL, guard zero denominators. Use stored leave remaining_days; do not sum snapshots across months. Return historical data for forecasts.",
    "Refuse unsupported, ambiguous or out-of-scope requests; never relax scope or invent an answer. Rules guide generation; server validation authorizes execution.",
]
SHORT_ROLE = {
    "EMPLOYEE": "Own employee facts only: employee_id=context.employeeId on every subject alias; tenant catalogs remain tenant-scoped. Reviews FINALIZED; documents is_confidential=0. No peers, recruiting or project-wide data.",
    "MANAGER": "Exact department only: department_id=context.departmentId; projects use owning_department_id. No descendants or indirect employee tables lacking a department column. Reviews FINALIZED. No pay amounts, salary bands, budgets, billing rates or private demographics/contact fields.",
    "ADMIN": "All permitted modules/departments within context.tenantId only. Compensation allowed; listed sensitive fields and inherited tables remain blocked. Published reviews FINALIZED; paid-cash payroll uses payment_status=PAID and includes both run types unless requested otherwise.",
}

OWNERSHIP = {
    "employee_dependents": {"parent": "employees", "child_columns": ["employee_id"], "parent_columns": ["employee_id"]},
    "employee_emergency_contacts": {"parent": "employees", "child_columns": ["employee_id"], "parent_columns": ["employee_id"]},
    "payroll_components": {"parent": "payroll_records", "child_columns": ["payroll_record_id"], "parent_columns": ["payroll_record_id"]},
    "performance_scores": {"parent": "performance_reviews", "child_columns": ["performance_review_id"], "parent_columns": ["performance_review_id"]},
}

VARIANTS = [
    ("01-employee", "EMPLOYEE", SHARED | CATALOGS | SELF_TABLES),
    ("02-manager", "MANAGER", SHARED | CATALOGS | set(MANAGER_DEPT) | {"cost_centers"}),
    ("03-admin", "ADMIN", set(TABLES) - DERIVED),
]


def run():
    policies = {}
    for number, (key, role, allowed) in enumerate(VARIANTS, 1):
        policy = make_policy(number, role, allowed)
        user = {"userId": f"example-{role.lower()}", "role": role, "tenantId": 101}
        if role == "EMPLOYEE":
            user["employeeId"] = 1001
        if role == "MANAGER":
            user["departmentId"] = 10
        policies[role] = policy
        rules = {
            "role": role,
            "context": {k: v for k, v in user.items() if k not in ("userId", "role")},
            "rules": [*SHORT_COMMON, SHORT_ROLE[role]],
        }
        write(key + ".policy.json", policy)
        write(key + ".rules.json", rules)
        write(key + ".user.json", user)

    manifest = {n: {"class": klass(t), "tenant_column": "tenant_id" if n in DIRECT else None, **({"inherit": OWNERSHIP[n]} if n in DERIVED else {})} for n, t in TABLES.items()}
    write("ownership-design.json", {"notice": "Design manifest only. This object is NOT compatible with the current flat tenant_registry.json and must not be copied into it.", "tables": manifest})
    write("schema-allowlist.entry.json", {"enterprise_hrms_alpha": {n: [c["name"] for c in t["columns"]] for n, t in TABLES.items()}})

    lines = ["# Complete table coverage", "", "Every one of the 68 tables is listed. Allowed means policy-authorized after the compatibility prerequisites in README; it does not mean the current app can execute the table. All four inherited tables are denied. All shared tables await verifier support.", "", "| Table | Ownership | Employee | Manager | Administrator |", "|---|---|---|---|---|"]
    for n, t in TABLES.items():
        cells = []
        for role in ("EMPLOYEE", "MANAGER", "ADMIN"):
            p = policies[role]
            if n not in p["allowedTables"]:
                cells.append("DENY — inherited ownership pending" if n in DERIVED else "DENY")
            elif n in SHARED:
                cells.append("Global reference; verifier pending")
            else:
                extras = [r for r in p["rowRules"] if r["table"] == n and r["field"] != "tenant_id"]
                restrictions = [r["field"] + "=" + ("claim:" + r["valueFrom"] if "valueFrom" in r else str(r["value"])) for r in extras]
                cells.append("Tenant" + ("; " + "; ".join(restrictions) if restrictions else ""))
        lines.append("| `" + n + "` | " + klass(t) + " | " + " | ".join(cells) + " |")
    lines += ["", "All applicable column denials still apply to allowed tables. Their exact qualified names are in each policy JSON. The accompanying schema inventory records all 601 column definitions, keys, checks, and 138 declared foreign keys.", ""]
    ROOT.joinpath("table-coverage.md").write_text("\n".join(lines), encoding="utf-8")
    print("Classes:", dict(Counter(klass(t) for t in TABLES.values())))
    for role, p in policies.items():
        print(role, "allowed:", len(p["allowedTables"]), "denied:", len(TABLES)-len(p["allowedTables"]), "denied columns:", len(p["deniedColumns"]), "row rules:", len(p["rowRules"]))


if __name__ == "__main__":
    run()
