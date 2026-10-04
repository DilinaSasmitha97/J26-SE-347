-- Synthetic multi-tenant business database for Component 4 integration tests.
--
-- Tables hold individual TRANSACTIONS (one invoice, one sale, one ticket), not
-- monthly totals, so the fixture queries must aggregate with GROUP BY exactly
-- as Member 1's generated SQL would. Every table carries tenant_id; tenant
-- scoping is written into each fixture query, standing in for Member 3.
--
-- Column names match synthetic_data.SCHEMA_DDL, so this file is also passed to
-- the query analyzer as schema metadata. Keep each definition free of
-- trailing table options (ENGINE=..., CHARSET=...): the analyzer's DDL parser
-- expects the closing parenthesis to be followed directly by a semicolon.

DROP TABLE IF EXISTS expenses;
DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS support_tickets;

CREATE TABLE expenses (
    expense_id INT NOT NULL,
    tenant_id VARCHAR(32) NOT NULL,
    invoice_date DATE NOT NULL,
    category VARCHAR(64) NOT NULL,
    vendor VARCHAR(128) NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    approved_by_email VARCHAR(128),
    PRIMARY KEY (expense_id),
    INDEX idx_expenses_tenant_date (tenant_id, invoice_date)
);

CREATE TABLE sales (
    sale_id INT NOT NULL,
    tenant_id VARCHAR(32) NOT NULL,
    sale_date DATE NOT NULL,
    region VARCHAR(64) NOT NULL,
    product VARCHAR(64) NOT NULL,
    units INT NOT NULL,
    revenue DECIMAL(12,2) NOT NULL,
    PRIMARY KEY (sale_id),
    INDEX idx_sales_tenant_date (tenant_id, sale_date)
);

CREATE TABLE employees (
    employee_id INT NOT NULL,
    tenant_id VARCHAR(32) NOT NULL,
    full_name VARCHAR(128) NOT NULL,
    email VARCHAR(128) NOT NULL,
    department VARCHAR(64) NOT NULL,
    hire_date DATE NOT NULL,
    salary DECIMAL(12,2) NOT NULL,
    PRIMARY KEY (employee_id),
    INDEX idx_employees_tenant (tenant_id)
);

CREATE TABLE support_tickets (
    ticket_id INT NOT NULL,
    tenant_id VARCHAR(32) NOT NULL,
    opened_date DATE NOT NULL,
    priority VARCHAR(16) NOT NULL,
    resolution_hours DECIMAL(8,2) NOT NULL,
    customer_phone VARCHAR(32),
    PRIMARY KEY (ticket_id),
    INDEX idx_tickets_tenant_date (tenant_id, opened_date)
);
