const test = require('node:test');
const assert = require('node:assert/strict');
const { once } = require('node:events');
const http = require('node:http');
const { createApp } = require('../src/index');
const service = require('../src/services/presentationService');
const { createResultStore } = require('../src/services/resultStore');
const users = [
  { userId: 'pasted-manager', role: 'MANAGER', tenantId: 101, departmentId: 1 },
  { userId: 'pasted-employee', role: 'EMPLOYEE', tenantId: 101, departmentId: 1 },
  { userId: 'other-manager', role: 'MANAGER', tenantId: 102, departmentId: 2 }
];
const policyTemplate = {
  allowedTables: ['employees', 'departments'], deniedColumns: ['employees.date_of_birth'],
  requiredFilters: [{ table: 'employees', column: 'tenant_id', valueFrom: 'tenantId' },
    { table: 'employees', column: 'department_id', valueFrom: 'departmentId' }]
};
const context = (user = users[0]) => ({ user, policy: policyTemplate });
const { createEffectivePolicy } = require('../src/index');

function post(server, endpoint, body) {
  return new Promise((resolve, reject) => {
    const req = http.request({ hostname: '127.0.0.1', port: server.address().port, path: endpoint, method: 'POST', headers: { 'Content-Type': 'application/json' } }, (res) => {
      let text = '';
      res.on('data', (chunk) => { text += chunk; });
      res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(text) }));
    });
    req.on('error', reject); req.end(JSON.stringify(body));
  });
}
async function serve(t, dependencies) {
  const server = createApp(dependencies).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve) => server.close(resolve)));
  return server;
}
const masked = {
  statementType: 'SELECT', columns: [{ name: 'work_email' }], rows: [['m***@example.com']],
  rowCount: 1, truncated: false, masking: { columns: [{ name: 'work_email', piiType: 'EMAIL' }], maskedCells: 1 }
};
const envelope = { status: 'SUCCESS', response: { blocks_emitted: ['TABLE'] }, prediction: {} };
const sql = 'SELECT work_email FROM employees WHERE tenant_id = 101 AND department_id = 1';
const decision = { passed: true, checks: [], securityValidation: { safe: true } };

test('schema metadata removes denied columns and unauthorized tables', () => {
  const schema = service.permittedSchema(createEffectivePolicy(users[0], policyTemplate));
  assert.deepEqual(Object.keys(schema), ['employees', 'departments']);
  assert.equal(schema.employees.date_of_birth, undefined);
  assert.equal(schema.payroll, undefined);
  assert.equal(schema.employees.joined_date, 'DATE');
});

test('hybrid intent analysis is enabled and can be disabled by server configuration', async (t) => {
  const original = process.env.PRESENTATION_USE_LLM;
  t.after(() => {
    if (original === undefined) delete process.env.PRESENTATION_USE_LLM;
    else process.env.PRESENTATION_USE_LLM = original;
  });
  const requests = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    requests.push(JSON.parse(options.body));
    return { ok: true, json: async () => ({ status: 'SUCCESS', analysis: { intent: {}, response_intent: {} } }) };
  });
  process.env.PRESENTATION_USE_LLM = 'true';
  const policy = createEffectivePolicy(users[0], policyTemplate);
  await service.analyzeQuestion('Count employees', users[0], policy);
  assert.equal(requests[0].use_llm, true);
  process.env.PRESENTATION_USE_LLM = 'false';
  await service.analyzeQuestion('Count employees', users[0], policy);
  assert.equal(requests[1].use_llm, false);
  assert.equal(requests[0].schema_meta.employees.date_of_birth, undefined);
});

test('generation guidance uses only schema-valid fields and keeps historical forecast input', () => {
  const hints = service.generationGuidance({ intent: { primary_intent: 'TREND_ANALYSIS' },
    prediction_request: { prediction_required: true },
    semantic_roles: { metrics: [{ table: 'payroll', column: 'net_salary', aggregation: 'SUM' }], dimensions: ['department_id'], temporal_field: 'joined_date', temporal_granularity: 'MONTH' },
    schema_binding: { affected_columns: [{ table: 'employees', column: 'department_id' }, { table: 'employees', column: 'joined_date' }] }
  }, createEffectivePolicy(users[0], policyTemplate));
  assert.doesNotMatch(hints, /payroll|net_salary/);
  assert.match(hints, /employees.department_id/);
  assert.match(hints, /employees.joined_date/);
  assert.match(hints, /historical observations/);
  assert.match(hints, /do not apply the future forecast horizon/);
});

