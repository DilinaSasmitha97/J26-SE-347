# HRMS user policies and NL-to-SQL rules: three variants

These proposals were derived from the **entire `Dump20261021.sql`** and the application's actual policy, generation, isolation, and masking code. They are reviewable configuration artifacts; they have not been installed into the application's runtime configuration or used to execute the dump.

## What was scanned

| Item | Finding |
|---|---|
| Database named in dump | `enterprise_hrms_alpha` |
| Database dialect | MySQL 8.0; server version in dump header: 8.0.43 |
| Tables / columns / declared foreign keys | **68 / 601 / 138** |
| Ownership classes | 47 tenant-owned, 3 tenant-config, 1 tenant-root, 13 shared-reference, 4 tenant-derived |
| Data rows supplied | None: **0 INSERT statements** |
| Source SHA-256 | `d3079c66c2bf33f17869f5d00a799ec743751bce4c1b2b5215485750ad0fb2ed` |

The dump provides structure, enum domains, constraints, comments and next auto-increment values. Auto-increment values are **not row counts**. It does not establish actual tenant/employee/department IDs, observed date ranges, completeness, distributions, populated currencies, or real business metric definitions. Sensitivity annotations and synthetic-data comments are dataset metadata; they do not grant access or override the requested analysis. No dump statements were executed.

The [full inventory](schema-inventory.json) records every column definition, table comment, primary/unique/index/check constraint, and declared FK. [Table coverage](table-coverage.md) gives an explicit allow/deny/scope decision for **each of the 68 tables under each variant**. Coverage does not mean every user receives access to every table.

## The three user-policy variants

| Variant | Audience and scope | Allowed / denied tables | Main access boundary |
|---|---|---|---|
| **1. Employee self-service** | One employee inside one tenant, plus approved tenant catalogs and shared lookups | **51 / 17** | Tenant + employee equality on all employee facts; finalized reviews; nonconfidential document metadata |
| **2. Department manager** | Exactly one department inside one tenant, plus approved tenant catalogs and shared lookups | **32 / 36** | Direct department predicates; no descendant or indirect employee-fact access; no exact compensation, salary bands, budgets, billing rates, or listed personal fields |
| **3. Tenant HR/payroll administrator** | All departments and permitted business modules within one tenant | **64 / 4** | Tenant only; permits operational HR and individual compensation; raw national ID, bank routing/account details, document paths and selected sensitive narratives remain denied |

All variants permit **SELECT only**. All four tenant-derived tables remain denied in all three policies pending independently verified inherited ownership. Shared reference tables are policy-authorized but need explicit verifier support before execution. The counts above describe the proposed policies, not the number of tables supported by the current runtime.

### 1. Employee self-service

Files: [policy JSON](01-employee.policy.json), [matching NL-to-SQL rules](01-employee.rules.json), [example user claims](01-employee.user.json).

Allows the employee's attendance, adjustments, shifts, overtime, leave requests/balances/entitlements, contract/history, skills/training/certifications, performance goals/KPIs/published reviews, salary history, payroll summaries, bonuses, recurring deductions, compensation adjustments, promotions, project assignments and timesheets.

Employee facts require both `tenant_id = user.tenantId` and `employee_id = user.employeeId`. Authentication `userId` is a string identity and is never used as the employee data key. Reviews also require `review_status = 'FINALIZED'`; document metadata requires `is_confidential = 0`. The employee can inspect own compensation amounts by access policy; the separate `EMPLOYEE` masking role may still redact classified values.

Private contact values, full home address fields, national ID, raw bank details, sensitive narrative text and document file names/URIs/hashes are denied. The policy exposes selected bank/contact metadata rather than a raw personal-data export. Project assignments/timesheets can return the employee's project IDs and hours, but `projects` is denied because the current policy format cannot enforce project-membership joins. A manager-name self-join is also blocked by the self-only restriction on every `employees` alias.

Suggested questions after prerequisites are met:

- “Show my approved overtime hours by month in 2025.”
- “Show my 2026 annual-leave remaining days and snapshot date.”
- “Show my net pay by payroll period for paid regular and supplementary runs in 2025.”
- “Show my completed training courses in 2025.”
- “Show my finalized performance review ratings by review cycle.”

Expected denials include peer salaries, recruiting candidates, confidential document metadata, bank account numbers, project-wide data, and other employees' records.

### 2. Department manager

Files: [policy JSON](02-manager.policy.json), [matching NL-to-SQL rules](02-manager.rules.json), [example user claims](02-manager.user.json).

Uses one exact department, resolved from `user.departmentId`. Direct filters apply to `employees`, `departments`, `teams`, `department_managers`, `employment_history`, `job_openings`, `payroll_records`, `performance_reviews`, `project_resource_allocations`, and `workforce_capacity`. `projects` uses `owning_department_id`. Payroll and performance use their **historical department snapshots**; employees use their current department. These scopes deliberately answer different questions.

