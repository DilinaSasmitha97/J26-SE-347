const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { createApp } = require('../src/index');

const users = [
  { userId: 'pasted-manager', role: 'MANAGER', tenantId: 101, departmentId: 1 },
  { userId: 'other-manager', role: 'MANAGER', tenantId: 102, departmentId: 2 }
];
const policy = {
  allowedTables: ['employees'],
  requiredFilters: [{ table: 'employees', column: 'tenant_id', valueFrom: 'tenantId' }]
};
const sql = 'SELECT gender, COUNT(*) AS headcount FROM employees WHERE tenant_id = 101 GROUP BY gender';
const masked = {
  statementType: 'SELECT', columns: [{ name: 'gender' }, { name: 'headcount' }], rows: [['Female', 42], ['Male', 51]],
  rowCount: 2, truncated: false, masking: { columns: [], maskedCells: 0 }
};
const classification = { intent: 'PROPORTION', presentation_types: ['table', 'pie_chart', 'bar_chart'] };
const rendered = { status: 'SUCCESS', source: 'classification', intent: 'PROPORTION', row_count: 2, views: [{ type: 'table', available: true }] };
const decision = { passed: true, checks: [], securityValidation: { safe: true }, finalSql: sql,
  tenantRewrite: { status: 'UNCHANGED_VERIFIED', finalVerification: 'PASS' },
  execution: { sql: sql.replace('= 101', '= ?'), parameters: ['101'] } };

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

function presentationService(t) {
  const calls = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return { ok: true, json: async () => rendered };
  });
  return calls;
}

async function execute(server, user = users[0]) {
  const response = await post(server, '/api/secure-query', { user, policy, sql, question: 'Give me the gender distribution in my company', execute: true });
  assert.equal(response.body.status, 'COMPLETED');
  return response.body;
}

test('execution skips prediction by default but keeps the result for presentation', async (t) => {
  const calls = presentationService(t);
  const server = await serve(t);
  const body = await execute(server);
  assert.equal(body.presentationStatus, 'SKIPPED');
  assert.equal(body.presentation, null);
  assert.equal(typeof body.resultId, 'string');
  assert.equal(calls.length, 0, 'No prediction call while prediction is disabled');
});

test('presentation renders only the stored masked result in the classified formats', async (t) => {
  const calls = presentationService(t);
  const server = await serve(t);
  const { resultId } = await execute(server);
  const response = await post(server, '/api/present-result', {
    user: users[0], policy, resultId, classification: { ...classification, nl_query: 'ignored' },
    member2_result: { columns: [{ name: 'secret' }], rows: [['secret@example.com']] }, rows: [['tampered']]
  });
  assert.equal(response.status, 200);
  assert.deepEqual(response.body, rendered);
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/v4\/render$/);
  assert.deepEqual(calls[0].body, {
    member2_result: masked, user_query: 'Give me the gender distribution in my company',
    intent: 'PROPORTION', presentation_types: ['table', 'pie_chart', 'bar_chart']
  });
  assert.doesNotMatch(JSON.stringify(calls), /secret@example.com|tampered/);
});

test('classification is optional: formats are then chosen from the data', async (t) => {
  const calls = presentationService(t);
  const server = await serve(t);
  const { resultId } = await execute(server);
  const response = await post(server, '/api/present-result', { user: users[0], policy, resultId, classification: null });
  assert.equal(response.status, 200);
  assert.equal(calls[0].body.intent, null);
  assert.equal(calls[0].body.presentation_types, null);
});

test('another identity, a changed policy or an unknown result cannot be rendered', async (t) => {
  const calls = presentationService(t);
  const server = await serve(t);
  const { resultId } = await execute(server);
  for (const body of [
    { user: users[1], policy, resultId, classification },
    { user: users[0], policy: { ...policy, version: 'changed' }, resultId, classification },
    { user: users[0], policy, resultId: 'unknown', classification }
  ]) {
    const response = await post(server, '/api/present-result', body);
    assert.equal(response.status, 404);
    assert.equal(response.body.code, 'RESULT_UNAVAILABLE');
  }
  assert.equal(calls.length, 0);
});

test('invalid presentation requests are rejected before rendering', async (t) => {
  const calls = presentationService(t);
  const server = await serve(t);
  const { resultId } = await execute(server);
  for (const body of [
    { user: users[0], policy, classification },
    { user: users[0], policy, resultId, classification: { intent: 'GENDER_SPLIT', presentation_types: ['table'] } },
    { user: users[0], policy, resultId, classification: { intent: 'PROPORTION', presentation_types: [] } },
    { user: users[0], policy, resultId, classification: { intent: 'PROPORTION', presentation_types: ['donut_chart'] } },
    { user: users[0], policy, resultId, classification: { intent: 'PROPORTION', presentation_types: ['table', 'table'] } },
    { policy, resultId, classification }
  ]) {
    const response = await post(server, '/api/present-result', body);
    assert.equal(response.status, 400, JSON.stringify(body.classification));
  }
  assert.equal(calls.length, 0);
});

test('a presentation outage is reported without affecting the executed result', async (t) => {
  t.mock.method(global, 'fetch', async () => { throw new Error('offline'); });
  const server = await serve(t);
  const { resultId, result } = await execute(server);
  assert.deepEqual(result, masked);
  const response = await post(server, '/api/present-result', { user: users[0], policy, resultId, classification });
  assert.equal(response.status, 502);
  assert.equal(response.body.code, 'PRESENTATION_UNAVAILABLE');
});
