# Defensive Security Assessment: SQL Validator and Authorization Flow

Assessment date: 2026-10-07  
Scope: `backend/` and `sqlglot-service/` in this repository  
Method: source review plus synthetic requests to the local SQLGlot service and local Express API. No SQL was executed against a database, and no external system or real user was targeted.

## 1. Executive Summary

The current validator is not safe to use as a database security boundary. The principal design problem is that SQLGlot's scoped AST is flattened into global lists of tables, columns, filters, and joins. The Node authorization layer then proves that a required predicate exists somewhere for a table name, rather than proving that every row-producing relation instance and every query block is constrained.

The review confirmed false accepts for:

- cross-tenant self-joins where only one alias is filtered;
- cross-tenant scalar subqueries, derived tables, and CTEs;
- `SELECT *` and `alias.*` despite denied columns;
- nested data-modifying CTEs whose root statement is `SELECT`;
- MySQL executable comments ignored by SQLGlot but interpreted by MySQL;
- same-named tables in unapproved schemas;
- alias shadowing that causes a denied column to be attributed to another table;
- caller-forged policies and caller-forged user/tenant contexts;
- an allowed table (`departments`) that has no tenant rule; and
- unrestricted SQL functions such as `SLEEP`.

The existing 15 Node tests all passed. However, those tests mostly construct the simplified analysis object by hand and therefore do not test the security-critical AST-to-summary transformation. The Python extractor currently has no discovered tests.

Overall assessment: **unsafe for production enforcement**. Database-native row-level security and least-privilege database roles should remain the final boundary even after the application validator is redesigned.

### Finding summary

| ID | Severity | Finding | Observed |
|---|---|---|---|
| SQLV-001 | Critical | Policy and authenticated user are caller-controlled | `PASS` |
| SQLV-002 | Critical | Nested query blocks are not independently tenant-validated | `PASS` |
| SQLV-003 | Critical | Tenant checks collapse relation instances by physical table name | `PASS` |
| SQLV-004 | High | Global alias map ignores lexical scope | `PASS` |
| SQLV-005 | High | Wildcards bypass denied-column enforcement | `PASS` |
| SQLV-006 | Critical | Root-only operation check permits data-modifying CTEs | `PASS` |
| SQLV-007 | High | MySQL executable comments create a parser/database differential | `PASS` |
| SQLV-008 | High | Schema/catalog and quoted identifier identity is discarded | `PASS` |
| SQLV-009 | High | Allowed tables can silently have no tenant rule | `PASS` |
| SQLV-010 | Medium | SQL functions are unrestricted | `PASS` |

## 2. Architecture / Validation Flow

```text
HTTP request
  -> Express request validation
  -> inspectSql(sql, caller-supplied dialect)
  -> FastAPI /inspect
  -> SQLGlot parse (one top-level statement)
  -> extractor.py flattens the AST into JSON
       statementType: root node only
       tables: all Table nodes, without schema/catalog
       columns: all Column nodes, resolved by one global alias map
       filters: only root expression.args["where"]
       joins: extracted, but not used by the evaluator
  -> Node securityEvaluator
       root operation allowlist
       table name allowlist + denied-column list
       tenant filter existence/value check by table name
       additional row filter existence/value check by table name
  -> PASS / FAIL
```

Relevant implementation points:

- `backend/src/index.js:23-54` accepts the request and sends SQL for inspection.
- `sqlglot-service/inspector.py:17-82` parses exactly one top-level statement.
- `sqlglot-service/extractor.py:13-163` builds global alias, table, and column lists.
- `sqlglot-service/extractor.py:303-364` extracts only the root `WHERE` clause.
- `sqlglot-service/extractor.py:428-503` extracts joins.
- `backend/src/security/sql/securityEvaluator.js:15-52` runs the four checks, but never consumes `analysis.joins`.
- `backend/src/security/sql/tenantChecker.js:182-228` proves one matching filter per table name.
- `backend/src/security/sql/rowFilterChecker.js:7-21` uses the same table-name/filter-existence model.

