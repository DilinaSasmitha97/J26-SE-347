# SQL Security-Validation Bypass Report

**Target:** `Bosilu/secure-policy-prototype`
**Scope:** SQL queries that pass `evaluateSqlSecurity` but violate the intended security policy.
**Date:** 2026-10-07
**Method:** Static code review + dynamic confirmation. Every finding marked *CONFIRMED* was executed against the real SQLGlot extractor (`sqlglot 30.12.0`) and the real Node checkers (`node v22.12.0`) using the shipped `employeePolicy.json` / `managerPolicy.json`.

---

## How enforcement works (and where it breaks)

```
raw SQL ──▶ Python SQLGlot service (extractor.py) ──▶ analysis JSON
                                                         │
          evaluateSqlSecurity ◀──────────────────────────┘
          ├─ operation check      (statementType ∈ allowedOperations)
          ├─ tableColumnChecker   (allowedTables / deniedColumns)
          ├─ tenantChecker        (tenant_id = <user tenant>)
          └─ rowFilterChecker     (other required row filters)
```

**Root cause of most bypasses:** the security decision is made entirely from what `extractor.py` chooses to surface. Anything it does not extract — `*`, function calls, subquery internals — is invisible to the checkers and therefore unregulated.

**Policy baselines used in examples**
- *Employee*: `tenantId 101`, rules `tenant_id = tenantId`, `id = userId`.
- *Manager*: `tenantId 101`, `departmentId 1`, rules `tenant_id = tenantId`, `department_id = departmentId`. No per-row id lock → this is the primary exploit surface.

> Note: `checkAccess.js` and `postGenValidator.js` are **not imported by `index.js`** — they are dead code and enforce nothing.

---

## Risk summary

| ID | Severity | Title | Status |
|----|----------|-------|--------|
| C-1 | 🔴 Critical | `SELECT *` bypasses denied-column protection (salary, DOB) | **CONFIRMED PASS** |
| C-2 | 🔴 Critical | Tables with no tenant rule have zero tenant isolation | **CONFIRMED PASS** |
| C-3 | 🔴 Critical | `/api/verify-sql` trusts client-supplied `policy` + `user` | Confirmed by code |
| H-1 | 🟠 High | `LOAD_FILE()` / arbitrary functions pass unchecked (server file read) | **CONFIRMED PASS** |
| H-2 | 🟠 High | `SLEEP()` and other functions enable time-based DoS | **CONFIRMED PASS** |
| H-3 | 🟠 High | Attacker-controlled `dialect` (parser-differential) | Confirmed by code |
| H-4 | 🟠 High | Dead-code validators give false assurance | Confirmed by code |
| M-1 | 🟡 Medium | Tenant safety relies on a text regex over `raw` | Confirmed by code |
| M-2 | 🟡 Medium | String-based value comparison (type juggling) | Confirmed by code |
| M-3 | 🟡 Medium | Only top-level `WHERE` is inspected for filters | **CONFIRMED** |
| L-1 | 🟢 Low | No authentication/authorization on any endpoint | Confirmed by code |
| L-2 | 🟢 Low | Internal parser errors leaked to client | Confirmed by code |
| L-3 | 🟢 Low | Employee `id` rule can never match (breaks all employee queries) | **CONFIRMED FAIL-closed** |

---

## 🔴 CRITICAL

### C-1 — `SELECT *` bypasses denied-column protection  *(CONFIRMED PASS)*

`extract_columns` iterates `exp.Column` nodes only. A `*` is an `exp.Star`, so it is never extracted; `tableColumnChecker` can only block columns it is handed.

**PoC (Manager):**
```sql
SELECT * FROM employees WHERE tenant_id = 101 AND department_id = 1;
```

**Evidence:**
- Extractor `columns` → `[(None,'tenant_id'), (None,'department_id')]` — `salary`/`date_of_birth` never appear.
- `evaluateSqlSecurity` → **PASS ✅**
- Control is proven working for the explicit form: `SELECT salary …` → `FAIL (BLOCKED_COLUMN)`.

**Impact:** Full disclosure of `employees.salary` and `employees.date_of_birth` — the exact columns the policy exists to protect. `employees.*` behaves identically (extracted as `('employees','*')`, which is not in the denied set).

