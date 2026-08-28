// ---------------------------------------------------------------------------
// The semantic layer. Everything the planner is allowed to build a query from
// lives here: metrics, dimensions and the literal values it can filter on.
//
// Each metric carries two expressions because the grain of the FROM clause
// changes the correct aggregate:
//   orderGrain - used when we are querying orders (one row per order)
//   itemGrain  - used when order_items is joined in (one row per product line)
// A metric with orderGrain === null forces the item-level join.
// ---------------------------------------------------------------------------

export const SEMANTIC = {
  retail: {
    base: 'orders',
    metrics: [
      {
        id: 'revenue',
        label: 'Revenue',
        keywords: ['revenue', 'sales', 'sold', 'turnover', 'income', 'earnings', 'money', 'total amount', 'gmv'],
        orderGrain: 'ROUND(SUM(o.total_amount), 2)',
        itemGrain: 'ROUND(SUM(oi.line_total), 2)',
        format: 'currency',
        description: 'the sum of order totals',
      },
      {
        id: 'order_count',
        label: 'Orders',
        keywords: ['orders', 'order count', 'number of orders', 'how many orders', 'purchases', 'transactions'],
        orderGrain: 'COUNT(*)',
        itemGrain: 'COUNT(DISTINCT o.order_id)',
        format: 'number',
        description: 'the number of orders placed',
      },
      {
        id: 'customer_count',
        label: 'Customers',
        keywords: ['customers', 'buyers', 'shoppers', 'how many customers', 'unique customers', 'clients'],
        orderGrain: 'COUNT(DISTINCT o.customer_id)',
        itemGrain: 'COUNT(DISTINCT o.customer_id)',
        format: 'number',
        description: 'the number of distinct customers who ordered',
      },
      {
        id: 'aov',
        label: 'Average Order Value',
        keywords: ['average order value', 'aov', 'average order', 'avg order', 'basket size', 'average spend', 'average basket'],
        orderGrain: 'ROUND(AVG(o.total_amount), 2)',
        itemGrain: 'ROUND(SUM(oi.line_total) / COUNT(DISTINCT o.order_id), 2)',
        format: 'currency',
        description: 'average revenue per order',
      },
      {
        id: 'units',
        label: 'Units Sold',
        keywords: ['units', 'quantity', 'items sold', 'units sold', 'how many units', 'volume', 'pieces'],
        orderGrain: null,
        itemGrain: 'SUM(oi.quantity)',
        format: 'number',
        description: 'the total quantity of units sold',
      },
      {
        id: 'profit',
        label: 'Gross Profit',
        keywords: ['profit', 'margin', 'gross profit', 'earnings after cost', 'contribution'],
        orderGrain: null,
        itemGrain: 'ROUND(SUM(oi.line_total - oi.line_cost), 2)',
        format: 'currency',
        sensitive: true,
        description: 'revenue minus cost of goods sold',
      },
      {
        id: 'margin_pct',
        label: 'Margin %',
        keywords: ['margin percent', 'margin percentage', 'profit margin', 'margin rate'],
        orderGrain: null,
        itemGrain: 'ROUND(100.0 * SUM(oi.line_total - oi.line_cost) / SUM(oi.line_total), 2)',
        format: 'percent',
        sensitive: true,
        description: 'gross profit as a share of revenue',
      },
      {
        id: 'avg_discount',
        label: 'Average Discount',
        keywords: ['discount', 'discounts', 'average discount', 'markdown'],
        orderGrain: null,
        itemGrain: 'ROUND(AVG(oi.discount) * 100, 2)',
        format: 'percent',
        description: 'the mean discount rate applied to line items',
      },
      {
        id: 'ticket_count',
        label: 'Support Tickets',
        keywords: ['tickets', 'ticket', 'support tickets', 'complaints', 'cases', 'support cases'],
        needs: ['tickets'],
        orderGrain: 'COUNT(*)',
        itemGrain: 'COUNT(*)',
        format: 'number',
        description: 'the number of support tickets raised',
      },
      {
        id: 'avg_csat',
        label: 'Average CSAT',
        keywords: ['csat', 'satisfaction', 'satisfaction score', 'customer satisfaction', 'happiness'],
        needs: ['tickets'],
        orderGrain: 'ROUND(AVG(t.satisfaction_score), 2)',
        itemGrain: 'ROUND(AVG(t.satisfaction_score), 2)',
        format: 'decimal',
        description: 'the mean satisfaction score out of 5',
      },
    ],

    dimensions: [
      { id: 'region', label: 'Region', keywords: ['region', 'regions', 'geography', 'area', 'territory'], expr: 'c.region', needs: ['customers'] },
      { id: 'country', label: 'Country', keywords: ['country', 'countries', 'nation', 'market'], expr: 'c.country', needs: ['customers'] },
      { id: 'segment', label: 'Segment', keywords: ['segment', 'segments', 'customer type', 'customer segment'], expr: 'c.segment', needs: ['customers'] },
      { id: 'category', label: 'Category', keywords: ['category', 'categories', 'product type', 'product category', 'department'], expr: 'p.category', needs: ['items', 'products'] },
      { id: 'product', label: 'Product', keywords: ['product', 'products', 'item', 'items', 'sku', 'skus'], expr: 'p.product_name', needs: ['items', 'products'] },
      { id: 'channel', label: 'Channel', keywords: ['channel', 'channels', 'source', 'platform'], expr: 'o.channel', needs: [] },
      { id: 'status', label: 'Order Status', keywords: ['status', 'statuses', 'order status', 'state'], expr: 'o.status', needs: [] },
      { id: 'customer', label: 'Customer', keywords: ['customer', 'customers', 'buyer', 'client'], expr: 'c.customer_name', needs: ['customers'], pii: true },
      { id: 'priority', label: 'Ticket Priority', keywords: ['priority', 'priorities', 'urgency'], expr: 't.priority', needs: ['tickets'] },
      { id: 'ticket_subject', label: 'Ticket Reason', keywords: ['subject', 'reason', 'ticket reason', 'issue type', 'complaint type'], expr: 't.subject', needs: ['tickets'] },
    ],

    // Time grains map onto columns we precompute at load time, so no date
    // functions are needed at query time.
    timeGrains: [
      { id: 'day', label: 'Day', keywords: ['by day', 'daily', 'per day', 'day by day'], expr: 'o.order_date', sort: 'o.order_date' },
      { id: 'week', label: 'Week', keywords: ['by week', 'weekly', 'per week', 'week over week'], expr: 'o.order_week', sort: 'o.order_week' },
      { id: 'month', label: 'Month', keywords: ['by month', 'monthly', 'per month', 'month over month', 'over time', 'trend', 'each month'], expr: 'o.order_month', sort: 'o.order_month' },
      { id: 'quarter', label: 'Quarter', keywords: ['by quarter', 'quarterly', 'per quarter'], expr: 'o.order_quarter', sort: 'o.order_quarter' },
      { id: 'year', label: 'Year', keywords: ['by year', 'yearly', 'per year', 'annually', 'year over year'], expr: 'o.order_year', sort: 'o.order_year' },
    ],

    timeColumn: 'o.order_date',

    // Literal values the planner can recognise directly in the question.
    values: [
      { column: 'c.region', needs: ['customers'], label: 'region', options: ['North America', 'Europe', 'Asia Pacific', 'Middle East'] },
      { column: 'c.country', needs: ['customers'], label: 'country', options: ['United States', 'Canada', 'United Kingdom', 'Germany', 'France', 'Spain', 'Sri Lanka', 'India', 'Singapore', 'Japan', 'Australia', 'UAE', 'Qatar'] },
      { column: 'c.segment', needs: ['customers'], label: 'segment', options: ['Consumer', 'SMB', 'Enterprise'] },
      { column: 'p.category', needs: ['items', 'products'], label: 'category', options: ['Electronics', 'Furniture', 'Stationery', 'Accessories', 'Apparel'] },
      { column: 'o.channel', needs: [], label: 'channel', options: ['Web', 'Mobile App', 'Retail Store', 'Partner'] },
      { column: 'o.status', needs: [], label: 'status', options: ['Completed', 'Pending', 'Cancelled', 'Refunded'] },
      { column: 't.priority', needs: ['tickets'], label: 'priority', options: ['Low', 'Medium', 'High', 'Urgent'] },
    ],
  },

  peopleops: {
    base: 'employees',
    metrics: [
      {
        id: 'headcount',
        label: 'Headcount',
        keywords: ['headcount', 'employees', 'staff', 'people', 'how many employees', 'team size', 'workforce'],
        orderGrain: 'COUNT(*)',
        itemGrain: 'COUNT(*)',
        format: 'number',
        description: 'the number of employees',
      },
      {
        id: 'avg_salary',
        label: 'Average Salary',
        keywords: ['average salary', 'avg salary', 'mean salary', 'average pay', 'average compensation'],
        orderGrain: 'ROUND(AVG(e.salary), 2)',
        itemGrain: 'ROUND(AVG(e.salary), 2)',
        format: 'currency',
        sensitive: true,
        description: 'the mean annual salary',
      },
      {
        id: 'total_salary',
        label: 'Total Payroll',
        keywords: ['payroll', 'total salary', 'salary cost', 'wage bill', 'total compensation'],
        orderGrain: 'ROUND(SUM(e.salary), 2)',
        itemGrain: 'ROUND(SUM(e.salary), 2)',
        format: 'currency',
        sensitive: true,
        description: 'the sum of annual salaries',
      },
      {
        id: 'avg_rating',
        label: 'Average Rating',
        keywords: ['rating', 'performance', 'performance rating', 'review score'],
        orderGrain: 'ROUND(AVG(e.performance_rating), 2)',
        itemGrain: 'ROUND(AVG(e.performance_rating), 2)',
        format: 'decimal',
        sensitive: true,
        description: 'the mean performance review score',
      },
    ],

    dimensions: [
      { id: 'department', label: 'Department', keywords: ['department', 'departments', 'team', 'teams', 'division'], expr: 'd.department_name', needs: ['departments'] },
      { id: 'job_title', label: 'Job Title', keywords: ['title', 'titles', 'job title', 'role', 'roles', 'position'], expr: 'e.job_title', needs: [] },
      { id: 'location', label: 'Location', keywords: ['location', 'locations', 'office', 'city', 'site'], expr: 'e.location', needs: [] },
      { id: 'employment_type', label: 'Employment Type', keywords: ['employment type', 'contract', 'full time', 'part time', 'contract type'], expr: 'e.employment_type', needs: [] },
      { id: 'employee', label: 'Employee', keywords: ['employee', 'employees', 'person', 'name'], expr: 'e.full_name', needs: [], pii: true },
    ],

    timeGrains: [
      { id: 'month', label: 'Month', keywords: ['by month', 'monthly', 'per month', 'over time', 'trend'], expr: 'e.hire_month', sort: 'e.hire_month' },
      { id: 'year', label: 'Year', keywords: ['by year', 'yearly', 'per year', 'annually'], expr: 'e.hire_year', sort: 'e.hire_year' },
    ],

    timeColumn: 'e.hire_date',

    values: [
      { column: 'd.department_name', needs: ['departments'], label: 'department', options: ['Engineering', 'Sales', 'Marketing', 'Customer Support', 'Finance', 'People Ops'] },
      { column: 'e.location', needs: [], label: 'location', options: ['Colombo', 'London', 'Singapore'] },
      { column: 'e.employment_type', needs: [], label: 'employment type', options: ['Full-time', 'Contract', 'Part-time'] },
    ],
  },
};

export function getSemantic(connectionId) {
  return SEMANTIC[connectionId] || null;
}