The architectural invariant that must hold is stronger: every row-producing path, relation instance, and nested query block must be authorized in its own lexical scope. The current flattened intermediate representation cannot express that invariant.

## 3. Attack Surface

### Public/request-facing inputs

- `/api/verify-sql`: accepts `policy`, `user`, `sql`, and `dialect` from the request body.
- `/api/check-sql`: accepts a `userId`; any known demo identity may be selected, and an unknown identity falls back to the default context.
- `/api/query`: also selects its authorization context from request-supplied `userId`.
- `/api/users` and `/api/user-policy/:userId`: expose the demo identities and resolved policies.

### Parser and authorization boundary

- SQL dialect is selected by the caller, not fixed to the execution database.
- SQLGlot and the target database may interpret comments, quoting, functions, and dialect extensions differently.
- The original SQL is validated, while `normalizedSql` is generated with MySQL output syntax even when input was parsed as another dialect (`normalize_sql` defaults to MySQL).
- Tables/columns are gathered recursively, but predicates are gathered only from the root `WHERE`.
- Relation aliases are resolved globally rather than per scope.
- JOIN metadata is not enforced.
- Wildcards are not expanded against a trusted schema.

### Policy surface

- Table access is allowlisted.
- Column access is denylisted, making new or omitted sensitive columns allowed by default.
- Tenant and row rules are checked only for tables having an explicit policy rule.
- No function, operator, join type, schema, catalog, or nested-operation policy exists.

## 4. Findings

### SQLV-001 — Caller-controlled policy and identity

- **Severity:** Critical
- **Vulnerable file/function:** `backend/src/index.js:23-49` (`validateVerificationRequest`), `backend/src/index.js:83-94` (`POST /api/verify-sql`), `backend/src/index.js:112-155` (`/api/check-sql`, `/api/query`)
- **Root cause:** The API treats request-body `policy` and `user` objects, or a request-body `userId`, as authenticated authorization state. There is no authentication middleware or server-side binding between the requester, tenant, role, and policy.
- **Incorrect assumption:** Structurally valid JSON supplied by a client is equivalent to a trusted authenticated context and trusted policy decision.
- **Minimal synthetic test:** POST `/api/verify-sql` with a user-selected tenant and policy:

```json
{
  "user": { "userId": "attacker-chosen", "role": "MANAGER", "tenantId": 102 },
  "policy": {
    "allowedOperations": ["SELECT"],
    "allowedTables": ["employees"],
    "deniedColumns": [],
    "requiredFilters": [
      { "table": "employees", "column": "tenant_id", "operator": "=", "valueFrom": "tenantId" }
    ]
  },
  "sql": "SELECT salary FROM employees WHERE tenant_id = 102",
  "dialect": "mysql"
}
```

- **Expected validator result:** `FAIL`; callers must not be able to select their identity, tenant, or policy.
- **Actual validator result:** `PASS` (confirmed through the local API).
- **Security impact:** Complete bypass of tenant, role, table, and column policy if a downstream component treats this result as authoritative.
- **Recommended fix:** Authenticate the request; derive tenant, subject, and roles from a verified server-side principal; load policy server-side; remove `policy` and `user` from the public verification contract. Reject unknown users instead of falling back to a default identity. Treat the current endpoints as explicitly development-only until this is done.
- **Suggested test:** Send a forged `tenantId`, role, denied-column list, and policy ID and assert they are ignored/rejected; assert an unknown `userId` returns 401/403 rather than selecting the default user.
- **Regression risk:** High. The frontend/demo currently depends on selecting mock users and directly submitting policy objects. Preserve that behavior only behind a development flag and a non-production route.

### SQLV-002 — Nested query blocks are not independently tenant-validated

