const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { createApp } = require('../src/index');

const user = { userId: 'test-user', role: 'MANAGER', tenantId: 101 };
const policy = {
  allowedTables: ['employees'],
  deniedColumns: ['employees.nic_number'],
  requiredFilters: [{ table: 'employees', column: 'tenant_id', valueFrom: 'tenantId' }]
};

function post(server, body) {
  return new Promise((resolve, reject) => {
    const request = http.request({
      host: '127.0.0.1', port: server.address().port, path: '/api/secure-query',
      method: 'POST', headers: { 'Content-Type': 'application/json' }
    }, (response) => {
      let text = '';
      response.on('data', (chunk) => { text += chunk; });
      response.on('end', () => resolve({ status: response.statusCode, body: JSON.parse(text) }));
    });
    request.on('error', reject);
    request.end(JSON.stringify(body));
  });
}

test('table and column access is enforced after SQLGlot under Policy check', async (t) => {
  let executed = 0;
  let inspected = 0;
  const server = createApp({
    executeAndMask: async () => {
      executed += 1;
      return { columns: [], rows: [], rowCount: 0, masking: { maskedCells: 0 } };
    },
    presentationService: { predictionEnabled: () => false }
  }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve) => server.close(resolve)));

  let inspection;
  t.mock.method(global, 'fetch', async (url) => {
    assert.match(String(url), /\/inspect$/);
    inspected += 1;
    return { ok: true, json: async () => ({ success: true, analysis: inspection }) };
  });

  for (const scenario of [
    { title: 'denied column', table: 'employees', select: 'e.nic_number', columns: ['nic_number'], reason: 'BLOCKED_COLUMN' },
    { title: 'unauthorized table', table: 'payroll', select: 'e.net_salary', columns: ['net_salary'], reason: 'TABLE_NOT_ALLOWED' },
    { title: 'column outside canonical schema', table: 'employees', select: 'e.unknown_column', columns: ['unknown_column'], reason: 'COLUMN_NOT_ALLOWED' },
    { title: 'wildcard that would expose restricted columns', table: 'employees', select: '*', columns: [], reason: 'COLUMN_NOT_ALLOWED' },
    { title: 'restricted column in a nested query', table: 'employees', select: '(SELECT nic_number FROM employees WHERE tenant_id = 101)', columns: ['nic_number'], reason: 'BLOCKED_COLUMN' }
  ]) {
    await t.test(scenario.title, async () => {
      const sql = `SELECT ${scenario.select} FROM ${scenario.table} e WHERE e.tenant_id = 101`;
      inspection = {
        statementType: 'SELECT', normalizedSql: sql,
        tables: [{ name: scenario.table, alias: 'e' }],
        columns: scenario.columns.map((column) => ({ table: scenario.table, column })),
        filters: [{ table: scenario.table, column: 'tenant_id', operator: '=', value: 101 }], joins: []
      };
      const before = inspected;
      const response = await post(server, { sql, policy, user, execute: true });
      assert.equal(response.status, 200);
      assert.equal(response.body.status, 'BLOCKED');
      assert.equal(response.body.securityValidation.safe, true);
      assert.deepEqual(response.body.securityValidation.violations, []);
      assert.equal(inspected, before + 1, 'SQLGlot must run before table/column authorization');
      assert.ok(response.body.inspection);
      const access = response.body.decision.checks.find((check) => check.label === 'Table & column access');
      assert.equal(access.passed, false);
      assert.equal(access.reason, scenario.reason);
      assert.equal(executed, 0, 'Policy failure must prevent database execution');
    });
  }

  await t.test('the same SQL executes after the policy permits its column', async () => {
    const sql = 'SELECT e.nic_number FROM employees e WHERE e.tenant_id = 101';
    inspection = {
      statementType: 'SELECT', normalizedSql: sql,
      tables: [{ name: 'employees', alias: 'e' }], columns: [{ table: 'employees', column: 'nic_number' }],
      filters: [{ table: 'employees', column: 'tenant_id', operator: '=', value: 101 }], joins: []
    };
    const response = await post(server, { sql, policy: { ...policy, deniedColumns: [] }, user, execute: true });
    assert.equal(response.status, 200);
    assert.equal(response.body.status, 'COMPLETED');
    assert.equal(response.body.securityValidation.safe, true);
    assert.ok(response.body.decision.checks.every((check) => check.passed));
    assert.equal(executed, 1);
  });
});
