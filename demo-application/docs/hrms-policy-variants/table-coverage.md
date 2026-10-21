# Complete table coverage

Every one of the 68 tables is listed. Allowed means policy-authorized after the compatibility prerequisites in README; it does not mean the current app can execute the table. All four inherited tables are denied. All shared tables await verifier support.

| Table | Ownership | Employee | Manager | Administrator |
|---|---|---|---|---|
| `applications` | TENANT_OWNED | DENY | DENY | Tenant |
| `attendance_adjustments` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `attendance_records` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `bonuses` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `candidates` | TENANT_OWNED | DENY | DENY | Tenant |
| `certifications` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `company_locations` | TENANT_OWNED | Tenant | Tenant | Tenant |
| `compensation_adjustments` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `competency_catalog` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `cost_centers` | TENANT_OWNED | DENY | Tenant | Tenant |
| `countries` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `currencies` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `deductions` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `department_hierarchy` | TENANT_OWNED | DENY | DENY | Tenant |
| `department_managers` | TENANT_OWNED | DENY | Tenant; department_id=claim:departmentId | Tenant |
| `departments` | TENANT_OWNED | Tenant | Tenant; department_id=claim:departmentId | Tenant |
| `employee_addresses` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `employee_bank_accounts` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `employee_contacts` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `employee_contracts` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `employee_dependents` | TENANT_DERIVED | DENY — inherited ownership pending | DENY — inherited ownership pending | DENY — inherited ownership pending |
| `employee_documents_metadata` | TENANT_OWNED | Tenant; employee_id=claim:employeeId; is_confidential=0 | DENY | Tenant |
| `employee_emergency_contacts` | TENANT_DERIVED | DENY — inherited ownership pending | DENY — inherited ownership pending | DENY — inherited ownership pending |
| `employee_kpis` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `employee_reporting_structure` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `employee_skills` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `employee_training` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `employees` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | Tenant; department_id=claim:departmentId | Tenant |
| `employment_history` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | Tenant; department_id=claim:departmentId | Tenant |
| `employment_types` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `exchange_rates` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `hiring_decisions` | TENANT_OWNED | DENY | DENY | Tenant |
| `industry_types` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `interview_records` | TENANT_OWNED | DENY | DENY | Tenant |
| `job_levels` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `job_openings` | TENANT_OWNED | DENY | Tenant; department_id=claim:departmentId | Tenant |
| `job_positions` | TENANT_OWNED | Tenant | Tenant | Tenant |
| `leave_approvals` | TENANT_OWNED | DENY | DENY | Tenant |
| `leave_balances` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `leave_entitlements` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `leave_policies` | TENANT_CONFIG | Tenant | Tenant | Tenant |
| `leave_requests` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `leave_type_catalog` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `overtime_records` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `payroll_component_catalog` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `payroll_components` | TENANT_DERIVED | DENY — inherited ownership pending | DENY — inherited ownership pending | DENY — inherited ownership pending |
| `payroll_periods` | TENANT_OWNED | DENY | DENY | Tenant |
| `payroll_records` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | Tenant; department_id=claim:departmentId | Tenant |
| `performance_goals` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `performance_reviews` | TENANT_OWNED | Tenant; employee_id=claim:employeeId; review_status=FINALIZED | Tenant; department_id=claim:departmentId; review_status=FINALIZED | Tenant |
| `performance_scores` | TENANT_DERIVED | DENY — inherited ownership pending | DENY — inherited ownership pending | DENY — inherited ownership pending |
| `position_skill_requirements` | TENANT_CONFIG | Tenant | Tenant | Tenant |
| `project_assignments` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `project_resource_allocations` | TENANT_OWNED | DENY | Tenant; department_id=claim:departmentId | Tenant |
| `projects` | TENANT_OWNED | DENY | Tenant; owning_department_id=claim:departmentId | Tenant |
| `promotion_history` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `public_holidays` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `qualification_levels` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `salary_history` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `shift_assignments` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `skill_catalog` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `standardized_job_categories` | SHARED_REFERENCE | Global reference; verifier pending | Global reference; verifier pending | Global reference; verifier pending |
| `teams` | TENANT_OWNED | Tenant | Tenant; department_id=claim:departmentId | Tenant |
| `tenants` | TENANT_ROOT | Tenant | Tenant | Tenant |
| `timesheets` | TENANT_OWNED | Tenant; employee_id=claim:employeeId | DENY | Tenant |
| `training_programs` | TENANT_OWNED | Tenant | Tenant | Tenant |
| `work_shifts` | TENANT_CONFIG | Tenant | Tenant | Tenant |
| `workforce_capacity` | TENANT_OWNED | DENY | Tenant; department_id=claim:departmentId | Tenant |

All applicable column denials still apply to allowed tables. Their exact qualified names are in each policy JSON. The accompanying schema inventory records all 601 column definitions, keys, checks, and 138 declared foreign keys.