- **Severity:** Critical
- **Vulnerable file/function:** `sqlglot-service/extractor.py:303-364` (`extract_filters`), `backend/src/security/sql/tenantChecker.js:182-228` (`checkTenant`), `backend/src/security/sql/rowFilterChecker.js:7-21` (`checkRowFilters`)
- **Root cause:** `extract_filters` reads only `expression.args.get("where")` on the root expression. Nested `SELECT`, derived-table, and CTE predicates are not represented. Tables and columns, by contrast, are collected recursively and merged.
- **Incorrect assumption:** A valid tenant predicate in the outer query constrains every nested occurrence of the same physical table.
- **Minimal synthetic SQL:** 

```sql
SELECT (
  SELECT e2.name
  FROM employees e2
  WHERE e2.tenant_id = 102
  LIMIT 1
) AS leaked_name
FROM employees e
WHERE e.tenant_id = 101
  AND e.department_id = 1
```

- **Expected validator result:** `FAIL` because the scalar subquery reads tenant 102.
- **Actual validator result:** `PASS` (confirmed).
- **Security impact:** Direct cross-tenant disclosure through scalar subqueries. Equivalent false accepts were confirmed with a derived table and a CTE that relabel tenant-102 rows with tenant-101 constants.
- **Recommended fix:** Produce a scoped intermediate representation with one node per query block. Recursively validate every `Select`, subquery, derived source, CTE body, and set-operation branch. Associate every column and predicate with a scope ID and relation-instance ID. Never use an outer predicate to satisfy an inner rule unless a sound correlated-reference analysis proves the relationship.
- **Suggested test:** Seed synthetic tenants 101 and 102, run the SQL above through the validator, and assert `FAIL`. Add variants for `EXISTS`, `IN`, scalar subqueries, correlated subqueries, derived tables, and CTEs.
- **Regression risk:** Medium to high. Legitimate nested analytics will initially fail until each block is represented and validated; correlated subqueries require careful scope resolution.

### SQLV-003 — Relation instances are collapsed by table name

- **Severity:** Critical
- **Vulnerable file/function:** `sqlglot-service/extractor.py:65-105` (`extract_tables`), `backend/src/security/sql/tenantChecker.js:102-104,182-228` (`checkTenant`), `backend/src/security/sql/rowFilterChecker.js:9-21` (`checkRowFilters`), `backend/src/security/sql/securityEvaluator.js:27-35` (JOIN results unused)
- **Root cause:** Authorization keys tenant requirements by normalized physical table name. Multiple aliases of the same table are indistinguishable. A matching predicate on one alias satisfies the rule for all aliases. Unsupported or unsafe JOIN conditions do not affect the final decision.
- **Incorrect assumption:** One tenant predicate per table name is sufficient even when the table appears multiple times.
- **Minimal synthetic SQL:**

```sql
SELECT victim.name
FROM employees safe
JOIN employees victim ON 1 = 1
WHERE safe.tenant_id = 101
  AND safe.department_id = 1
```

- **Expected validator result:** `FAIL`; `victim` has no tenant or department restriction.
- **Actual validator result:** `PASS` (confirmed; extracted tables were `employees, employees`).
- **Security impact:** Direct cross-tenant disclosure through self-joins and Cartesian joins. The same defect affects repeated table references across nested scopes.
- **Recommended fix:** Assign a unique relation-instance ID to every `FROM`/`JOIN` source. Require mandatory predicates for every protected instance. Validate JOIN type and `ON` expression, reject unsupported relationships, and do not let an alias's rule satisfy another alias's rule. Prefer database RLS so aliases cannot bypass tenant isolation.
- **Suggested test:** Create one row for tenant 101 and one for tenant 102, execute the query only after validator denial is asserted, and verify every self-join alias must have `alias.tenant_id = 101` plus its applicable row rules.
- **Regression risk:** Medium. Queries that intentionally self-join within a tenant will need predicates on both aliases or a formally verified tenant-equality join plus one anchored predicate.

### SQLV-004 — Global alias mapping ignores lexical scope