Tenant-wide reference/configuration access includes positions, locations, cost-center labels, leave policies, shift definitions, program catalogs and position skill requirements. It does not include the restricted money columns. Only finalized performance reviews are allowed. All manager payroll monetary fields are denied, including using those fields in aggregates or predicates; the allowed payroll fields support operational status/count/day reporting.

**This conservative policy does not authorize attendance, leave employee facts, employee training/skills, timesheets, reporting-line facts, candidates or application details.** Most lack a direct department column. A rule on `employees.department_id` is checked only when `employees` is actually referenced; by itself it does not force a standalone child query to join employees. Granting those child tables without mandatory join-path verification would leave a scope gap. A production extension can permit these modules after implementing that proof. No department-descendant expansion or direct-report scope is claimed by this variant.

Suggested questions:

- “Count current employees in my department by employment status.”
- “Show my department's workforce capacity by month in 2025.”
- “Show requested seats and open requisitions for my department.”
- “Compare planned and actual project resource hours for my department by month.”
- “Show finalized review counts by rating band for my department.”

Expected denials include exact employee pay, aggregate pay, salary bands, medical narratives, other departments, attendance records and timesheets. A project owned by this department does not authorize employee records from contributing departments.

### 3. Tenant HR/payroll administrator

Files: [policy JSON](03-admin.policy.json), [matching NL-to-SQL rules](03-admin.rules.json), [example user claims](03-admin.user.json).

Allows all 51 directly scoped tables and all 13 shared catalogs. Covers organization, employee administration, recruitment, attendance, leave, payroll, performance, training and projects. It permits salary amounts, pay history, payroll summaries, compensation events, organizational budgets and authorized personal/contact/demographic fields. It remains restricted to **one tenant**; `ADMIN` does not imply platform or cross-tenant access.

The 15 explicit column denials cover national ID, address lines/postal code, bank account/branch/account-holder details, document filename/URI/hash, and selected narrative fields in leave requests/approvals, reviews, attendance adjustments and compensation adjustments. Other HR fields remain accessible by design; apply a narrower administrator policy if the business does not authorize those uses. All 4 inherited tables are denied until their parent-based ownership can be verified.

Suggested questions:

- “Show paid gross and net payroll by department snapshot and month for 2025, including both run types.”
- “Compare application and accepted-offer counts by candidate source for the same application cohort.”
- “Show approved overtime hours and overtime claim amounts by month.”
- “Show training completion counts and actual training cost by program.”
- “Show promotion event counts by department and year using historical attribution.”

Complex cohort/history questions can require more than the currently supported single SELECT shape. The generator must request clarification or split the work instead of emitting unsupported subqueries or multiplying fact tables.

## The three NL-to-SQL rule-set variants

Each `.rules.json` is **standalone**, with the common rules copied into it. There is no `extends` mechanism for the application to resolve. Use the rule file matching the policy and example user:

| Rule set | Added behavior |
|---|---|
| **1. Self-service translation** | Literal tenant/employee guards for every alias, self-only employee joins, finalized reviews, nonconfidential metadata; refuses peer, recruiting and project-wide requests |
| **2. Department operations translation** | Exact department predicates, snapshot-aware attribution, restricted monetary fields and indirect modules; refuses automatic descendant/report/project-collaborator expansion |
| **3. Tenant HR/payroll translation** | Tenant-wide authorized reporting, individual compensation and financial measures, explicit payroll/run/payment conventions; still refuses raw denied fields, cross-tenant access and inherited tables |

Each compact rule file contains only the role, example scope IDs, and **nine short instructions** covering safe SELECTs, tenant guards, complete FK joins, sensitive fields, reporting grain, historical attribution, money, dates and role-specific scope. Repeated table lists, column definitions, FK catalogs, enum lists and per-table essays have been removed; generation already receives the database schema. Full structural coverage remains in [schema-inventory.json](schema-inventory.json) and [table-coverage.md](table-coverage.md).

The complete access restrictions remain in the unchanged policy JSON and are enforced by the gateway. Compact rules provide role-level guidance rather than duplicating every permission: the generator can still draft a query the gateway rejects. The SQL-only generation service has no structured clarification/refusal response contract; these rule instructions do not add one.

### Database-specific semantic rules that matter

