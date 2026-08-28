import alasql from 'alasql';
import { buildRetail } from '../data/retail.js';
import { buildHr } from '../data/hr.js';

// ---------------------------------------------------------------------------
// Executes generated SQL against in-memory tables.
//
// alasql gives us a genuine SQL engine in pure JS, so the SQL shown in the UI
// is the SQL that actually ran - nothing is faked. Swapping this module for a
// real pg/mysql pool is the only change needed to point the demo at a live
// database.
// ---------------------------------------------------------------------------

const DATABASES = {};

// Date buckets are precomputed at load time so the planner never needs
// engine-specific date functions.
function isoWeek(dateStr) {
  const d = new Date(dateStr + 'T00:00:00Z');
  const target = new Date(d.getTime());
  const dayNr = (d.getUTCDay() + 6) % 7;
  target.setUTCDate(target.getUTCDate() - dayNr + 3);
  const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4));
  const diff = target - firstThursday;
  const week = 1 + Math.round(diff / (7 * 86400000));
  return `${target.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

function decorateRetail(data) {
  for (const o of data.orders) {
    const [y, m] = o.order_date.split('-');
    o.order_month = `${y}-${m}`;
    o.order_year = y;
    o.order_quarter = `${y}-Q${Math.floor((parseInt(m, 10) - 1) / 3) + 1}`;
    o.order_week = isoWeek(o.order_date);
  }
  return data;
}

function decorateHr(data) {
  for (const e of data.employees) {
    const [y, m] = e.hire_date.split('-');
    e.hire_month = `${y}-${m}`;
    e.hire_year = y;
  }
  return data;
}

const BUILDERS = {
  retail: () => decorateRetail(buildRetail()),
  peopleops: () => decorateHr(buildHr()),
};

function ensureDatabase(connectionId) {
  if (DATABASES[connectionId]) return DATABASES[connectionId];
  const builder = BUILDERS[connectionId];
  if (!builder) throw new Error(`No dataset registered for connection "${connectionId}"`);

  const data = builder();
  const db = new alasql.Database(`db_${connectionId}`);
  for (const [table, rows] of Object.entries(data)) {
    db.exec(`CREATE TABLE ${table}`);
    db.tables[table].data = rows;
  }
  DATABASES[connectionId] = { db, data, rowCounts: Object.fromEntries(Object.entries(data).map(([k, v]) => [k, v.length])) };
  return DATABASES[connectionId];
}

export function getRowCounts(connectionId) {
  try {
    return ensureDatabase(connectionId).rowCounts;
  } catch {
    return {};
  }
}

export function getSampleRows(connectionId, table, limit = 8) {
  const { data } = ensureDatabase(connectionId);
  const rows = data[table] || [];
  return rows.slice(0, limit);
}

const maskName = (name) => {
  const parts = String(name).split(' ');
  return parts.length > 1 ? `${parts[0]} ${parts[1][0]}.` : String(name);
};

export function execute(sql, connectionId, plan, settings = {}) {
  const { db } = ensureDatabase(connectionId);
  const started = process.hrtime.bigint();
  let rows = db.exec(sql);
  const elapsed = Number(process.hrtime.bigint() - started) / 1e6;

  if (!Array.isArray(rows)) rows = [];

  // "value" is a reserved word in the SQL dialect, so the generated query
  // aliases the measure as metric_value. Normalise it back for the client.
  rows = rows.map((r) => Object.fromEntries(
    Object.entries(r).map(([k, v]) => [k === 'metric_value' ? 'value' : k, v])
  ));

  // Admin setting: PII columns can be masked on the way out.
  if (plan && plan.dimension && plan.dimension.pii && settings.mask_pii === 'mask') {
    rows = rows.map((r) => ({ ...r, label: maskName(r.label) }));
  }

  return {
    rows,
    rowCount: rows.length,
    executionMs: Math.round(elapsed * 100) / 100,
  };
}

// Warm both datasets so the first question is not slower than the rest.
export function warmUp() {
  for (const id of Object.keys(BUILDERS)) ensureDatabase(id);
}
