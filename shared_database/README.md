# 🏢 Shared Multi-Tenant HR & Payroll Database

**Project:** Secure Multi-Tenant Natural Language Interface for Database Querying (J26-SE-347)  
**Standard Database Specification:** MySQL 8.x + Portable SQLite Dual-Engine  
**Total Records:** 3,062 rows across 14 tables  
**Active Tenants:** Tenant 101 (*Apex Technologies*) & Tenant 102 (*Nova Holdings*)

---

## 📋 1. Alignment with Research TAF Mandate
As specified in **Section 8 (Data Availability and Collection Strategy, Page 6)** of our signed Topic Assessment Form:
> *"To stress-test the multi-tenant security middleware, PII masking, and prediction engines, the team will generate extensive synthetic MySQL databases simulating realistic **Sales, HR, and Finance environments** with varying degrees of statistical noise and volatility."*

This database represents our project's standardized **HR & Finance (Payroll)** multi-tenant test environment.

---

## 🏛️ 2. Tenant Boundaries & Partition Keys
Every business table is strictly partitioned by `tenant_id BIGINT NOT NULL` referencing `tenants(id)`:

| Tenant ID | Company Name | Code | Primary Domain / Contact | Employee ID Range |
| :---: | :--- | :---: | :--- | :---: |
| **101** | Apex Technologies | `APEX` | `hr@apex.example.com` (Colombo) | `1001` – `1060` |
| **102** | Nova Holdings | `NOVA` | `hr@nova.example.com` (Kandy) | `2001` – `2060` |

---

## 🗄️ 3. Table Catalog (14 Interconnected Tables)

1. **`tenants`** (2 rows): Core multi-tenant catalog (`id`, `name`, `code`, `email`, `phone`, `address`).
2. **`departments`** (100 rows): Organizational divisions (`id`, `tenant_id`, `name`, `code`, `description`).
3. **`designations`** (100 rows): Job roles and seniority levels (`id`, `tenant_id`, `title`, `code`, `level_no`).
4. **`employees`** (120 rows): Workforce directory (`id`, `tenant_id`, `employee_no`, `department_id`, `designation_id`, `first_name`, `last_name`, `gender`, `joined_date`, `nic_number` [PII], `passport_number` [PII], `work_email` [PII], `personal_email` [PII], `city`, `district`).
5. **`employee_phone_numbers`** (240 rows): Telecom contacts (`id`, `tenant_id`, `employee_id`, `phone_type`, `phone_number` [PII]).
6. **`employee_children`** (120 rows): Dependent family records (`id`, `tenant_id`, `employee_id`, `first_name`, `last_name`, `date_of_birth`).
7. **`employee_bank_accounts`** (120 rows): Financial routing (`id`, `tenant_id`, `employee_id`, `bank_name`, `branch_name`, `account_number` [PII], `account_holder_name` [PII]).
8. **`employee_salary`** (120 rows): Compensation contracts (`id`, `tenant_id`, `employee_id`, `basic_salary`, `fixed_allowance`, `transport_allowance`, `meal_allowance`, `currency`).
9. **`attendance`** (1,200 rows): Daily workforce tracking (`id`, `tenant_id`, `employee_id`, `attendance_date`, `check_in_time`, `check_out_time`, `work_minutes`, `late_minutes`, `attendance_status`).
10. **`overtime_records`** (120 rows): Approved overtime claims (`id`, `tenant_id`, `employee_id`, `overtime_date`, `ot_hours`, `hourly_rate`, `ot_amount`, `approval_status`).
11. **`payroll_periods`** (100 rows): Monthly accounting cycles (`id`, `tenant_id`, `year_no`, `month_no`, `period_start`, `period_end`, `payment_date`, `status`).
12. **`payroll`** (240 rows): Processed disbursements (`id`, `tenant_id`, `payroll_period_id`, `employee_id`, `basic_salary`, `overtime_amount`, `bonus_amount`, `gross_salary`, `epf_employee`, `tax_amount`, `net_salary`).
13. **`payroll_allowances`** (240 rows): Itemized earnings (`id`, `tenant_id`, `payroll_id`, `employee_id`, `allowance_type`, `amount`).
14. **`payroll_deductions`** (240 rows): Itemized withholdings (`id`, `tenant_id`, `payroll_id`, `employee_id`, `deduction_type`, `amount`).

---

## 🤝 4. Responsibilities Across All 4 Members

### Member 1: Sasmitha (NL-to-SQL Engine & Schema Intelligence)
* Prunes 14 tables down to only relevant subsets per natural language query.
* Maps multi-hop joins (e.g. `employees` &rarr; `departments` &rarr; `payroll`).
* Generates dialect-valid SQL conforming to user intent and Member 3's `injected_rules`.

### Member 2: Dewmini (AST Security & PII Protection)
* Scans AST to block destructive commands (`DROP TABLE`, `UPDATE employee_salary`).
* Dynamically detects and masks PII fields: `nic_number`, `passport_number`, `work_email`, `personal_email`, `phone_number`, `account_number`.

### Member 3: Jinajith (Access Control & Multi-Tenant Isolation)
* Validates user JWT claims (`sub`, `tenant_id`).
* Injects prompt grounding constraints (e.g. `STRICT: Filter all tables by tenant_id = 101`).
* Verifies zero cross-tenant leakage: queries by Tenant 101 never return rows from Tenant 102.

### Member 4: Vonara (Visualization, Analytics & Forecasting)
* Generates Vega-Lite charts using time-series fields (`payroll_periods.payment_date`, `attendance.attendance_date`) and numeric metrics (`net_salary`, `gross_salary`, `ot_amount`).
* Runs SARIMA / forecasting models on quarterly payroll trends.

---

## 💻 5. How to Run & Connect

### Option A: MySQL 8.x (Target Production Engine)
```bash
mysql -u root -p < shared_database/multitenant_hr_sample.sql
```
Connect via connection string:
`mysql+pymysql://root:password@localhost:3306/multi_tenant_hr`

### Option B: Portable SQLite (Zero-Setup Engine)
A pre-built SQLite file is ready at:
`shared_database/multitenant_hr.db`

In Python:
```python
import sqlite3
conn = sqlite3.connect("shared_database/multitenant_hr.db")
cursor = conn.cursor()
cursor.execute("SELECT first_name, last_name, work_email FROM employees WHERE tenant_id = 101 LIMIT 5;")
print(cursor.fetchall())
```