- **Severity:** High
- **Vulnerable file/function:** `sqlglot-service/extractor.py:13-62` (`build_alias_map`, `resolve_table_name`), `sqlglot-service/extractor.py:108-163` (`extract_columns`)
- **Root cause:** A single alias map is built from every `Table` node in the entire AST. Inner aliases overwrite outer aliases with the same spelling, even though SQL alias scope is lexical.
- **Incorrect assumption:** An alias has one meaning across the entire statement.
- **Minimal synthetic SQL:**

```sql
SELECT victim.salary,
       (SELECT victim.name FROM departments victim LIMIT 1)
FROM employees safe
JOIN employees victim ON 1 = 1
WHERE safe.tenant_id = 101
  AND safe.department_id = 1
```

- **Expected validator result:** `FAIL` for `employees.salary`, as well as the unscoped `victim` relation.
- **Actual validator result:** `PASS` (confirmed). The inner `departments victim` binding causes the outer `victim.salary` to be attributed to `departments`, so the `employees.salary` deny rule does not match.
- **Security impact:** Denied-column and table ownership checks can be bypassed using alias shadowing. Combined with SQLV-003, this exposes both cross-tenant and restricted-column data.
- **Recommended fix:** Resolve identifiers with SQLGlot's scope model (or an equivalent symbol table) separately for every query block. Store the resolved source identity on each column reference. Reject unresolved and multiply-resolved references.
- **Suggested test:** Reuse the same alias name in outer and inner scopes and assert each column resolves to the correct source; include three-level nesting and correlated references.
- **Regression risk:** Medium. Correct scope resolution may newly reject previously accepted ambiguous SQL, which is desirable for a security boundary.

### SQLV-005 — Wildcards bypass denied-column enforcement

- **Severity:** High
- **Vulnerable file/function:** `sqlglot-service/extractor.py:108-163` (`extract_columns`), `backend/src/security/sql/tableColumnChecker.js:27-42` (`checkTableColumns`)
- **Root cause:** The extractor visits only `exp.Column`. An unqualified `*` is an `exp.Star`, and a qualified wildcard is not expanded to the actual schema columns. The checker sees zero columns or only a benign `*`, neither of which matches `employees.salary` or `employees.date_of_birth`.
- **Incorrect assumption:** Enumerating `Column` AST nodes enumerates all data returned by a query.
- **Minimal synthetic SQL:**

```sql
SELECT *
FROM employees e
WHERE e.tenant_id = 101
  AND e.department_id = 1
```

- **Expected validator result:** `FAIL` because the result includes denied columns `salary` and `date_of_birth`.
- **Actual validator result:** `PASS` (confirmed). `SELECT e.*` also passed.
- **Security impact:** Direct disclosure of every denied and future sensitive column in an otherwise authorized table.
- **Recommended fix:** Reject wildcards for protected tables, or expand them using a trusted, versioned schema catalog before authorization and verify every expanded column. An allowlist of selectable columns is safer than a denylist under schema evolution.
- **Suggested test:** Assert `*`, `e.*`, wildcard through a CTE/derived table, and wildcard after a schema change all fail or expand to authorized columns only.
- **Regression risk:** High if clients rely on `SELECT *`. Explicit projections should replace wildcard queries.

### SQLV-006 — Root-only operation check permits data-modifying CTEs

- **Severity:** Critical
- **Vulnerable file/function:** `sqlglot-service/extractor.py:516-539` (`extract_sql_info`), `sqlglot-service/inspector.py:85-101` (`get_statement_type`), `backend/src/security/sql/securityEvaluator.js:15-25` (`evaluateSqlSecurity`)
- **Root cause:** Only `expression.key` for the root AST node is checked. Nested `INSERT`, `UPDATE`, or `DELETE` nodes are not prohibited. PostgreSQL permits data-modifying statements inside CTEs.
- **Incorrect assumption:** A root `SELECT` means the complete statement is read-only.
- **Minimal synthetic SQL (parse/validation only; not executed):**

