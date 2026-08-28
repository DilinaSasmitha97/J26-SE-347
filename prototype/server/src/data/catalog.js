// ---------------------------------------------------------------------------
// Schema catalog. Two jobs:
//   1. feeds the Schema Explorer + admin access controls in the UI
//   2. tells the query engine which columns are sensitive / joinable
// ---------------------------------------------------------------------------

const col = (name, type, role, description, extra = {}) => ({ name, type, role, description, ...extra });

export const CATALOG = {
  retail: {
    engine: 'mysql',
    tables: [
      {
        name: 'orders',
        label: 'Orders',
        description: 'One row per customer order, including cancelled and refunded ones.',
        rowCountKey: 'orders',
        primaryKey: 'order_id',
        columns: [
          col('order_id', 'integer', 'id', 'Primary key of the order.'),
          col('customer_id', 'integer', 'foreign_key', 'References customers.customer_id.'),
          col('order_date', 'date', 'time', 'Date the order was placed.'),
          col('status', 'varchar(20)', 'dimension', 'Completed, Pending, Cancelled or Refunded.'),
          col('channel', 'varchar(20)', 'dimension', 'Where the order came from.'),
          col('shipping_fee', 'numeric(10,2)', 'measure', 'Shipping charged to the customer.'),
          col('total_amount', 'numeric(12,2)', 'measure', 'Order grand total including shipping.', { format: 'currency' }),
        ],
        joins: [{ table: 'customers', on: 'orders.customer_id = customers.customer_id' }],
      },
      {
        name: 'order_items',
        label: 'Order Items',
        description: 'Line items belonging to an order. Grain is one product per order.',
        rowCountKey: 'order_items',
        primaryKey: 'order_item_id',
        columns: [
          col('order_item_id', 'integer', 'id', 'Primary key of the line item.'),
          col('order_id', 'integer', 'foreign_key', 'References orders.order_id.'),
          col('product_id', 'integer', 'foreign_key', 'References products.product_id.'),
          col('quantity', 'integer', 'measure', 'Units sold on this line.'),
          col('unit_price', 'numeric(10,2)', 'measure', 'Price paid per unit after discount.', { format: 'currency' }),
          col('discount', 'numeric(4,2)', 'measure', 'Discount rate applied, 0 to 1.'),
          col('line_total', 'numeric(12,2)', 'measure', 'quantity x unit_price.', { format: 'currency' }),
          col('line_cost', 'numeric(12,2)', 'measure', 'Cost of goods for this line.', { format: 'currency', sensitive: true }),
        ],
        joins: [
          { table: 'orders', on: 'order_items.order_id = orders.order_id' },
          { table: 'products', on: 'order_items.product_id = products.product_id' },
        ],
      },
      {
        name: 'customers',
        label: 'Customers',
        description: 'Registered customers with region and segment attributes.',
        rowCountKey: 'customers',
        primaryKey: 'customer_id',
        columns: [
          col('customer_id', 'integer', 'id', 'Primary key of the customer.'),
          col('customer_name', 'varchar(120)', 'dimension', 'Full name.', { pii: true }),
          col('email', 'varchar(160)', 'dimension', 'Contact email address.', { pii: true }),
          col('phone', 'varchar(40)', 'dimension', 'Contact phone number.', { pii: true }),
          col('region', 'varchar(40)', 'dimension', 'Sales region.'),
          col('country', 'varchar(60)', 'dimension', 'Country of the billing address.'),
          col('segment', 'varchar(20)', 'dimension', 'Consumer, SMB or Enterprise.'),
          col('signup_date', 'date', 'time', 'Date the account was created.'),
          col('is_active', 'boolean', 'dimension', 'Whether the account is still active.'),
        ],
        joins: [{ table: 'orders', on: 'customers.customer_id = orders.customer_id' }],
      },
      {
        name: 'products',
        label: 'Products',
        description: 'Product master with list price and unit cost.',
        rowCountKey: 'products',
        primaryKey: 'product_id',
        columns: [
          col('product_id', 'integer', 'id', 'Primary key of the product.'),
          col('product_name', 'varchar(120)', 'dimension', 'Display name.'),
          col('category', 'varchar(40)', 'dimension', 'Merchandising category.'),
          col('unit_price', 'numeric(10,2)', 'measure', 'Current list price.', { format: 'currency' }),
          col('unit_cost', 'numeric(10,2)', 'measure', 'Landed cost per unit.', { format: 'currency', sensitive: true }),
          col('in_stock', 'integer', 'measure', 'Units currently on hand.'),
          col('discontinued', 'boolean', 'dimension', 'Whether the product is retired.'),
        ],
        joins: [{ table: 'order_items', on: 'products.product_id = order_items.product_id' }],
      },
      {
        name: 'support_tickets',
        label: 'Support Tickets',
        description: 'Customer support cases linked to an order.',
        rowCountKey: 'support_tickets',
        primaryKey: 'ticket_id',
        columns: [
          col('ticket_id', 'integer', 'id', 'Primary key of the ticket.'),
          col('order_id', 'integer', 'foreign_key', 'References orders.order_id.'),
          col('customer_id', 'integer', 'foreign_key', 'References customers.customer_id.'),
          col('subject', 'varchar(120)', 'dimension', 'Reason the ticket was raised.'),
          col('priority', 'varchar(20)', 'dimension', 'Low, Medium, High or Urgent.'),
          col('status', 'varchar(20)', 'dimension', 'Open or Resolved.'),
          col('opened_date', 'date', 'time', 'Date the ticket was opened.'),
          col('resolved_date', 'date', 'time', 'Date the ticket was closed, null if open.'),
          col('satisfaction_score', 'integer', 'measure', 'CSAT score from 1 to 5.'),
        ],
        joins: [{ table: 'customers', on: 'support_tickets.customer_id = customers.customer_id' }],
      },
    ],
  },

  peopleops: {
    engine: 'mysql',
    tables: [
      {
        name: 'employees',
        label: 'Employees',
        description: 'Current and former employees.',
        rowCountKey: 'employees',
        primaryKey: 'employee_id',
        columns: [
          col('employee_id', 'int', 'id', 'Primary key of the employee.'),
          col('full_name', 'varchar(120)', 'dimension', 'Employee full name.', { pii: true }),
          col('department_id', 'int', 'foreign_key', 'References departments.department_id.'),
          col('job_title', 'varchar(80)', 'dimension', 'Current job title.'),
          col('employment_type', 'varchar(20)', 'dimension', 'Full-time, Contract or Part-time.'),
          col('salary', 'decimal(12,2)', 'measure', 'Annual gross salary.', { format: 'currency', sensitive: true }),
          col('hire_date', 'date', 'time', 'Start date.'),
          col('exit_date', 'date', 'time', 'Leaving date, null if still employed.'),
          col('is_active', 'tinyint(1)', 'dimension', 'Whether the employee is still with the company.'),
          col('performance_rating', 'decimal(3,2)', 'measure', 'Latest review score out of 5.', { sensitive: true }),
          col('location', 'varchar(60)', 'dimension', 'Office location.'),
        ],
        joins: [{ table: 'departments', on: 'employees.department_id = departments.department_id' }],
      },
      {
        name: 'departments',
        label: 'Departments',
        description: 'Departments with their annual budget.',
        rowCountKey: 'departments',
        primaryKey: 'department_id',
        columns: [
          col('department_id', 'int', 'id', 'Primary key of the department.'),
          col('department_name', 'varchar(60)', 'dimension', 'Department name.'),
          col('location', 'varchar(60)', 'dimension', 'Primary office.'),
          col('annual_budget', 'decimal(14,2)', 'measure', 'Approved yearly budget.', { format: 'currency' }),
        ],
        joins: [{ table: 'employees', on: 'departments.department_id = employees.department_id' }],
      },
      {
        name: 'leave_requests',
        label: 'Leave Requests',
        description: 'Time-off requests raised by employees.',
        rowCountKey: 'leave_requests',
        primaryKey: 'leave_id',
        columns: [
          col('leave_id', 'int', 'id', 'Primary key of the request.'),
          col('employee_id', 'int', 'foreign_key', 'References employees.employee_id.'),
          col('leave_type', 'varchar(20)', 'dimension', 'Annual, Sick, Unpaid or Parental.'),
          col('start_date', 'date', 'time', 'First day of leave.'),
          col('days_taken', 'int', 'measure', 'Number of days requested.'),
          col('status', 'varchar(20)', 'dimension', 'Approved, Pending or Rejected.'),
        ],
        joins: [{ table: 'employees', on: 'leave_requests.employee_id = employees.employee_id' }],
      },
    ],
  },
};

export function getCatalog(connectionId) {
  return CATALOG[connectionId] || null;
}