test('only server-masked rows reach presentation and simulation; identity tampering fails', async (t) => {
  const calls = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    const body = JSON.parse(options.body);
    calls.push({ url, body });
    return { ok: true, json: async () => url.endsWith('/simulate') ? { status: 'SUCCESS', scenario: { simulated: true } } : envelope };
  });
  let executed = 0;
  const server = await serve(t, {
    verifySql: async () => decision,
    executeAndMask: async () => { executed++; return masked; }
  });
  const result = await post(server, '/api/secure-query', {
    ...context(), sql, question: 'List work emails', execute: true,
    raw_results: [{ work_email: 'secret@example.com' }], security_context: { tenant_id: '999' }
  });
  assert.equal(result.body.status, 'COMPLETED');
  assert.equal(result.body.presentationStatus, 'READY');
  assert.deepEqual(calls[0].body.member2_result, masked);
  assert.equal(calls[0].body.security_context.tenant_id, '101');
  assert.equal(calls[0].body.use_llm, true);
  assert.doesNotMatch(JSON.stringify(calls), /secret@example.com|999/);
  const id = result.body.resultId;
  for (const user of [users[1], users[2]]) {
    const denied = await post(server, '/api/simulate', { ...context(user), resultId: id, scenarioText: 'Increase by 10%' });
    assert.equal(denied.status, 404);
  }
  assert.equal(calls.length, 1);
  const changedPolicy = await post(server, '/api/simulate', { ...context(), policy: { ...policyTemplate, version: 'changed' }, resultId: id, scenarioText: 'Increase by 10%' });
  assert.equal(changedPolicy.status, 404);
  const simulation = await post(server, '/api/simulate', { ...context(), resultId: id, scenarioText: 'Increase by 10%', member2_result: { rows: [['secret@example.com']] } });
  assert.equal(simulation.body.status, 'SUCCESS');
  assert.deepEqual(calls[1].body.member2_result, masked);
  assert.equal(executed, 1, 'Simulation must not reexecute SQL');
});

test('presentation outage leaves masked execution successful', async (t) => {
  t.mock.method(global, 'fetch', async () => { throw new Error('offline'); });
  const server = await serve(t, { verifySql: async () => decision, executeAndMask: async () => masked });
  const result = await post(server, '/api/secure-query', { ...context(), sql, question: 'List work emails', execute: true });
  assert.equal(result.body.status, 'COMPLETED');
  assert.deepEqual(result.body.result, masked);
  assert.equal(result.body.presentationStatus, 'UNAVAILABLE');
});

test('blocked SQL never executes or calls presentation', async (t) => {
  t.mock.method(global, 'fetch', async () => { assert.fail('Blocked SQL must not call a service'); });
  const server = await serve(t, { executeAndMask: async () => { assert.fail('Blocked SQL must not execute'); } });
  const result = await post(server, '/api/secure-query', { ...context(), sql: 'DROP TABLE employees', question: 'List employees', execute: true });
  assert.equal(result.body.status, 'BLOCKED');
  assert.equal(result.body.resultId, undefined);
  assert.equal(result.body.presentation, undefined);
});

test('invalid intent precondition stops generation; analysis outage forwards only question and provided rules', async (t) => {
  const calls = [];
  let offline = false;
  t.mock.method(global, 'fetch', async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    if (url.endsWith('/analyze')) {
      if (offline) throw new Error('offline');
      return { ok: true, json: async () => ({ status: 'SUCCESS', analysis: { intent: {}, response_intent: { is_data_request: false } } }) };
    }
    return { ok: true, json: async () => ({ status: 'SUCCESS', predicted_sql: sql }) };
  });
  const server = await serve(t);
  assert.equal((await post(server, '/api/generate-sql', { ...context(), question: 'hello' })).body.code, 'NOT_A_DATA_REQUEST');
  assert.equal(calls.length, 1);
  offline = true;
  const result = await post(server, '/api/generate-sql', { ...context(), question: 'List employees' });
  assert.equal(result.body.status, 'GENERATED');
  assert.equal(result.body.analysisStatus, 'UNAVAILABLE');
  assert.deepEqual(calls[2].body, { user_query: 'List employees', injected_rules: null });
});

test('secure-query generation forwards only question and JSON rules and still checks supplied policy', async (t) => {
  const rules = { constraints: ['Count employees.'], note: 'Keep this extra field.' };
  const requests = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    requests.push(JSON.parse(options.body));
    return { ok: true, json: async () => ({ status: 'SUCCESS', predicted_sql: sql }) };
  });
  let verification;
  const server = await serve(t, {
    presentationService: { analyzeQuestion: async () => ({ analysis: null, analysisStatus: 'DISABLED' }) },
    verifySql: async (input) => { verification = input; return decision; }
  });
  const result = await post(server, '/api/secure-query', { ...context(), rules, question: 'Count employees', execute: false });
  assert.equal(result.body.status, 'APPROVED');
  assert.deepEqual(requests, [{ user_query: 'Count employees', injected_rules: rules }]);
  assert.equal(verification.user.userId, users[0].userId);
  assert.deepEqual(verification.policy, createEffectivePolicy(users[0], policyTemplate));
});

test('result store enforces expiry, policy changes, identity boundaries and capacity', () => {
  let time = 0;
  const store = createResultStore({ ttlMs: 10, maxEntries: 2, now: () => time });
  const user = users[0], policy = createEffectivePolicy(user, policyTemplate);
  const save = () => store.save({ user, policy, question: 'List employees', result: masked });
  const id = save();
  assert.ok(store.get(id, user, policy));
  assert.equal(store.get(id, users[1], policy), null);
  assert.equal(store.get(id, user, { ...policy, version: 'changed' }), null);
  save(); save();
  assert.equal(store.get(id, user, policy), null);
  const latest = save(); time = 11;
  assert.equal(store.get(latest, user, policy), null);
});
