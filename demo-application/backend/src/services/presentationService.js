const fs = require('node:fs');
const path = require('node:path');
const { buildPolicyAllowlist, policyToInjectedRules } = require('./secureQueryService');

class PresentationError extends Error {
  constructor(code, message, status = 502) {
    super(message);
    this.code = code;
    this.status = status;
  }
}

function enabled() { return process.env.PRESENTATION_ENABLED !== 'false'; }
function useLlm() { return process.env.PRESENTATION_USE_LLM !== 'false'; }
// Prediction (forecasts, anomalies, what-if) is kept but off until it is
// re-enabled; the data presentation layer works without it.
function predictionEnabled() { return process.env.PRESENTATION_PREDICTION_ENABLED === 'true'; }

// This metadata is read locally, never fetched from a browser or from an LLM.
// The allowlist remains the authority even when a type is absent from the DDL.
function permittedSchema(policy) {
  const ddl = fs.readFileSync(path.resolve(__dirname, '../../../shared-database/multitenant_hr_schema.sql'), 'utf8');
  const types = {};
  for (const match of ddl.matchAll(/CREATE TABLE\s+(\w+)\s*\(([\s\S]*?)\n\);/gi)) {
    const columns = {};
    for (const line of match[2].split('\n')) {
      const col = line.match(/^\s*(\w+)\s+((?:BIGINT|INT|TINYINT|DECIMAL|VARCHAR|CHAR|ENUM|DATETIME|DATE|TIME)(?:\([^\n]*?\))?)/i);
      if (col) columns[col[1].toLowerCase()] = col[2];
    }
    types[match[1].toLowerCase()] = columns;
  }
  return Object.fromEntries(Object.entries(buildPolicyAllowlist(policy)).map(([table, columns]) => [
    table, Object.fromEntries(columns.map((column) => [column, types[table]?.[column] || 'VARCHAR']))
  ]));
}

function trustedContext(user, policy) {
  return {
    tenant_id: String(user.tenantId), user_role: user.role,
    prompt_grounding_rules: policyToInjectedRules(policy), denied_tables: []
  };
}

async function call(endpoint, body, timeoutMs) {
  if (!enabled()) throw new PresentationError('PRESENTATION_DISABLED', 'Presentation is disabled.', 503);
  const url = `${(process.env.PRESENTATION_SERVICE_URL || 'http://127.0.0.1:8004').replace(/\/$/, '')}/api/v4/${endpoint}`;
  let response, payload;
  try {
    response = await fetch(url, {
      method: body ? 'POST' : 'GET',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
      signal: AbortSignal.timeout(timeoutMs)
    });
    payload = await response.json();
  } catch {
    throw new PresentationError('PRESENTATION_UNAVAILABLE', 'The presentation service could not be reached or timed out.');
  }
  if (!response.ok || !payload || (endpoint === 'health' ? payload.status !== 'UP' : payload.status !== 'SUCCESS')) {
    throw new PresentationError('PRESENTATION_FAILED', 'The presentation service could not complete this request.');
  }
  return payload;
}

function timeout() { return Number(process.env.PRESENTATION_TIMEOUT_MS || 60000); }

async function analyzeQuestion(question, user, policy) {
  if (!enabled()) return { analysis: null, analysisStatus: 'DISABLED' };
  try {
    const payload = await call('analyze', {
      user_query: question, schema_meta: permittedSchema(policy),
      security_context: trustedContext(user, policy), use_llm: useLlm()
    }, Number(process.env.PRESENTATION_ANALYSIS_TIMEOUT_MS || 60000));
    if (!payload.analysis?.intent || !payload.analysis?.response_intent) throw new PresentationError('INVALID_ANALYSIS', 'Invalid analysis contract.');
    return { analysis: payload.analysis, analysisStatus: 'READY' };
  } catch (error) {
    return { analysis: null, analysisStatus: 'UNAVAILABLE', analysisWarning: error.message };
  }
}