| Area | Required interpretation |
|---|---|
| Organization | `department_hierarchy` is closure with depth 0 = self; current and historical reporting lines differ; team FKs can include tenant + department + team |
| Employee history | `employees` is current state; `employment_history` carries effective-dated department/position/status; end-date inclusivity and interval overlap are not established by DDL |
| Compensation | Actual salary is `salary_history.annual_base_salary`; position bands are annual rates; monthly payroll is paid/accrued amounts, not annual rates divided and called actual pay |
| Payroll | One record per employee/period/**run type**; regular and supplementary can coexist; department is a pay-date snapshot; paid cash uses an explicit payment/reversal convention |
| Payroll components | Detail inherits tenant from payroll record and can have a shorter retention window; earning/deduction/employer components are not a single universally signed net-pay sum |
| Attendance and overtime | Daily attendance measures minutes; monthly overtime claims measure hours/amounts; payroll overtime can represent the same expense and must not be added twice |
| Leave | Snapshot balance and yearly grants differ; stored `remaining_days` avoids subtracting pending/taken twice; request `total_days` is working days and cannot exactly allocate overlapping requests by calendar-month arithmetic |
| Recruitment | Candidates, applications, interview rounds and opening seats have different grains; terminal application state does not supply complete stage-event history; accepted offer, planned start and actual hire are different events |
| Performance | Published metrics use finalized reviews; review-time department differs from current department; weighted scores need an explicit nonzero weight denominator; KPI units/direction must match |
| Projects | Assignment %, planned FTE, resource hours and weekly timesheets differ; timesheets lack a department column; owning and contributing departments differ; exact daily split within a timesheet week is unavailable |
| Training | Program defaults differ from actual enrollment cost/completion; skill assessments differ from certifications; `certifications.employee_training_id` has no declared FK |
| Reference and FX | Reference catalogs are shared; tenant configuration is not. `units_per_usd` means source/USD conversion divides by the rate; match currency and month. FX/holiday series are synthetic approximations |

## Application compatibility: required before use on this database

The policy JSON uses fields supported by the application today: `policyId`, `version`, `role`, `allowedOperations`, `allowedTables`, `deniedColumns`, and `rowRules` with `valueFrom` or literal `value`. It deliberately does **not** invent enforceable fields such as `aggregateOnly`, `minGroupSize`, `requiredJoins`, `columnMasks`, or `maxRows`.

**These files are structurally compatible proposals, not drop-in operational configurations for the current dataset wiring.** Prerequisites:

1. **Use the same target database for schema generation and execution.** The current defaults/bundled SQLite schema are `multi_tenant_hr`, with different table/column names. Configure the actual loaded `enterprise_hrms_alpha` database and avoid falling back to the old SQLite dataset. This analysis did not import the dump or verify a live database. The dump has structure only, so loading it alone does not populate data.
2. **Register the 68-table/601-column schema in the security allowlist.** The backend loads `packages/security-validation-layer/config/schema_allowlist.json` by database name. [schema-allowlist.entry.json](schema-allowlist.entry.json) is a generated, reviewable database entry to merge, not a replacement for the whole existing configuration.
3. **Correct and extend trusted tenant ownership.** The current `sqlglot-service/tenant_registry.json` contains only the older table set and maps `tenants` to `id`; this dump uses **`tenants.tenant_id`**. Register the 51 direct tables using their real tenant column. Missing ownership blocks execution even when the policy allows a table.
4. **Add shared-reference ownership support.** The current rewriter expects a tenant-column string for every source and has no explicit global-reference class. The 13 global tables lack tenant columns and are currently refused. **Do not give them a fabricated tenant_id or disable isolation checks.** Shared-only queries also need gateway handling because the current verified response contract expects at least one bound tenant parameter.
5. **Keep inherited tables denied until verification is implemented.** The 4 derived tables have no tenant column: `employee_dependents` and `employee_emergency_contacts` inherit through `employees`; `payroll_components` through `payroll_records`; `performance_scores` through `performance_reviews`. Their globally unique parent keys support these paths, but the current verifier does not prove inherited ownership. [ownership-design.json](ownership-design.json) documents the intended classes/paths; it is **not compatible with the flat runtime registry** and must not be copied into it. Future support must prove the complete parent join and tenant/employee/department restrictions for each child alias.
6. **Update PII tagging and review masking for this schema.** Runtime code loads `pii_columns.json` and `masking_policy.json`; it does not automatically enforce dump annotations such as `mask=BAND`, `YEAR_ONLY`, `LAST4` or `FULL`. Current masking actions are `clear`, `partial`, `redact`, `fpe`, not a salary-band engine. Role policies here deny particularly sensitive fields rather than promising unimplemented masking. `ADMIN` currently defaults to clear for classified PII, while `EMPLOYEE` defaults to redact. Exposed fields need explicit review, including generated `full_name`, polymorphic `contact_value`, national IDs, document metadata and narratives. Do not treat an unknown/unclassified numeric value as protected by NER.
7. **Supply identity, policy and generation scope from trusted server context.** The demo editors accept operator-supplied claims/policy, and policy `role` is descriptive metadata rather than a server-enforced assignment to that role. The backend does not authenticate these pasted claims or automatically select these policies. Production must bind user, tenant, employee/department scope, policy and masking role on the server. A user-written department or tenant ID must never create authorization.

The current gateway supports one SELECT over recognized physical sources, INNER/LEFT joins, aggregates and supported windows. It refuses CTEs, nested queries, set operations, RIGHT/FULL/NATURAL/USING joins, qualified databases, placeholders and unknown/custom functions. Some valid reporting requests therefore require a separate query/workflow or a verified execution extension.

### Enforced controls versus guidance

| Control | Where it actually belongs |
|---|---|
| SELECT-only, table allowlist, denied source columns | Current SQL safety/access checks plus schema allowlist |
| Tenant guard per alias | Trusted registry + deterministic repair + independent verification |
| Employee/department/status/confidentiality row filters | Policy rowRules, independently verified; generator must already include non-tenant guards |
| Ownership inherited through parent joins | Additional verifier capability; currently blocked |
| Global reference sources | Explicit shared-reference verifier capability; currently missing |
| Display redaction/pseudonyms | Separate server-loaded PII classification/masking configuration |
| Correct grain, metric meaning, dates, currency conventions | NL rule guidance and report review; not proven by access-policy checks |
| Aggregate-only access, minimum group size, inference resistance, output row caps | No such enforcement is added by these policy files; prompt instructions alone cannot guarantee them |

Column denials apply to source references throughout the query, not just visible output. For example, the manager cannot ask for average salary by department because the salary source is denied, even though the output would be aggregated. These are not anonymization or aggregate-only policies.

## How to use the files after prerequisites

1. Select one complete trio: `01-employee`, `02-manager`, or `03-admin`.
2. Put `.user.json` into **Authenticated user**, `.policy.json` into **User policy**, and `.rules.json` into **NL-to-SQL rules**.
3. Replace example tenant `101`, employee `1001`, or department `10` with real authorized IDs in both user JSON and the rules file's `context` object. These IDs were not observed in data. `userId` is an example authentication identifier. The policy dynamically resolves `valueFrom`; generation must use the matching context values as SQL literals. Supply the correct business date/timezone when asking relative-date questions.
4. Generate a draft, review its identifiers, filters, dates and grain, then validate through the gateway before execution. Tenant repair can supply/correct direct tenant guards, but it does **not** invent employee, department, finalized-review or confidentiality guards. Missing required non-tenant guards must block the query.
5. Treat a missing ownership/schema/masking capability as a configuration task, not a reason to relax the policy. No unverified inherited table access is authorized by these proposals.

The generator receives only the question and the submitted rules object. It does **not** receive the user policy or authenticated claims automatically. The compact `context` supplies example tenant/employee/department scope; the rules describe the role restrictions. The full table/column permissions stay in the separate policy and are checked after generation. JSON rule keys are prompt content, not a second machine-enforced policy language.

## Validation and source trace

All JSON exports were checked for parseability; policy identifiers match the full schema. Row rules resolve using the application's own `resolvePolicyValues` helper. Each compact rules file has nine instructions, is under 3 KB, and matches its policy/user role and scope IDs. Complete table/FK/enum detail remains in the schema inventory. The application's access checker passed 10 positive/negative cases. Its isolation verifier passed 16 positive/negative cases using a process-local proposed registry for the 51 direct tables, with no runtime registry changes. See [validation-results.json](validation-results.json) for the exact checks and limitations. No live database execution, LLM generation, or deployed authorization/masking validation is claimed.

The extraction can be reproduced with `python docs/hrms-policy-variants/inspect_dump.py`; policy/rule generation with `python docs/hrms-policy-variants/generate_variants.py`; validation with `.\sqlglot-service\.venv\Scripts\python.exe docs/hrms-policy-variants/validate_variants.py`. `inspect_dump.py` reads the source path recorded in that script. The proposal generator uses the saved inventory and writes only this documentation directory.

Application evidence:

- [README: manual context, generation contract and supported execution](../../README.md)
- [Request/policy validation](../../backend/src/index.js)
- [Claim resolution](../../backend/src/utils/resolvePolicyValues.js)
- [Table/column enforcement](../../backend/src/security/sql/tableColumnChecker.js)
- [Generation payload, schema allowlist and result masking](../../backend/src/services/secureQueryService.js)
- [Current ownership registry](../../sqlglot-service/tenant_registry.json) and [rewriter/verifier](../../sqlglot-service/rewriter.py)
- [NL prompt construction](../../nl-to-sql-service/prompts.py)
- [Current masking configuration](../../packages/security-validation-layer/config/masking_policy.json)