```sql
WITH employees AS (
  DELETE FROM app.employees
  WHERE tenant_id = 102
  RETURNING name, 101 AS tenant_id, 1 AS department_id
)
SELECT employees.name
FROM employees
WHERE employees.tenant_id = 101
  AND employees.department_id = 1
```

- **Expected validator result:** `FAIL` because a `DELETE` exists anywhere in the AST and the policy permits only `SELECT`.
- **Actual validator result:** `PASS` when parsed with the PostgreSQL dialect (confirmed; SQL was never sent to a database).
- **Security impact:** Unauthorized modification or deletion if the validated original SQL is executed with a write-capable PostgreSQL role.
- **Recommended fix:** Walk the entire AST and fail if any prohibited DML, DDL, transaction, command, copy/export, or procedure node exists. Execute through a database role that has no write/DDL privileges and preferably enforce a read-only transaction.
- **Suggested test:** Add `DELETE`, `UPDATE`, and `INSERT` CTE variants and assert rejection before execution. Add database integration tests under a role that is technically incapable of mutation.
- **Regression risk:** Low for a SELECT-only product. Higher only if data-modifying CTEs are an intended feature, in which case they require a separate policy model.

### SQLV-007 — MySQL executable comments create a parser/database differential

- **Severity:** High
- **Vulnerable file/function:** `sqlglot-service/inspector.py:17-82` (`parse_sql`), `sqlglot-service/extractor.py:303-364` (`extract_filters`), `backend/src/index.js:52-54` (`verifySql`)
- **Root cause:** SQLGlot treats MySQL version comments as comments and normalizes `/*!50000 ... */` to an inert-looking comment. A compatible MySQL server executes the content. The validator authorizes the parser's interpretation while a downstream database may execute the original string under different semantics.
- **Incorrect assumption:** SQLGlot and the target database interpret all comments identically.
- **Minimal synthetic SQL:**

```sql
SELECT e.name
FROM employees e
WHERE e.tenant_id = 101
  AND e.department_id = 1
/*!50000 OR 1 = 1 */
```

- **Expected validator result:** `FAIL` because an executable comment changes the predicate to allow all rows.
- **Actual validator result:** `PASS` (confirmed). SQLGlot normalized the suffix as `/* !50000 OR 1 = 1 */`.
- **Security impact:** Cross-tenant disclosure when the original SQL is executed by a MySQL-compatible database that honors executable comments.
- **Recommended fix:** Fix the execution dialect server-side; reject MySQL executable comments before parsing; preferably reject all comments in generated SQL; test the exact parser/database/version combination. Never validate one string and execute a semantically different one.
- **Suggested test:** Assert rejection for version comments with `OR`, `UNION`, functions, and nested statements. In an isolated read-only test database, compare SQLGlot's AST semantics with the database's `EXPLAIN`/parse result.
- **Regression risk:** Low unless legitimate generated SQL depends on comments or optimizer hints. If hints are required, permit a narrow parsed allowlist.

### SQLV-008 — Schema/catalog and quoted identifier identity is discarded

- **Severity:** High
- **Vulnerable file/function:** `sqlglot-service/extractor.py:31-40,85-103` (`build_alias_map`, `extract_tables`), `backend/src/security/sql/tableColumnChecker.js:1-14` (`normalized`, `checkTableColumns`)
- **Root cause:** `Table.name` is retained while catalog/database/schema qualifiers are discarded. The Node layer lowercases all identifiers, including quoted identifiers whose case can be semantically significant.
- **Incorrect assumption:** The unqualified, lowercased object name uniquely identifies the database object.
- **Minimal synthetic SQL:**

```sql
SELECT e.name
FROM other.employees e
WHERE e.tenant_id = 101
  AND e.department_id = 1
```