// Whitelist generation hints against the permitted schema. No arbitrary model
// text is appended to security rules, and prediction never executes future SQL.
function generationGuidance(analysis, policy) {
  if (!analysis) return '';
  const schema = permittedSchema(policy);
  const roles = analysis.semantic_roles || {};
  const lines = [];
  const intents = new Set(['TREND_ANALYSIS', 'COMPARISON', 'RANKING', 'PROPORTION', 'DISTRIBUTION', 'CORRELATION', 'ANOMALY_DETECTION', 'KPI_SINGLE_VALUE', 'DETAIL_LOOKUP']);
  if (intents.has(analysis.intent?.primary_intent)) lines.push(`Analytical intent: ${analysis.intent.primary_intent}.`);
  for (const metric of roles.metrics || []) {
    if (schema[metric.table]?.[metric.column] && ['SUM', 'AVG', 'COUNT', 'MIN', 'MAX'].includes(metric.aggregation)) {
      lines.push(`Metric hint: ${metric.aggregation}(${metric.table}.${metric.column}).`);
    }
  }
  const bindings = (analysis.schema_binding?.affected_columns || []).filter((binding) => schema[binding.table]?.[binding.column]);
  for (const dimension of roles.dimensions || []) {
    const binding = bindings.find((item) => item.column === dimension);
    if (binding) lines.push(`Grouping hint: ${binding.table}.${binding.column}.`);
  }
  const temporal = bindings.find((item) => item.column === roles.temporal_field);
  if (temporal) lines.push(`Time axis hint: ${temporal.table}.${temporal.column}.`);
  if (['DAY', 'WEEK', 'MONTH', 'QUARTER', 'YEAR'].includes(roles.temporal_granularity)) lines.push(`Period granularity: ${roles.temporal_granularity}.`);
  const ordering = typeof roles.ordering === 'string' ? roles.ordering.match(/^(\w+)\s+(ASC|DESC)$/i) : null;
  if (ordering && (bindings.some((item) => item.column === ordering[1]) || (roles.metrics || []).some((item) => item.column === ordering[1] && schema[item.table]?.[item.column]))) {
    lines.push(`Order hint: ${ordering[1]} ${ordering[2].toUpperCase()}.`);
  }
  if (analysis.prediction_request?.prediction_required) {
    lines.push('Return historical observations for prediction, never future-only observations. Aggregate the requested measure to one row per period (and category when requested), include an ISO date period column, and order chronologically. The presentation service forecasts future periods; do not apply the future forecast horizon as a historical date filter. Do not impose a top-N limit on forecast history unless explicitly requested.');
  } else if (Number.isInteger(roles.limit) && roles.limit > 0 && roles.limit <= 1000 && ['EXPLICIT', 'INFERRED'].includes(roles.limit_source)) {
    lines.push(`Limit hint: ${roles.limit} (${roles.limit_source === 'EXPLICIT' ? 'requested by user' : 'inferred default, overridable'}).`);
  }
  return lines.join('\n');
}

async function presentResult(question, result, user, policy) {
  if (!question) return { presentation: null, presentationStatus: 'SKIPPED' };
  if (!enabled()) return { presentation: null, presentationStatus: 'DISABLED' };
  try {
    const presentation = await call('present', {
      user_query: question, member2_result: result, schema_meta: permittedSchema(policy),
      security_context: trustedContext(user, policy), use_llm: useLlm(), use_llm_summary: false
    }, timeout());
    if (!Array.isArray(presentation.response?.blocks_emitted) || !presentation.prediction) {
      throw new PresentationError('INVALID_PRESENTATION', 'Invalid presentation contract.');
    }
    return { presentation, presentationStatus: 'READY' };
  } catch (error) {
    return { presentation: null, presentationStatus: 'UNAVAILABLE', presentationError: { code: error.code || 'PRESENTATION_FAILED', message: error.message } };
  }
}

// Data presentation layer: the stored masked result in the classified formats.
// Only the result kept by the gateway is sent; the browser never supplies rows.
async function renderResult(entry, classification) {
  const payload = await call('render', {
    member2_result: entry.result,
    user_query: entry.question || '',
    intent: classification ? classification.intent : null,
    presentation_types: classification ? classification.presentation_types : null
  }, Number(process.env.PRESENTATION_RENDER_TIMEOUT_MS || 30000));
  if (!Array.isArray(payload.views)) throw new PresentationError('INVALID_PRESENTATION', 'Invalid presentation contract.');
  return payload;
}

async function simulateResult(entry, scenarioText, user, policy) {
  return call('simulate', {
    user_query: entry.question, member2_result: entry.result, scenario_text: scenarioText,
    schema_meta: permittedSchema(policy), security_context: trustedContext(user, policy)
  }, timeout());
}

async function presentationHealth() {
  if (!enabled()) return { status: 'disabled' };
  try { return { ...await call('health', null, 1500), status: 'ok' }; }
  catch { return { status: 'unavailable' }; }
}

module.exports = { PresentationError, permittedSchema, trustedContext, generationGuidance, analyzeQuestion, presentResult, renderResult, predictionEnabled, simulateResult, presentationHealth };
