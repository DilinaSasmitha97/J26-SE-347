import { getSemantic } from './semantic.js';

// ---------------------------------------------------------------------------
// Question -> query plan.
//
// This is a deterministic semantic parser, not an LLM. For the demo that is a
// feature: it is instant, offline, reproducible, and every decision it makes
// can be shown to the user as a numbered reasoning step. Swapping it for a
// real model later means replacing plan() only - the shape it returns is what
// the rest of the system depends on.
// ---------------------------------------------------------------------------

// The dataset is generated up to this date, so "last month" is resolved
// against it rather than the wall clock.
export const NOW = new Date('2026-06-30T00:00:00Z');

const DAY = 86400000;
const MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july',
  'august', 'september', 'october', 'november', 'december'];
const NUMBER_WORDS = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8,
  nine: 9, ten: 10, eleven: 11, twelve: 12, fifteen: 15, twenty: 20, fifty: 50, hundred: 100,
};

const iso = (d) => d.toISOString().slice(0, 10);
const utc = (y, m, d) => new Date(Date.UTC(y, m, d));

function normalise(text) {
  return ' ' + String(text)
    .toLowerCase()
    .replace(/[‘’]/g, "'")
    .replace(/[^a-z0-9'\-\s/]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim() + ' ';
}

// Keyword matching. Longer keywords win at the same position so "average
// order value" beats "order". For metrics we prefer the *earliest* mention:
// in "sales to enterprise customers" the measure being asked for is sales,
// and "customers" is just describing who.
function matchKeyword(haystack, items, { preferEarliest = false } = {}) {
  let best = null;
  for (const item of items) {
    for (const kw of item.keywords) {
      for (const form of [' ' + kw + ' ', ' ' + kw + 's ']) {
        const index = haystack.indexOf(form);
        if (index === -1) continue;
        const cand = { item, matched: kw, matchedLength: kw.length, index };
        if (!best) { best = cand; continue; }
        const better = preferEarliest
          ? cand.index < best.index || (cand.index === best.index && cand.matchedLength > best.matchedLength)
          : cand.matchedLength > best.matchedLength;
        if (better) best = cand;
      }
    }
  }
  return best;
}

// ---------------------------------------------------------------------------
// Time range parsing
// ---------------------------------------------------------------------------
function quarterStart(d) {
  return utc(d.getUTCFullYear(), Math.floor(d.getUTCMonth() / 3) * 3, 1);
}

export function parseTimeRange(text) {
  const t = text;
  const now = NOW;
  const y = now.getUTCFullYear();
  const m = now.getUTCMonth();

  const rel = t.match(/\b(?:last|past|previous|trailing)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s+(day|week|month|quarter|year)s?\b/);
  if (rel) {
    const n = NUMBER_WORDS[rel[1]] || parseInt(rel[1], 10);
    const unit = rel[2];
    let start;
    if (unit === 'day') start = new Date(now.getTime() - (n - 1) * DAY);
    else if (unit === 'week') start = new Date(now.getTime() - (n * 7 - 1) * DAY);
    else if (unit === 'month') start = utc(y, m - n + 1, 1);
    else if (unit === 'quarter') start = utc(y, Math.floor(m / 3) * 3 - (n - 1) * 3, 1);
    else start = utc(y - n + 1, 0, 1);
    return { start: iso(start), end: iso(now), label: `the last ${n} ${unit}${n > 1 ? 's' : ''}` };
  }

  if (/\b(this|current) month\b/.test(t)) {
    return { start: iso(utc(y, m, 1)), end: iso(now), label: 'this month' };
  }
  if (/\b(last|previous) month\b/.test(t)) {
    return { start: iso(utc(y, m - 1, 1)), end: iso(utc(y, m, 0)), label: 'last month' };
  }
  if (/\b(this|current) quarter\b/.test(t)) {
    return { start: iso(quarterStart(now)), end: iso(now), label: 'this quarter' };
  }
  if (/\b(last|previous) quarter\b/.test(t)) {
    const qs = quarterStart(now);
    return {
      start: iso(utc(qs.getUTCFullYear(), qs.getUTCMonth() - 3, 1)),
      end: iso(new Date(qs.getTime() - DAY)),
      label: 'last quarter',
    };
  }
  if (/\b(this|current) year\b/.test(t) || /\b(ytd|year to date)\b/.test(t)) {
    return { start: iso(utc(y, 0, 1)), end: iso(now), label: 'this year to date' };
  }
  if (/\b(last|previous) year\b/.test(t)) {
    return { start: iso(utc(y - 1, 0, 1)), end: iso(utc(y - 1, 11, 31)), label: 'last year' };
  }
  if (/\b(this|current|last|past) week\b/.test(t)) {
    return { start: iso(new Date(now.getTime() - 6 * DAY)), end: iso(now), label: 'the last 7 days' };
  }
  if (/\b(today|yesterday)\b/.test(t)) {
    const d = /yesterday/.test(t) ? new Date(now.getTime() - DAY) : now;
    return { start: iso(d), end: iso(d), label: /yesterday/.test(t) ? 'yesterday' : 'today' };
  }

  // "in march 2026" / "march 2026" / "in march"
  for (let i = 0; i < MONTHS.length; i++) {
    const re = new RegExp(`\\b${MONTHS[i]}\\b(?:\\s+(\\d{4}))?`);
    const hit = t.match(re);
    if (hit) {
      const year = hit[1] ? parseInt(hit[1], 10) : (i <= m ? y : y - 1);
      return {
        start: iso(utc(year, i, 1)),
        end: iso(utc(year, i + 1, 0)),
        label: `${MONTHS[i][0].toUpperCase() + MONTHS[i].slice(1)} ${year}`,
      };
    }
  }

  const q = t.match(/\bq([1-4])\s*(\d{4})?\b/);
  if (q) {
    const qi = parseInt(q[1], 10) - 1;
    const year = q[2] ? parseInt(q[2], 10) : y;
    return { start: iso(utc(year, qi * 3, 1)), end: iso(utc(year, qi * 3 + 3, 0)), label: `Q${qi + 1} ${year}` };
  }

  const between = t.match(/\bbetween\s+(\d{4}-\d{2}-\d{2})\s+and\s+(\d{4}-\d{2}-\d{2})\b/);
  if (between) {
    return { start: between[1], end: between[2], label: `${between[1]} to ${between[2]}` };
  }

  const since = t.match(/\bsince\s+(\d{4}-\d{2}-\d{2})\b/);
  if (since) return { start: since[1], end: iso(now), label: `since ${since[1]}` };

  const year = t.match(/\b(?:in|during|for)?\s*(20\d{2})\b/);
  if (year) {
    const yy = parseInt(year[1], 10);
    return { start: iso(utc(yy, 0, 1)), end: iso(utc(yy, 11, 31)), label: String(yy) };
  }

  return null;
}

// Default trend windows, aligned to whole buckets so the first and last
// points are complete periods.
function defaultTrendRange(grainId) {
  const now = NOW;
  const y = now.getUTCFullYear();
  const m = now.getUTCMonth();

  if (grainId === 'month') {
    return { start: iso(utc(y, m - 11, 1)), end: iso(now), label: 'the last 12 months' };
  }
  if (grainId === 'quarter') {
    const qStart = Math.floor(m / 3) * 3;
    return { start: iso(utc(y, qStart - 15, 1)), end: iso(now), label: 'the last 6 quarters' };
  }
  if (grainId === 'week') {
    const mondayOffset = (now.getUTCDay() + 6) % 7;
    const monday = new Date(now.getTime() - mondayOffset * DAY);
    return {
      start: iso(new Date(monday.getTime() - 12 * 7 * DAY)),
      end: iso(new Date(monday.getTime() - DAY)),
      label: 'the last 12 complete weeks',
    };
  }
  if (grainId === 'day') {
    return { start: iso(new Date(now.getTime() - 29 * DAY)), end: iso(now), label: 'the last 30 days' };
  }
  return null; // yearly trends run over the full history
}

// The equally long window immediately before the one asked about.
function previousRange(range) {
  const start = new Date(range.start + 'T00:00:00Z');
  const end = new Date(range.end + 'T00:00:00Z');
  const lengthDays = Math.round((end - start) / DAY) + 1;
  const prevEnd = new Date(start.getTime() - DAY);
  const prevStart = new Date(prevEnd.getTime() - (lengthDays - 1) * DAY);
  return { start: iso(prevStart), end: iso(prevEnd), label: 'the preceding period' };
}

// ---------------------------------------------------------------------------
// Limit / sort direction
// ---------------------------------------------------------------------------
function parseLimit(text) {
  const m = text.match(/\b(?:top|bottom|first|last|best|worst)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|twenty|fifty)\b/);
  if (m) return NUMBER_WORDS[m[1]] || parseInt(m[1], 10);
  const n = text.match(/\b(\d+)\s+(?:top|best|worst|biggest|largest|highest|lowest)\b/);
  if (n) return parseInt(n[1], 10);
  return null;
}

const ASC_WORDS = /\b(lowest|worst|bottom|least|smallest|fewest|weakest|poorest|slowest)\b/;
const RANK_WORDS = /\b(top|bottom|best|worst|highest|lowest|most|least|biggest|largest|smallest|ranking|rank|leading|fewest)\b/;
const TREND_WORDS = /\b(trend|trends|over time|growth|grew|declin|month over month|year over year|history|historical|by month|monthly|weekly|daily|quarterly|yearly|each month|per month|evolution|trajectory)\b/;
const LIST_WORDS = /\b(list|show me the|show all|which ones|give me the names|names of|who are)\b/;
const COMPARE_WORDS = /\b(compare|versus|vs|against|difference between)\b/;

// ---------------------------------------------------------------------------
// Main entry point
// ---------------------------------------------------------------------------
export function plan(question, connectionId, settings = {}) {
  const model = getSemantic(connectionId);
  if (!model) return { ok: false, reason: 'unknown_connection' };

  const raw = String(question || '');
  let text = normalise(raw);
  const steps = [];
  const glossaryHits = [];

  // 1. Business glossary - admin-defined synonyms are rewritten first, so the
  //    rest of the parser only ever sees canonical vocabulary.
  const glossary = settings.glossary || [];
  for (const entry of glossary) {
    if (!entry.term || !entry.maps_to) continue;
    const term = normalise(entry.term).trim();
    if (term && text.includes(' ' + term + ' ')) {
      text = text.split(' ' + term + ' ').join(' ' + entry.maps_to.toLowerCase() + ' ');
      glossaryHits.push(entry);
    }
  }
  if (glossaryHits.length) {
    steps.push({
      title: 'Used your business terms',
      detail: glossaryHits.map((g) => `"${g.term}" was read as "${g.maps_to}"`).join(', '),
    });
  }

  // 2. Metric
  const allowedMetrics = model.metrics.filter(
    (m) => !(m.sensitive && settings.hide_sensitive_metrics)
  );
  const metricHit = matchKeyword(text, allowedMetrics, { preferEarliest: true });
  const blockedMetric = !metricHit ? matchKeyword(text, model.metrics.filter((m) => m.sensitive)) : null;

  const metric = metricHit ? metricHit.item : allowedMetrics[0];
  const metricInferred = !metricHit;

  // 3. Dimension
  const allowedDims = model.dimensions.filter((d) => !(d.pii && settings.mask_pii === 'block'));
  let dimensionHit = matchKeyword(text, allowedDims);

  // "by <dimension>" / "per <dimension>" is a much stronger signal than a bare
  // mention, so prefer whatever follows it.
  const byMatch = text.match(/\b(?:by|per|across|for each|grouped by|broken down by|split by)\s+([a-z ]{3,25})/);
  let explicitDim = null;
  if (byMatch) {
    const tail = ' ' + byMatch[1].trim() + ' ';
    explicitDim = matchKeyword(tail, allowedDims);
    if (explicitDim) dimensionHit = explicitDim;
  }

  // A bare noun is not a request to group. "How many customers ordered?" wants
  // one number; "customers by region" and "top customers" want a breakdown.
  // Require an explicit grouping or ranking signal before we group at all.
  const groupingSignal = !!explicitDim
    || RANK_WORDS.test(text)
    || /\b(breakdown|break down|distribution|split|share of|compare)\b/.test(text);
  if (dimensionHit && !groupingSignal) dimensionHit = null;

  // 4. Time grain (only counts when the question really asks for a series)
  const grainHit = matchKeyword(text, model.timeGrains);
  const wantsTrend = TREND_WORDS.test(text);
  let timeGrain = grainHit ? grainHit.item : null;
  if (!timeGrain && wantsTrend) {
    timeGrain = model.timeGrains.find((g) => g.id === 'month') || null;
  }

  // 5. Time range
  let timeRange = parseTimeRange(text);
  let rangeInferred = false;
  if (timeGrain && !timeRange) {
    // A trend with no stated window would otherwise open on a half-empty
    // first bucket and report a meaningless jump. Default to whole buckets.
    timeRange = defaultTrendRange(timeGrain.id);
    rangeInferred = !!timeRange;
  }

  // 6. Literal value filters
  const filters = [];
  for (const group of model.values) {
    for (const option of group.options) {
      const needle = ' ' + option.toLowerCase() + ' ';
      if (text.includes(needle)) {
        filters.push({ column: group.column, op: '=', value: option, label: group.label, needs: group.needs });
        break;
      }
    }
  }

  // 7. Intent
  const limit = parseLimit(text);
  const isRanking = RANK_WORDS.test(text) && !!dimensionHit;
  let intent;
  if (timeGrain) intent = 'trend';
  else if (isRanking) intent = 'ranking';
  else if (dimensionHit) intent = COMPARE_WORDS.test(text) ? 'comparison' : 'breakdown';
  else if (LIST_WORDS.test(text) && dimensionHit) intent = 'list';
  else intent = 'aggregate';

  const direction = ASC_WORDS.test(text) ? 'ASC' : 'DESC';
  const dimension = intent === 'aggregate' ? null : (dimensionHit ? dimensionHit.item : null);

  // ---- assemble --------------------------------------------------------
  const rowLimit = Math.min(settings.max_rows || 500, 5000);
  const effectiveLimit = intent === 'ranking'
    ? (limit || 10)
    : intent === 'trend'
      ? rowLimit
      : (limit || (dimension ? 25 : 1));

  const buildArgs = {
    model, connectionId, metric, dimension, timeGrain, timeRange, filters,
    intent, direction, limit: Math.min(effectiveLimit, rowLimit), settings,
  };
  const built = buildSql(buildArgs);

  // For a single headline number over a bounded window we also prepare the
  // same query shifted back one window, so the answer can carry a delta.
  let comparisonSql = null;
  let comparisonRange = null;
  if (intent === 'aggregate' && timeRange) {
    comparisonRange = previousRange(timeRange);
    comparisonSql = buildSql({ ...buildArgs, timeRange: comparisonRange }).sql;
  }

  // ---- reasoning steps for the UI --------------------------------------
  steps.push({
    title: 'Worked out what to measure',
    detail: metricInferred
      ? `The question did not name a measure, so ${metric.label} was used - ${metric.description}.`
      : `"${metricHit.matched}" was read as ${metric.label} - ${metric.description}.`,
  });
  if (dimension) {
    steps.push({ title: 'Grouped the results', detail: `Broken down by ${dimension.label.toLowerCase()}.` });
  }
  if (timeGrain) {
    steps.push({ title: 'Split it over time', detail: `Shown one ${timeGrain.label.toLowerCase()} at a time.` });
  }
  steps.push({
    title: 'Set the time period',
    detail: !timeRange
      ? 'No period was mentioned, so everything on record was included.'
      : rangeInferred
        ? `No period was mentioned, so ${timeRange.label} was used (${timeRange.start} to ${timeRange.end}), which keeps every period a full one.`
        : `"${timeRange.label}" means ${timeRange.start} to ${timeRange.end}.`,
  });
  if (filters.length) {
    steps.push({
      title: 'Narrowed it down',
      detail: filters.map((f) => `${f.label} is ${f.value}`).join(', '),
    });
  }
  if (built.guards.length) {
    steps.push({ title: 'Applied your workspace rules', detail: built.guards.join(' ') });
  }

  // ---- confidence -------------------------------------------------------
  let confidence = 0.55;
  if (metricHit) confidence += 0.2;
  if (dimensionHit) confidence += 0.1;
  if (timeRange) confidence += 0.08;
  if (filters.length) confidence += 0.07;
  if (glossaryHits.length) confidence += 0.05;
  if (metricInferred) confidence -= 0.12;
  confidence = Math.max(0.28, Math.min(0.98, confidence));

  return {
    ok: true,
    intent,
    metric,
    dimension,
    timeGrain,
    timeRange,
    filters,
    direction,
    limit: built.limit,
    sql: built.sql,
    comparisonSql,
    comparisonRange,
    tables: built.tables,
    steps,
    confidence: Math.round(confidence * 100) / 100,
    metricInferred,
    blockedMetric: blockedMetric ? blockedMetric.item.label : null,
    glossaryHits,
  };
}

// ---------------------------------------------------------------------------
// SQL generation
// ---------------------------------------------------------------------------
function buildSql(ctx) {
  const { model, connectionId, metric, dimension, timeGrain, timeRange, filters, intent, direction, limit, settings } = ctx;

  const needs = new Set([...(metric.needs || []), ...((dimension && dimension.needs) || [])]);
  for (const f of filters) (f.needs || []).forEach((n) => needs.add(n));
  if (timeGrain && timeGrain.expr.startsWith('oi.')) needs.add('items');
  if (metric.orderGrain === null) needs.add('items');
  if (needs.has('products')) needs.add('items');

  const guards = [];
  let from;
  let tables;

  if (connectionId === 'peopleops') {
    from = ['FROM employees e'];
    tables = ['employees'];
    if (needs.has('departments')) {
      from.push('JOIN departments d ON e.department_id = d.department_id');
      tables.push('departments');
    }
  } else {
    from = ['FROM orders o'];
    tables = ['orders'];
    if (needs.has('customers')) {
      from.push('JOIN customers c ON o.customer_id = c.customer_id');
      tables.push('customers');
    }
    if (needs.has('items')) {
      from.push('JOIN order_items oi ON oi.order_id = o.order_id');
      tables.push('order_items');
    }
    if (needs.has('products')) {
      from.push('JOIN products p ON p.product_id = oi.product_id');
      tables.push('products');
    }
    if (needs.has('tickets')) {
      from.push('JOIN support_tickets t ON t.order_id = o.order_id');
      tables.push('support_tickets');
    }
  }

  const usingItems = needs.has('items');
  const aggregate = usingItems ? metric.itemGrain : (metric.orderGrain || metric.itemGrain);

  // ---- WHERE ------------------------------------------------------------
  const where = [];
  if (timeRange) {
    where.push(`${model.timeColumn} >= '${timeRange.start}'`);
    where.push(`${model.timeColumn} <= '${timeRange.end}'`);
  }
  for (const f of filters) {
    where.push(`${f.column} ${f.op} '${String(f.value).replace(/'/g, "''")}'`);
  }

  // Workspace rule: cancelled and refunded orders are excluded from revenue
  // style questions unless the user asked about status explicitly.
  const askedAboutStatus = filters.some((f) => f.column === 'o.status')
    || (dimension && dimension.expr === 'o.status');
  if (connectionId !== 'peopleops' && settings.exclude_cancelled !== false && !askedAboutStatus) {
    where.push("o.status NOT IN ('Cancelled', 'Refunded')");
    guards.push('Cancelled and refunded orders were excluded.');
  }
  if (connectionId === 'peopleops' && settings.active_only !== false) {
    where.push('e.is_active = true');
    guards.push('Only currently active employees were counted.');
  }

  // ---- SELECT -----------------------------------------------------------
  const groupExpr = timeGrain ? timeGrain.expr : (dimension ? dimension.expr : null);
  const groupLabel = timeGrain ? timeGrain.label : (dimension ? dimension.label : null);
  const alias = timeGrain ? 'period' : 'label';

  const select = [];
  if (groupExpr) select.push(`${groupExpr} AS ${alias}`);
  select.push(`${aggregate} AS metric_value`);

  // A second, contextual measure makes the table read like a real report.
  if (groupExpr && intent !== 'trend' && metric.id !== 'order_count' && connectionId !== 'peopleops' && !needs.has('tickets')) {
    select.push(usingItems ? 'COUNT(DISTINCT o.order_id) AS orders' : 'COUNT(*) AS orders');
  }
  if (groupExpr && connectionId === 'peopleops' && metric.id !== 'headcount') {
    select.push('COUNT(*) AS headcount');
  }

  const parts = [`SELECT ${select.join(', ')}`, ...from];
  if (where.length) parts.push(`WHERE ${where.join('\n  AND ')}`);
  if (groupExpr) parts.push(`GROUP BY ${groupExpr}`);
  if (groupExpr) {
    parts.push(timeGrain ? `ORDER BY ${timeGrain.sort} ASC` : `ORDER BY metric_value ${direction}`);
  }
  if (groupExpr) parts.push(`LIMIT ${limit}`);

  return { sql: parts.join('\n'), tables, guards, limit };
}
