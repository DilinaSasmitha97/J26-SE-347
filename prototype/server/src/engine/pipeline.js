import { plan as planQuestion } from './planner.js';
import { execute } from './executor.js';
import { narrate } from './narrator.js';
import { visualise } from './visualizer.js';
import { getSemantic } from './semantic.js';

// ---------------------------------------------------------------------------
// The full ask -> answer pipeline: plan, enforce policy, execute, narrate,
// choose a chart, suggest follow-ups.
// ---------------------------------------------------------------------------

function followUps(plan, connectionId, asked = '') {
  const model = getSemantic(connectionId);
  const out = [];

  if (!plan.timeGrain) out.push(`${plan.metric.label} by month over the last 12 months`);
  if (!plan.dimension) {
    const dim = model.dimensions.find((d) => !d.pii && (!d.needs || !d.needs.includes('tickets')));
    if (dim) out.push(`${plan.metric.label} by ${dim.label.toLowerCase()}`);
  } else {
    out.push(`Top 5 ${plan.dimension.label.toLowerCase()}s by ${plan.metric.label.toLowerCase()} this year`);
  }
  if (!plan.timeRange) out.push(`${plan.metric.label} last quarter`);
  else out.push(`Compare ${plan.metric.label.toLowerCase()} across regions ${plan.timeRange.label}`);

  // Never suggest the question that was just asked.
  const normalise = (t) => String(t).toLowerCase().replace(/[^a-z0-9 ]/g, '').trim();
  return out.filter((s) => normalise(s) !== normalise(asked)).slice(0, 3);
}

export function ask({ question, connection, user }) {
  const settings = connection.settings || {};
  const startedAt = Date.now();

  if (connection.status !== 'connected') {
    return {
      status: 'error',
      answer: {
        headline: 'Connection unavailable',
        subline: connection.name,
        description: connection.statusMessage
          || `The connection "${connection.name}" is not currently reachable, so the question could not be answered.`,
        insights: [],
      },
      chart: { type: 'empty' },
      rows: [],
      columns: [],
      sql: null,
      steps: [],
      confidence: 0,
      executionMs: 0,
      followUps: [],
    };
  }

  const plan = planQuestion(question, connection.id, settings);

  if (!plan.ok) {
    return clarification(question, connection, 'That connection has no semantic model registered.');
  }

  // ---- policy: restricted metric ---------------------------------------
  // The question named a measure that governance hides. Say so rather than
  // quietly answering with a different measure.
  if (plan.blockedMetric && plan.metricInferred) {
    return {
      status: 'blocked',
      answer: {
        headline: 'Restricted measure',
        subline: `${plan.blockedMetric} is not exposed on this connection`,
        description: `This question asks for ${plan.blockedMetric}, which an administrator has marked as sensitive for ${connection.name}. Ask an owner to turn off "Hide sensitive metrics" under Admin -> Governance, or rephrase the question around a measure you can access.`,
        insights: [],
      },
      chart: { type: 'empty' },
      rows: [],
      columns: [],
      sql: null,
      steps: plan.steps,
      confidence: plan.confidence,
      executionMs: Date.now() - startedAt,
      followUps: followUps(plan, connection.id),
    };
  }

  // ---- nothing in the question was understood ---------------------------
  if (plan.metricInferred && !plan.dimension && !plan.timeGrain && !plan.timeRange && !plan.filters.length) {
    return clarification(question, connection, 'Nothing in that question matched a measure, a grouping or a time period in this schema.');
  }

  // ---- policy: blocked tables ------------------------------------------
  const blocked = (settings.blocked_tables || []).filter((t) => plan.tables.includes(t));
  if (blocked.length) {
    return {
      status: 'blocked',
      answer: {
        headline: 'Blocked by workspace policy',
        subline: `${blocked.join(', ')} ${blocked.length > 1 ? 'are' : 'is'} not available for questions`,
        description: `Answering this would need the ${blocked.join(' and ')} table${blocked.length > 1 ? 's' : ''}, which an administrator has excluded from natural language access for this connection. An owner can re-enable ${blocked.length > 1 ? 'them' : 'it'} under Admin -> Access Control.`,
        insights: [],
      },
      chart: { type: 'empty' },
      rows: [],
      columns: [],
      sql: settings.show_sql ? plan.sql : null,
      steps: plan.steps,
      confidence: plan.confidence,
      executionMs: Date.now() - startedAt,
      followUps: [],
    };
  }

  // ---- execute ----------------------------------------------------------
  let result;
  try {
    result = execute(plan.sql, connection.id, plan, settings);
  } catch (err) {
    return clarification(question, connection, `The generated SQL could not be executed: ${err.message}`);
  }

  let comparison = null;
  if (plan.comparisonSql) {
    try {
      const prev = execute(plan.comparisonSql, connection.id, plan, settings);
      if (prev.rows.length) comparison = { value: prev.rows[0].value, range: plan.comparisonRange };
    } catch {
      comparison = null;
    }
  }

  const answer = narrate(plan, result, comparison);
  const chart = settings.auto_chart ? visualise(plan, result) : { type: 'table', valueFormat: plan.metric.format };

  // ---- shape the table --------------------------------------------------
  const columns = buildColumns(plan, result.rows);

  if (settings.narrative_style === 'concise') {
    answer.description = answer.description.split('. ')[0] + '.';
  }

  return {
    status: 'ok',
    answer,
    chart,
    rows: result.rows,
    columns,
    rowCount: result.rowCount,
    sql: settings.show_sql ? plan.sql : null,
    steps: settings.show_reasoning ? plan.steps : [],
    confidence: plan.confidence,
    lowConfidence: plan.confidence < 0.5,
    metricInferred: plan.metricInferred,
    blockedMetric: plan.blockedMetric,
    executionMs: result.executionMs,
    plan: {
      intent: plan.intent,
      metric: plan.metric.label,
      dimension: plan.dimension ? plan.dimension.label : null,
      timeGrain: plan.timeGrain ? plan.timeGrain.label : null,
      timeRange: plan.timeRange,
      filters: plan.filters.map((f) => ({ label: f.label, value: f.value })),
      tables: plan.tables,
    },
    followUps: followUps(plan, connection.id, question),
  };
}

