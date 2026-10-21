# Tenant ownership registry

`tenant_registry.json` targets the `enterprise_hrms_alpha` database in the supplied
`Dump20261021.sql`. The dump was inspected as schema data; it was not executed or
imported. Every registered column was confirmed against parsed CREATE TABLE DDL
and its NOT NULL constraint and explicit tenant-key annotation.

| Dump classification | Tables | Registry treatment |
| --- | ---: | --- |
| TENANT_OWNED | 47 | Register `tenant_id` |
| TENANT_CONFIG | 3 | Register `tenant_id` |
| TENANT_ROOT | 1 | Register `tenants.tenant_id` |
| SHARED_REFERENCE | 13 | Leave unregistered; no tenant column exists |
| TENANT_DERIVED | 4 | Leave unregistered; ownership requires a parent relationship |
| Total | 68 | 51 direct tenant mappings |

This includes `workforce_capacity`, `job_openings` and `job_positions`. The registry
does not grant table access; the active user policy and schema allowlist must also
permit a query. Restart SQLGlot after changing this file because the service loads
the registry at startup.

The 13 shared reference tables are `competency_catalog`, `countries`, `currencies`,
`employment_types`, `exchange_rates`, `industry_types`, `job_levels`,
`leave_type_catalog`, `payroll_component_catalog`, `public_holidays`,
`qualification_levels`, `skill_catalog` and `standardized_job_categories`.

The four parent-owned tables require these schema relationships:

| Table | Ownership path |
| --- | --- |
| `employee_dependents` | `employee_id` to `employees.employee_id`, then `employees.tenant_id` |
| `employee_emergency_contacts` | `employee_id` to `employees.employee_id`, then `employees.tenant_id` |
| `payroll_components` | `payroll_record_id` to `payroll_records.payroll_record_id`, then `payroll_records.tenant_id` |
| `performance_scores` | `performance_review_id` to `performance_reviews.performance_review_id`, then `performance_reviews.tenant_id` |

The current correction engine supports direct-column mappings only. Queries
referencing these shared or parent-owned tables therefore remain blocked with
`UNKNOWN_TENANT_OWNERSHIP`. Adding a fictitious `tenant_id` or a dotted parent path
to the JSON would not implement ownership enforcement. Shared-reference support
and relationship-based enforcement require separate engine changes.

The former demo entries `attendance`, `designations`, `employee_children`,
`employee_phone_numbers`, `employee_salary`, `payroll`, `payroll_allowances` and
`payroll_deductions` were removed because they do not exist in this dump.
`tenants` now uses `tenant_id`, replacing the older demo's `id` mapping. This
registry should not be reused as an ownership definition for that older schema;
the portable SQLite sample is not a replacement for the enterprise schema.
