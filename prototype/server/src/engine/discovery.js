// ---------------------------------------------------------------------------
// Schema discovery review.
//
// After a database is connected, a real system reads the schema, infers what
// it can, and is left with a pile of things it genuinely cannot work out from
// names and types alone: cryptic columns, status codes, which of three amount
// columns is "revenue", whether a loosely named column is really a foreign
// key. Those become questions for the person who owns the database.
//
// Answering them is what turns a raw schema into a semantic model, so the
// questions below mirror the ones that actually block a text-to-SQL system.
// ---------------------------------------------------------------------------

const QUESTIONS = [
  {
    id: 'q_cd_count',
    kind: 'text',
    table: 'orders',
    column: 'cd_count',
    type: 'int(11)',
    samples: ['1', '3', '2', '5', '1', '2'],
    title: 'What does cd_count mean?',
    context: 'A whole number on every order, usually between 1 and 6. The name does not match anything else in the schema.',
    why: 'Until this is named, nobody can ask questions about it and it will be left out of answers.',
    placeholder: 'e.g. number of distinct products in the order',
  },
  {
    id: 'q_status_codes',
    kind: 'text',
    table: 'orders',
    column: 'sts',
    type: 'char(1)',
    samples: ['A', 'P', 'X', 'A', 'R', 'A'],
    title: 'What do the codes in sts stand for?',
    context: 'Only five values are ever used: A, P, X, R and H.',
    why: 'People will ask about “cancelled” or “completed” orders in words, not letter codes.',
    placeholder: 'e.g. A = Approved, P = Pending, X = Cancelled, R = Refunded, H = On hold',
  },
  {
    id: 'q_revenue_column',
    kind: 'choice',
    table: 'orders',
    column: null,
    title: 'Which column should “revenue” mean?',
    context: 'Three money columns sit on the orders table and they hold different totals.',
    why: 'Revenue is the most asked-about figure. Picking the wrong column makes every sales answer wrong.',
    options: [
      { value: 'gross_amt', label: 'gross_amt', hint: 'Before discounts and tax' },
      { value: 'net_amt', label: 'net_amt', hint: 'After discounts, before tax' },
      { value: 'ord_total', label: 'ord_total', hint: 'Final charged total including shipping and tax' },
    ],
  },
  {
    id: 'q_date_column',
    kind: 'choice',
    table: 'orders',
    column: null,
    title: 'Which date should “when” questions use?',
    context: 'The orders table carries three dates: dt_created, dt_confirmed and dt_shipped.',
    why: 'Questions like “revenue last month” need one agreed date to filter and group by.',
    options: [
      { value: 'dt_created', label: 'dt_created', hint: 'When the order was placed' },
      { value: 'dt_confirmed', label: 'dt_confirmed', hint: 'When payment cleared' },
      { value: 'dt_shipped', label: 'dt_shipped', hint: 'When it left the warehouse' },
    ],
  },
  {
    id: 'q_relationship',
    kind: 'confirm',
    table: 'orders',
    column: 'cust_ref',
    type: 'varchar(24)',
    samples: ['C-10428', 'C-10429', 'C-11002'],
    title: 'Does orders.cust_ref point at customers.cust_code?',
    context: 'The values line up, but the database has no foreign key declared between these two tables.',
    why: 'Without this link, no question can combine order figures with customer details like region or segment.',
    confirmLabel: 'Yes, they are linked',
    denyLabel: 'No, unrelated',
  },
  {
    id: 'q_quantity',
    kind: 'choice',
    table: 'order_lines',
    column: null,
    title: 'Which quantity means “units sold”?',
    context: 'Order lines hold both qty_ordered and qty_shipped, and they often differ.',
    why: '“How many units did we sell” has to resolve to exactly one of these.',
    options: [
      { value: 'qty_ordered', label: 'qty_ordered', hint: 'What the customer asked for' },
      { value: 'qty_shipped', label: 'qty_shipped', hint: 'What actually went out' },
    ],
  },
  {
    id: 'q_backup_table',
    kind: 'confirm',
    table: 'orders_bkp_2024',
    column: null,
    title: 'Should orders_bkp_2024 be included in answers?',
    context: 'This table looks like a backup copy of orders. It has 41,882 rows and has not changed in 14 months.',
    why: 'If it is included, totals will be double counted.',
    confirmLabel: 'Include it',
    denyLabel: 'Leave it out',
    defaultAnswer: false,
  },
  {
    id: 'q_pii',
    kind: 'confirm',
    table: 'customers',
    column: 'contact_1',
    type: 'varchar(120)',
    samples: ['nimal.perera@…', '+94-77-…'],
    title: 'Does customers.contact_1 hold personal details?',
    context: 'Values look like a mix of email addresses and phone numbers.',
    why: 'Personal details get masked in answers unless you say otherwise.',
    confirmLabel: 'Yes, treat as personal',
    denyLabel: 'No, it is not personal',
    defaultAnswer: true,
  },
];

// A plausible scan result. Deterministic per connection id so a refresh does
// not reshuffle the numbers mid-demo.
function hash(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  return Math.abs(h);
}

export function buildReview(connection) {
  const h = hash(connection.id);
  return {
    scan: {
      tables: 12 + (h % 9),
      columns: 96 + (h % 60),
      relationships: 8 + (h % 7),
      rows: 120000 + (h % 400000),
      flagged: QUESTIONS.length,
    },
    questions: QUESTIONS,
  };
}

// Answers become semantic-layer entries. In a full build these would extend the
// metric and dimension definitions; here they are recorded on the connection
// and folded into its glossary so the effect is visible.
export function applyAnswers(connection, answers = {}) {
  const glossary = connection.settings.glossary || [];
  const additions = [];

  const revenue = answers.q_revenue_column;
  if (revenue) additions.push({ id: `g_${Date.now()}_rev`, term: 'revenue', maps_to: revenue });

  const qty = answers.q_quantity;
  if (qty) additions.push({ id: `g_${Date.now()}_qty`, term: 'units sold', maps_to: qty });

  const cd = answers.q_cd_count;
  if (cd && String(cd).trim()) {
    additions.push({ id: `g_${Date.now()}_cd`, term: 'cd_count', maps_to: String(cd).trim() });
  }

  connection.settings.glossary = [...glossary, ...additions];

  if (answers.q_backup_table === false) {
    const blocked = connection.settings.blocked_tables || [];
    if (!blocked.includes('orders_bkp_2024')) {
      connection.settings.blocked_tables = [...blocked, 'orders_bkp_2024'];
    }
  }
  if (answers.q_pii === false) {
    // Owner says it is not personal, so leave masking as configured.
  }

  connection.review = {
    completed: true,
    completedAt: new Date().toISOString(),
    answers,
    answered: Object.keys(answers).length,
    total: QUESTIONS.length,
  };
  return connection.review;
}