**Fix:** Reject `*`/`table.*`, or expand it to the concrete column list (against an allow-list) before the denied-column check.

---

### C-2 — Tables without a tenant rule have no isolation  *(CONFIRMED PASS)*

`checkTenant` only enforces isolation on tables named in a tenant `rowRule` ([tenantChecker.js:182](backend/src/security/sql/tenantChecker.js#L182)). `departments` is in the Manager's `allowedTables` but has **no** tenant rule.

**PoC (Manager):**
```sql
SELECT * FROM departments;            -- every tenant's departments
SELECT * FROM departments WHERE 1=1;  -- same
```

**Evidence:** Extractor → `tables:['departments']`, `filters:[]`; `evaluateSqlSecurity` → **PASS ✅**.

**Impact:** Cross-tenant data disclosure for any allowed table lacking an explicit tenant rule (today `departments`; any future table by default). Also exploitable via JOIN — joined-table rows are never tenant-scoped.

**Fix:** Require an explicit tenant rule for **every** allowed table; fail closed when a referenced table is not covered.

---

### C-3 — `/api/verify-sql` trusts client-supplied `policy` and `user`

[index.js:83](backend/src/index.js#L83) + [validateVerificationRequest](backend/src/index.js#L23) read `policy` and `user` straight from the request body.

**PoC:**
```http
POST /api/verify-sql
{ "user": {"tenantId": 999},
  "sql":  "SELECT * FROM employees",
  "policy": {"allowedTables": ["employees"], "rowRules": []} }
```
→ `PASS`. A caller defines their own permissive policy and identity, defeating the entire engine. (`/api/check-sql` and `/api/query` derive policy server-side and are not affected — but none of the endpoints authenticate the caller.)

**Fix:** Derive `policy`, `user`, and `dialect` server-side from an authenticated session. Never accept them from the body.

---

## 🟠 HIGH

### H-1 — `LOAD_FILE()` and arbitrary functions pass unchecked  *(CONFIRMED PASS)*

Function calls are `exp.Func`/`exp.Anonymous`, not `exp.Column`, so they are invisible to every checker.

**PoC (Manager):**
```sql
SELECT name, LOAD_FILE('/etc/passwd')
FROM employees WHERE tenant_id = 101 AND department_id = 1;
```

**Evidence:** Extractor `columns` → `name, tenant_id, department_id` (no sign of `LOAD_FILE`); `evaluateSqlSecurity` → **PASS ✅**.

**Impact:** On MySQL with `FILE` privilege, arbitrary server-side file read. More broadly, *no* function is subject to any policy — the validator regulates column/table names only.

**Fix:** Add a semantic function deny-list (`LOAD_FILE`, `SLEEP`, `BENCHMARK`, `GET_LOCK`, …) and reject unknown functions by default.

---

### H-2 — `SLEEP()` / resource functions enable time-based DoS  *(CONFIRMED PASS)*

**PoC (Manager):**
```sql
SELECT name FROM employees
WHERE tenant_id = 101 AND department_id = 1 AND SLEEP(5) = 0;
```

**Evidence:** `SLEEP(5)=0` is captured as `{type:'UNSUPPORTED', raw:'SLEEP(5) = 0'}` but, since the two required filters are present as separate `AND` clauses and the raw does **not** contain `tenant_id`, the unsupported clause is ignored → **PASS ✅**.

**Impact:** Attacker-controlled execution time / connection exhaustion. Same vector as H-1 for any side-effecting function.

**Fix:** Treat **any** `UNSUPPORTED` filter as fail-closed (see M-1/M-3), plus the H-1 function deny-list.

---

### H-3 — Attacker-controlled `dialect` (parser differential)

`dialect` is taken from the request ([index.js:38](backend/src/index.js#L38)) and passed to SQLGlot. A caller can select a dialect whose parse differs from the real database engine, so the AST the validator inspects is not the SQL that executes.

**Fix:** Pin `dialect` server-side to the production database.

---

### H-4 — Dead-code validators give false assurance

[postGenValidator.js](backend/src/services/postGenValidator.js) and [checkAccess.js](backend/src/services/checkAccess.js) are never called by the request pipeline. `postGenValidator`'s regex approach is additionally weak: `\b(salary)\b` flags harmless identifiers and misses quoted/aliased ones; `FROM\s+(\w+)` sees only the first table and ignores JOINs/subqueries.

**Fix:** Delete them, or wire a hardened version into `index.js` so the code reflects what actually enforces.

---

## 🟡 MEDIUM

### M-1 — Tenant safety relies on a text regex over `raw`
Compound/unsupported conditions become `{type:'UNSUPPORTED', raw:'…'}`. `checkTenant` only fails these when the **raw string** matches `/tenant_id/i` ([tenantChecker.js:152](backend/src/security/sql/tenantChecker.js#L152)). This is a string heuristic, not a semantic one — fragile against column aliasing, casing, and (per H-2) any non-tenant clause.

### M-2 — String-based value comparison
`valuesEqual` does `String(a).trim() === String(b).trim()` ([tenantChecker.js:16](backend/src/security/sql/tenantChecker.js#L16)). Equivalent-but-differently-rendered literals (`101` vs `101.0` vs `0x65`) fail closed today, but the stringly-typed comparison invites drift between the validated value and the executed value.

### M-3 — Only the top-level `WHERE` is inspected  *(CONFIRMED)*
`extract_filters` reads `expression.args.get('where')` ([extractor.py:336](sqlglot-service/extractor.py#L336)); subquery/CTE `WHERE`s are ignored while their tables are still extracted. This fails closed for reads (missing filter → FAIL) but leaves the validator with an incomplete model — the enabling condition behind C-2's cross-table leaks.

---

## 🟢 LOW

- **L-1 — No authN/authZ on any endpoint** ([index.js:62](backend/src/index.js#L62)); identity is a `userId` string in the body.
- **L-2 — Internal error leakage**: SQLGlot/parse errors returned verbatim ([app.py:135](sqlglot-service/app.py#L135), [inspector.py:55](sqlglot-service/inspector.py#L55)), aiding query shaping.
- **L-3 — Employee `id` rule can never match** *(CONFIRMED)*: `valueFrom:'userId'` resolves to the string `"user-101-employee"`, compared against a numeric `employees.id`. Every employee query fails `ROW_FILTER_MISMATCH` — the control is a correctness bug that happens to fail closed, but masks C-1/H-1/H-2 for employees (they remain fully exploitable for Managers).

---

## Confirmed test matrix

| Query (Manager context) | Expected | Actual |
|---|---|---|
| `SELECT * FROM employees WHERE tenant_id=101 AND department_id=1` | block (salary hidden) | **PASS ❌ bypass** |
| `SELECT * FROM departments` | block (cross-tenant) | **PASS ❌ bypass** |
| `SELECT name, LOAD_FILE('/etc/passwd') FROM employees WHERE tenant_id=101 AND department_id=1` | block | **PASS ❌ bypass** |
| `… AND SLEEP(5)=0` | block | **PASS ❌ bypass** |
| `SELECT salary FROM employees …` | block | FAIL ✅ (BLOCKED_COLUMN) |
| `… tenant_id=102 …` | block | FAIL ✅ (WRONG_TENANT) |
| `… tenant_id=101 AND (department_id=1 OR department_id=2)` | block | FAIL ✅ (ROW_FILTER) |
| `… tenant_id=101 AND id=5 OR region='Kandy'` | block | FAIL ✅ (UNSAFE_TENANT_EXPRESSION) |

---

## Remediation priorities

1. **C-1** — Expand/reject `*` before the column check.
2. **C-2 / M-3** — Mandatory tenant rule per allowed table; fail closed on uncovered tables, subqueries, and CTEs.
3. **C-3 / H-3** — Policy/user/dialect server-side from an authenticated session.
4. **H-1 / H-2** — Function deny-list; treat every `UNSUPPORTED` filter as fail-closed.
5. **H-4 / L-3** — Remove dead validators; fix the employee `id` rule type mismatch.
6. **L-1 / L-2** — Add authentication; stop leaking parser internals.
