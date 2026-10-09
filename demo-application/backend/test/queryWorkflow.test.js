const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { createApp } = require('../src/index');
const user = { userId: 'pasted-user', role: 'CUSTOM', tenantId: 123, departmentId: 9 };
const policy = { allowedTables: ['employees'], requiredFilters: [
  { table: 'employees', column: 'tenant_id', valueFrom: 'tenantId' },
  { table: 'employees', column: 'department_id', valueFrom: 'departmentId' }
] };

function post(server, path, body) {
  return new Promise((resolve, reject) => {
    const request = http.request({
      host: '127.0.0.1', port: server.address().port, path,
      method: 'POST', headers: { 'Content-Type': 'application/json' }
    }, (response) => {
      let text = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { text += chunk; });
      response.on('end', () => resolve({ status: response.statusCode, body: JSON.parse(text) }));
    });
    request.on('error', reject);
    request.end(JSON.stringify(body));
  });
}

test('separate generation and execution workflow', async (t) => {
  const server = createApp({
    presentationService: {
      analyzeQuestion: async () => { assert.fail('Generate SQL must not analyze the question again'); },
      generationGuidance: () => { assert.fail('Vonara hints must not be used for SQL generation'); }
    },
    intentClassificationService: { classifyIntent: async () => { assert.fail('Generate SQL must not classify the question again'); } }
  }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve, reject) => server.close((error) => error ? reject(error) : resolve())));

  const draft = 'SELECT first_name FROM employees WHERE tenant_id = 101 AND department_id = 1';
  const calls = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return { ok: true, json: async () => ({ status: 'SUCCESS', predicted_sql: draft, metadata: { total_tokens: 25 } }) };
  });

  await t.test('generation forwards only question and pasted JSON rules and returns no classification', async () => {
    const response = await post(server, '/api/generate-sql', {
      question: ' Show employee names ', execute: true,
      policy, user, rules: { constraints: ['Sort employee names alphabetically.'] }
    });
    assert.equal(response.status, 200);
    assert.equal(response.body.status, 'GENERATED');
    assert.equal(response.body.sql, draft);
    assert.equal(response.body.question, 'Show employee names');
    assert.equal(response.body.user.tenantId, 123);
    assert.equal(response.body.user.role, 'CUSTOM');
    assert.deepEqual(response.body.effectivePolicy.allowedTables, ['employees']);
    assert.equal(response.body.generation.metadata.total_tokens, 25);
    assert.equal(response.body.decision, undefined);
    assert.equal(response.body.result, undefined);
    for (const key of ['analysis', 'analysisStatus', 'presentation_types', 'prediction_needed']) {
      assert.equal(response.body[key], undefined, `${key} must not come from generation`);
    }
    assert.equal(calls.length, 1);
    assert.deepEqual(calls[0].body, { user_query: 'Show employee names',
      injected_rules: { constraints: ['Sort employee names alphabetically.'] } });
    assert.deepEqual(response.body.generation.injectedRules, calls[0].body.injected_rules);
  });

  await t.test('execution validates the edited SQL and blocks a destructive change', async () => {
    const response = await post(server, '/api/secure-query', {
      user, policy, sql: 'DROP TABLE employees', execute: true
    });
    assert.equal(response.status, 200);
    assert.equal(response.body.sql, 'DROP TABLE employees');
    assert.equal(response.body.source, 'provided_sql');
    assert.equal(response.body.status, 'BLOCKED');
    assert.equal(response.body.decision.passed, false);
    assert.equal(response.body.result, undefined);
    assert.equal(calls.length, 1, 'Edited SQL must not be regenerated or sent to inspection after safety rejection');
  });

  await t.test('invalid generation inputs do not call the translation service', async () => {
    for (const body of [
      { userId: 'user-101-manager', question: 'Show employees' },
      { user, question: 'Show employees' },
      { policy, question: 'Show employees' },
      { user, policy, question: '   ' },
      { user, policy, question: 'x'.repeat(2001) }
    ]) {
      const response = await post(server, '/api/generate-sql', body);
      assert.equal(response.status, 400);
    }
    assert.equal(calls.length, 1);
  });
});