- **Expected validator result:** `FAIL` because `other.employees` is not the policy's authorized object.
- **Actual validator result:** `PASS` (confirmed). A PostgreSQL query against quoted `"EMPLOYEES"` also passed after normalization to `employees`.
- **Security impact:** Access to an unapproved same-named object in another schema/catalog, or to a distinct quoted-case object, when the database role can reach it.
- **Recommended fix:** Represent object identity as `{catalog, schema, name, quoted flags}` and compare it against fully qualified server-side policy entries using the target dialect's identifier rules. Set a safe search path and revoke access to unapproved schemas.
- **Suggested test:** Create synthetic `approved.employees`, `other.employees`, `employees`, and quoted `"EMPLOYEES"` objects and assert only the exact policy identity is accepted.
- **Regression risk:** Medium. Existing unqualified policies must be migrated to canonical fully qualified names.

### SQLV-009 — Allowed tables can silently have no tenant rule

- **Severity:** High
- **Vulnerable file/function:** `backend/src/security/sql/tenantChecker.js:182-245` (`checkTenant`), `backend/src/policies/managerPolicy.json:5-21`
- **Root cause:** The checker requires that the policy contain at least one tenant rule globally, but computes `applicableRules` only for referenced table names. If an allowed table has no tenant rule, the checker returns `PASS` with “No referenced table requires tenant isolation.” The manager policy allows `departments` but supplies tenant and department rules only for `employees`.
- **Incorrect assumption:** Absence of a tenant rule means the table is intentionally global.
- **Minimal synthetic SQL:**

```sql
SELECT * FROM departments
```

- **Expected validator result:** `FAIL` if `departments` is tenant-owned, or unless it is explicitly declared global.
- **Actual validator result:** `PASS` under `managerPolicy.json` (confirmed).
- **Security impact:** Cross-tenant access to any allowed table accidentally omitted from row rules. JOINs to that table also pass without a tenant predicate.
- **Recommended fix:** Make table scope explicit: every allowed table must be either `tenantScoped` with a rule or present in a reviewed `globalTables` list. Validate policy completeness at startup and fail closed for unknown scope.
- **Suggested test:** Iterate every `allowedTables` entry and assert exactly one scope classification. Assert a tenant-scoped `departments` query without a tenant predicate fails.
- **Regression risk:** Medium. Legitimately global lookup tables need explicit classification.

### SQLV-010 — SQL functions are unrestricted

- **Severity:** Medium
- **Vulnerable file/function:** `sqlglot-service/extractor.py:506-539` (`extract_sql_info` omits functions), `backend/src/security/sql/securityEvaluator.js:15-52` (`evaluateSqlSecurity`)
- **Root cause:** Function and procedure nodes are neither returned by the extractor nor checked by the policy evaluator.
- **Incorrect assumption:** A permitted `SELECT` over an allowed table is harmless regardless of invoked functions.
- **Minimal synthetic SQL:**

```sql
SELECT SLEEP(1)
FROM employees e
WHERE e.tenant_id = 101
  AND e.department_id = 1
```

- **Expected validator result:** `FAIL` because `SLEEP` is not an approved analytical function.
- **Actual validator result:** `PASS` (confirmed; function was parsed only, not executed).
- **Security impact:** Database resource exhaustion, timing channels, or use of file/network/system functions where the database and account expose them.
- **Recommended fix:** Extract all function/procedure nodes and enforce a conservative dialect-specific allowlist. Reject volatile, side-effecting, file, network, sleep/benchmark, dynamic-SQL, and unknown functions. Add database statement timeouts.
- **Suggested test:** Assert rejection of `SLEEP`, `BENCHMARK`, file/network functions, unknown UDFs, and stored procedures; assert approved aggregates such as `COUNT` remain accepted.
- **Regression risk:** Medium. Legitimate analytics may use a broad function set, so the allowlist needs ownership and versioning.

## 5. Security Test Matrix

All “actual” results below came from the local project API except the multi-statement case, which is also directly enforced by `parse_sql` at `inspector.py:77-80`. None of the SQL was executed against a database.

