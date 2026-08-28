import { randomUUID } from 'node:crypto';

// ---------------------------------------------------------------------------
// In-memory application state. A real deployment would keep all of this in the
// control-plane database; keeping it in a module makes the demo resettable and
// dependency free. Everything here is mutable at runtime through the admin API.
// ---------------------------------------------------------------------------

export const USERS = [
  {
    id: 'u_admin',
    name: 'Dewmini Navodya',
    email: 'admin@gmail.com',
    password: 'demo1234',
    role: 'owner',
    initials: 'DN',
    avatarUrl: '/avatars/admin.jpg',
    lastActive: '2026-06-30T08:12:00Z',
  },
  {
    id: 'u_viewer',
    name: 'Sara Lewis',
    email: 'vonara@gmail.com',
    password: 'demo1234',
    role: 'viewer',
    initials: 'SL',
    avatarUrl: '/avatars/viewer.jpg',
    lastActive: '2026-06-24T11:05:00Z',
  },
];

const defaultSettings = () => ({
  // Query behaviour
  max_rows: 500,
  timeout_ms: 15000,
  exclude_cancelled: true,
  active_only: true,
  allow_joins: true,

  // Governance
  mask_pii: 'mask', // 'off' | 'mask' | 'block'
  hide_sensitive_metrics: false,
  blocked_tables: [],

  // Answer presentation
  auto_chart: true,
  show_sql: true,
  show_reasoning: true,
  narrative_style: 'balanced', // 'concise' | 'balanced' | 'detailed'

  // Model (cosmetic in the demo, real in production)
  model: 'claude-sonnet-5',
  temperature: 0,

  // Business glossary: admin-defined synonyms applied before parsing
  glossary: [
    { id: 'g1', term: 'top line', maps_to: 'revenue' },
    { id: 'g2', term: 'gmv', maps_to: 'revenue' },
    { id: 'g3', term: 'basket', maps_to: 'average order value' },
  ],
});

export const CONNECTIONS = [
  {
    id: 'retail',
    name: 'NorthWind Retail',
    engine: 'mysql',
    host: 'db-prod-01.northwind.internal',
    port: 3306,
    database: 'retail_warehouse',
    username: 'askdb_reader',
    password: '••••••••••••',
    ssl: true,
    poolSize: 10,
    status: 'connected',
    readOnly: true,
    createdAt: '2026-02-14T09:00:00Z',
    lastSyncedAt: '2026-06-30T07:45:00Z',
    settings: defaultSettings(),
  },
  {
    id: 'peopleops',
    name: 'PeopleOps HR',
    engine: 'mysql',
    host: 'hr-db.internal',
    port: 3306,
    database: 'peopleops',
    username: 'askdb_hr',
    password: '••••••••••••',
    ssl: true,
    poolSize: 5,
    status: 'connected',
    readOnly: true,
    createdAt: '2026-04-02T13:20:00Z',
    lastSyncedAt: '2026-06-29T22:10:00Z',
    settings: {
      ...defaultSettings(),
      mask_pii: 'mask',
      hide_sensitive_metrics: true,
      glossary: [{ id: 'g1', term: 'attrition', maps_to: 'headcount' }],
    },
  },
  {
    id: 'billing',
    name: 'Billing (Staging)',
    engine: 'mysql',
    host: 'billing-staging.internal',
    port: 3306,
    database: 'billing',
    username: 'askdb_reader',
    password: '••••••••••••',
    ssl: false,
    poolSize: 5,
    status: 'disconnected',
    readOnly: true,
    createdAt: '2026-06-11T10:30:00Z',
    lastSyncedAt: null,
    statusMessage: 'Connection refused: check the host allowlist and credentials.',
    settings: defaultSettings(),
  },
];

export const HISTORY = [];
export const AUDIT = [];

export function getConnection(id) {
  return CONNECTIONS.find((c) => c.id === id) || null;
}

export function addHistory(entry) {
  const record = { id: randomUUID(), askedAt: new Date().toISOString(), ...entry };
  HISTORY.unshift(record);
  if (HISTORY.length > 200) HISTORY.pop();
  return record;
}

export function addAudit(entry) {
  const record = { id: randomUUID(), at: new Date().toISOString(), ...entry };
  AUDIT.unshift(record);
  if (AUDIT.length > 200) AUDIT.pop();
  return record;
}

// A few pre-seeded rows so History and the audit log are not empty on a fresh
// demo run.
export function seedActivity() {
  const seeds = [
    ['What was our revenue last quarter?', 'retail', 'Sara Lewis', 42, '$1.31M'],
    ['Top 5 products by revenue this year', 'retail', 'Sara Lewis', 71, 'Aurora Laptop Pro 16'],
    ['Show revenue by month over the last 12 months', 'retail', 'Dewmini Navodya', 63, '+18.4%'],
    ['Average order value by region', 'retail', 'Sara Lewis', 38, 'Middle East'],
    ['Headcount by department', 'peopleops', 'Dewmini Navodya', 21, 'Engineering'],
  ];
  const now = Date.now();
  seeds.forEach((s, i) => {
    HISTORY.push({
      id: randomUUID(),
      askedAt: new Date(now - (i + 1) * 3600 * 1000 * 5).toISOString(),
      question: s[0],
      connectionId: s[1],
      user: s[2],
      executionMs: s[3],
      headline: s[4],
      status: 'ok',
      seeded: true,
    });
  });

  AUDIT.push(
    { id: randomUUID(), at: new Date(now - 7200000).toISOString(), actor: 'Dewmini Navodya', action: 'settings.updated', detail: 'PII masking set to "mask" on NorthWind Retail' },
    { id: randomUUID(), at: new Date(now - 86400000).toISOString(), actor: 'Dewmini Navodya', action: 'connection.created', detail: 'Added connection "Billing (Staging)"' },
    { id: randomUUID(), at: new Date(now - 172800000).toISOString(), actor: 'Dewmini Navodya', action: 'user.invited', detail: 'Invited vonara@gmail.com as Viewer' },
  );
}
