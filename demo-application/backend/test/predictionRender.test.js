const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { createApp } = require('../src/index');

const users = [
  { userId: 'pasted-manager', role: 'MANAGER', tenantId: 101 },
  { userId: 'other-manager', role: 'MANAGER', tenantId: 102 }
];
const policy = { allowedTables: ['employees'], requiredFilters: [{ table: 'employees', column: 'tenant_id', valueFrom: 'tenantId' }] };
const sql = 'SELECT SUBSTR(joined_date, 1, 7) AS month, COUNT(*) AS hires FROM employees WHERE tenant_id = 101 GROUP BY month';
const question = 'Forecast monthly hires for the next 3 months';
const masked = {
  statementType: 'SELECT', columns: [{ name: 'month' }, { name: 'hires' }],
  rows: Array.from({ length: 12 }, (_, i) => [`2024-${String(i + 1).padStart(2, '0')}-01`, i + 3]),
  rowCount: 12, truncated: false, masking: { columns: [], maskedCells: 0 }
};
const forecast = { intent: 'TREND_ANALYSIS', presentation_types: ['table', 'line_chart'], prediction_needed: true };
const predicted = { status: 'SUCCESS', mode: 'FORECAST', readiness: { verdict: 'READY' }, forecast: { generated: true, points: [] }, anomalies: { evaluated: true } };
const decision = { passed: true, checks: [], securityValidation: { safe: true } };

function post(server, path, body) {
  return new Promise((resolve, reject) => {
    const request = http.request({ host: '127.0.0.1', port: server.address().port, path, method: 'POST',
      headers: { 'Content-Type': 'application/json' } }, (response) => {
      let text = '';
      response.on('data', (chunk) => { text += chunk; });
      response.on('end', () => resolve({ status: response.statusCode, body: JSON.parse(text) }));
    });
    request.on('error', reject);
    request.end(JSON.stringify(body));
  });
}

async function serve(t) {
  const server = createApp({ verifySql: async () => decision, executeAndMask: async () => masked }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve) => server.close(resolve)));
  return server;
}

function predictionService(t, reply = () => ({ ok: true, json: async () => predicted })) {
  const calls = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return reply(url, options);
  });
  return calls;
}

async function execute(server) {
  const response = await post(server, '/api/secure-query', { user: users[0], policy, sql, question, execute: true });
  assert.equal(response.body.status, 'COMPLETED');
  return response.body.resultId;
}

test('prediction uses only the stored masked result and the stored question', async (t) => {
  const calls = predictionService(t);
  const server = await serve(t);
  const resultId = await execute(server);
  const response = await post(server, '/api/predict-result', {
    user: users[0], policy, resultId, classification: forecast,
    member2_result: { rows: [['tampered']] }, scenario_text: 'Increase by 10%'
  });
  assert.equal(response.status, 200);
  assert.deepEqual(response.body, predicted);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v4\/predict$/);
  assert.deepEqual(calls[0].body, { member2_result: masked, user_query: question, intent: 'TREND_ANALYSIS', prediction_needed: true });
  assert.doesNotMatch(JSON.stringify(calls), /tampered|Increase by 10%/);
});

test('an anomaly question without a forecast request is accepted', async (t) => {
  const calls = predictionService(t);
  const server = await serve(t);
  const resultId = await execute(server);
  const response = await post(server, '/api/predict-result', {
    user: users[0], policy, resultId,
    classification: { intent: 'ANOMALY_DETECTION', presentation_types: ['table', 'line_chart'], prediction_needed: false }
  });
  assert.equal(response.status, 200);
  assert.equal(calls[0].body.prediction_needed, false);
});

test('questions that ask for neither a forecast nor anomalies are rejected', async (t) => {
  const calls = predictionService(t);
  const server = await serve(t);
  const resultId = await execute(server);
  const response = await post(server, '/api/predict-result', {
    user: users[0], policy, resultId,
    classification: { intent: 'PROPORTION', presentation_types: ['table'], prediction_needed: false }
  });
  assert.equal(response.status, 400);
  assert.equal(response.body.code, 'PREDICTION_NOT_REQUESTED');
  assert.equal(calls.length, 0);
});

test('invalid classifications and unknown results are rejected before prediction', async (t) => {
  const calls = predictionService(t);
  const server = await serve(t);
  const resultId = await execute(server);
  for (const classification of [undefined, null, { ...forecast, prediction_needed: 'yes' }, { ...forecast, intent: 'FORECAST' },
    { ...forecast, presentation_types: [] }]) {
    const response = await post(server, '/api/predict-result', { user: users[0], policy, resultId, classification });
    assert.equal(response.status, 400, JSON.stringify(classification));
  }
  for (const body of [
    { user: users[1], policy, resultId, classification: forecast },
    { user: users[0], policy: { ...policy, version: 'changed' }, resultId, classification: forecast },
    { user: users[0], policy, resultId: 'unknown', classification: forecast }
  ]) {
    const response = await post(server, '/api/predict-result', body);
    assert.equal(response.status, 404);
  }
  assert.equal(calls.length, 0);
});

test('a prediction service outage is reported as unavailable', async (t) => {
  predictionService(t, () => { throw new Error('offline'); });
  const server = await serve(t);
  const resultId = await execute(server);
  const response = await post(server, '/api/predict-result', { user: users[0], policy, resultId, classification: forecast });
  assert.equal(response.status, 502);
  assert.equal(response.body.code, 'PRESENTATION_UNAVAILABLE');
});