| Area | Synthetic case | Expected | Actual | Status |
|---|---|---:|---:|---|
| Baseline | tenant 101 + department 1, explicit allowed column | PASS | PASS | Correct |
| Missing tenant | no `tenant_id` predicate | FAIL | FAIL (`MISSING_TENANT_FILTER`) | Correct |
| Wrong tenant | `tenant_id = 102` | FAIL | FAIL (`WRONG_TENANT`) | Correct |
| Boolean OR | `tenant_id = 101 OR tenant_id = 102` | FAIL | FAIL (`UNSAFE_TENANT_EXPRESSION`) | Correct |
| UNION | safe branch `UNION` tenant-102 branch | FAIL | FAIL (`OPERATION_NOT_ALLOWED` plus missing filters) | Correct for current SELECT-only policy |
| Multiple statements | safe `SELECT; SELECT ...` | FAIL | FAIL at parser | Correct |
| Self-join | only first `employees` alias scoped | FAIL | PASS | Vulnerable: SQLV-003 |
| Scalar subquery | outer tenant 101, inner tenant 102 | FAIL | PASS | Vulnerable: SQLV-002 |
| Derived table | tenant-102 rows relabeled as tenant 101 | FAIL | PASS | Vulnerable: SQLV-002 |
| CTE | tenant-102 rows relabeled as tenant 101 | FAIL | PASS | Vulnerable: SQLV-002 |
| Nested DML | `DELETE` inside CTE, root `SELECT` | FAIL | PASS | Vulnerable: SQLV-006 |
| Alias shadowing | inner alias changes outer restricted-column ownership | FAIL | PASS | Vulnerable: SQLV-004 |
| Wildcard | `SELECT *` from employees | FAIL | PASS | Vulnerable: SQLV-005 |
| Qualified wildcard | `SELECT e.*` | FAIL | PASS | Vulnerable: SQLV-005 |
| Schema qualification | `other.employees` | FAIL | PASS | Vulnerable: SQLV-008 |
| Quoted/case-sensitive name | PostgreSQL `"EMPLOYEES"` | FAIL | PASS | Vulnerable: SQLV-008 |
| Executable comment | MySQL version comment adds `OR 1=1` | FAIL | PASS | Vulnerable: SQLV-007 |
| Unscoped allowed table | `SELECT * FROM departments` | FAIL if tenant-owned | PASS | Vulnerable/policy gap: SQLV-009 |
| JOIN filter in `ON` | mandatory filters only in `ON` | PASS if semantically valid | FAIL | Safe false negative; extractor checks only root `WHERE` |
| Multiple-table ambiguity | unqualified column with two tables | FAIL | FAIL (`AMBIGUOUS_COLUMN`) | Correct |
| Function | `SLEEP(1)` inside otherwise valid SELECT | FAIL | PASS | Vulnerable: SQLV-010 |
| Caller-forged policy | remove denied columns, select tenant 102 | FAIL | PASS | Vulnerable: SQLV-001 |
| Mixed-case MySQL identifiers | quoted case variants of allowed identifiers | PASS on case-insensitive target | PASS | Dialect-dependent; requires exact DB alignment |

## 6. Recommended Code Fixes

### Priority 0: Containment

1. Do not execute a query solely because this validator returned `PASS`.
2. Use a read-only database account with access only to approved schemas/views.
3. Add database-native RLS keyed from a server-set tenant session value.
4. Put a statement timeout and row/result-size limits on every query.
5. Disable the public policy/user submission path outside development.

### Priority 1: Replace the flattened security model

Return or evaluate a scope-aware representation resembling:

```json
{
  "queryBlocks": [
    {
      "scopeId": "q1",
      "operation": "SELECT",
      "sources": [
        {
          "relationId": "q1:r1",
          "catalog": null,
          "schema": "app",
          "name": "employees",
          "alias": "e"
        }
      ],
      "predicates": { "booleanAst": "...", "resolvedColumns": [] },
      "projections": [],
      "children": []
    }
  ]
}
```

Validation should be recursive and fail closed when identifier ownership, predicate semantics, or a dialect extension cannot be proven safe.

### Priority 2: Enforce complete AST restrictions