function buildColumns(plan, rows) {
  if (!rows.length) return [];
  const first = rows[0];
  const cols = [];
  for (const key of Object.keys(first)) {
    if (key === 'period') cols.push({ key, label: plan.timeGrain ? plan.timeGrain.label : 'Period', type: 'text' });
    else if (key === 'label') cols.push({ key, label: plan.dimension ? plan.dimension.label : 'Group', type: 'text' });
    else if (key === 'value') cols.push({ key, label: plan.metric.label, type: 'measure', format: plan.metric.format });
    else if (key === 'orders') cols.push({ key, label: 'Orders', type: 'measure', format: 'number' });
    else if (key === 'headcount') cols.push({ key, label: 'Headcount', type: 'measure', format: 'number' });
    else cols.push({ key, label: key, type: 'measure', format: 'number' });
  }
  return cols;
}

function clarification(question, connection, reason) {
  const model = getSemantic(connection.id);
  const metrics = model ? model.metrics.slice(0, 4).map((m) => m.label).join(', ') : '';
  return {
    status: 'clarify',
    answer: {
      headline: 'I need a bit more to go on',
      subline: 'Could not resolve the question against this schema',
      description: `${reason} Try naming a measure and, optionally, how to break it down. On ${connection.name} you can ask about ${metrics}.`,
      insights: [],
    },
    chart: { type: 'empty' },
    rows: [],
    columns: [],
    sql: null,
    steps: [],
    confidence: 0.2,
    executionMs: 0,
    followUps: model
      ? [
        `${model.metrics[0].label} by ${model.dimensions[0].label.toLowerCase()}`,
        `${model.metrics[0].label} by month over the last 12 months`,
        `Top 5 ${model.dimensions[0].label.toLowerCase()}s by ${model.metrics[0].label.toLowerCase()}`,
      ]
      : [],
  };
}