- Walk every AST node and reject nested DML/DDL/commands.
- Validate every query block and every set-operation branch.
- Treat each alias/source as a separate protected relation instance.
- Preserve full object identity and quotedness.
- Reject or schema-expand wildcards.
- Enforce a function allowlist.
- Reject executable comments and fix the dialect server-side.
- Validate JOIN type and ON predicates; do not ignore `analysis.joins`.
- Represent boolean predicates structurally. Required restrictions must dominate every satisfiable path; textual existence is insufficient.

### Priority 3: Strengthen policy design

- Use positive column allowlists.
- Require an explicit scope classification for every table.
- Validate policy schemas at startup and reject duplicates/conflicts.
- Bind policy versions to schema versions.
- Resolve all dynamic values from the authenticated server-side principal.

## 7. Regression Tests

### Extractor unit tests

Add Python tests for:

- scope-local alias resolution;
- catalog/schema/name/quoted identifier preservation;
- wildcard nodes;
- all nested query blocks and CTE bodies;
- all operations anywhere in the AST;
- boolean AST preservation (`AND`, `OR`, `NOT`, parentheses);
- filters in `WHERE`, `JOIN ON`, `HAVING`, and correlated subqueries;
- MySQL executable comments; and
- UNION/INTERSECT/EXCEPT branch enumeration.

### Evaluator unit tests

Use the new scoped representation and assert:

- each protected relation instance has its own tenant predicate;
- one alias cannot satisfy another alias's rule;
- outer predicates cannot satisfy inner query blocks;
- every allowed table has an explicit scope classification;
- wildcards are rejected/expanded;
- unapproved schemas and quoted-case identities fail;
- unknown functions and any nested write operation fail; and
- caller-supplied identity/policy fields have no authority.

### End-to-end integration tests

Run the exact SQL cases in the matrix through `/api/verify-sql`. For database semantics, use an isolated synthetic schema with tenant 101 and tenant 102 rows, a read-only test role, and transactions that are always rolled back. Compare the parser's interpretation with the target database's parser/plan. Data-modifying cases should be rejected before database submission.

### Recommended CI gates

- Existing Node tests: currently 15/15 passing.
- Python extractor tests: currently 0 discovered; add mandatory coverage.
- Differential corpus: every supported dialect/version.
- Property/fuzz tests: no accepted query may contain an unresolved source, wildcard, prohibited operation, executable comment, or protected relation instance lacking a mandatory predicate.

## 8. Remaining Risks

Even after the proposed changes, application-layer SQL authorization remains exposed to parser differentials, database-version changes, optimizer behavior, views/functions with hidden access, schema drift, collation/case rules, and resource-exhaustion queries. Specific residual concerns include:

- SQLGlot version upgrades changing AST shapes;
- target-database extensions not represented by SQLGlot;
- views or approved functions accessing unauthorized base objects;
- time/space denial of service through valid analytical queries;
- inference attacks through aggregates, errors, ordering, and timing;
- unsafe search paths or database privileges;
- differences between the validated SQL and the exact bytes executed; and
- denylist policy drift as columns are added.

Controls should therefore be layered: authenticated server-side context, a scope-aware validator, database RLS, approved views, read-only least privilege, fixed search paths, timeouts, quotas, logging, and result-size controls.

## 9. Overall Security Assessment

**Rating: Critical risk / not suitable as the sole enforcement boundary.**

The code has several good fail-closed behaviors: multiple top-level statements are rejected, direct wrong-tenant equality is rejected, tenant predicates using unsupported OR logic are rejected, unqualified columns in multi-table queries are rejected as ambiguous, and plain UNION is rejected by the current SELECT-only operation policy.

Those controls do not compensate for the loss of lexical scope and relation identity between SQLGlot and the Node checker. The demonstrated false accepts permit direct cross-tenant reads, denied-column reads, and—on PostgreSQL with a write-capable role—nested mutation. Remediation should begin with trusted identity/policy binding and database-native least privilege, followed by replacement of the flattened analysis with recursive scope-aware authorization.
