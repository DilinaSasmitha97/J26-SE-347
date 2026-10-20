const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { createApp } = require('../src/index');
const { createQueryExecutor } = require('security-validation-layer');
const { executeAndMask } = require('../src/services/secureQueryService');

const user = { userId: 'research-user', role: 'MANAGER', tenantId: 101 };
const policy = { allowedTables: ['employees'], requiredFilters: [
  { table: 'employees', column: 'tenant_id', valueFrom: 'tenantId' }
] };
const original = 'SELECT e.first_name FROM employees e';
const finalSql = 'SELECT e.first_name FROM employees AS e WHERE e.tenant_id = 101';
const parameterizedSql = finalSql.replace('= 101', '= ?');
const artifact = (repair) => ({ status: repair ? 'REPAIRED' : 'UNCHANGED_VERIFIED', applied: repair,
  finalSql, parameterizedSql, parameters: ['101'], finalVerification: 'PASS', rowFiltersVerified: true,
  changes: repair ? [{ alias: 'e', action: 'ADD_MISSING_TENANT_FILTER' }] : [], findings: [], message: 'Verified.' });

function post(server, path, body) {
  return new Promise((resolve, reject) => {
    const req = http.request({ host: '127.0.0.1', port: server.address().port, path, method: 'POST',
      headers: { 'Content-Type': 'application/json' } }, (res) => {
      let text = '';
      res.on('data', (part) => { text += part; });
      res.on('end', () => resolve(JSON.parse(text)));
    });
    req.on('error', reject); req.end(JSON.stringify(body));
  });
}

async function setup(t, isolation) {
  const executions = [];
  const calls = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    const input = JSON.parse(options.body);
    calls.push({ url: String(url), input });
    if (String(url).endsWith('/inspect')) return { ok: true, json: async () => ({ success: true, analysis: {
      statementType: 'SELECT', normalizedSql: input.sql, tables: [{ name: 'employees', alias: 'e' }],
      columns: [{ table: 'employees', column: 'first_name' }], filters: [], joins: []
    } }) };
    assert.match(String(url), /\/tenant-isolation$/);
    const result = isolation ? await isolation(input) : artifact(input.repair);
    return { ok: true, json: async () => ({ success: true, tenantRewrite: result }) };
  });
  const server = createApp({
    executeAndMask: async (...args) => { executions.push(args); return { columns: [], rows: [], rowCount: 0 }; },
    presentationService: { predictionEnabled: () => false }
  }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve) => server.close(resolve)));
  return { server, executions, calls };
}

test('repair is verified again and only bound final SQL reaches execution', async (t) => {
  const { server, executions, calls } = await setup(t);
  const response = await post(server, '/api/secure-query', { user, policy, sql: original, execute: true,
    finalSql: 'SELECT * FROM payroll', parameters: ['102'], tenantRewrite: { status: 'UNCHANGED_VERIFIED' } });
  assert.equal(response.status, 'COMPLETED');
  assert.equal(response.originalSql, original);
  assert.equal(response.sql, finalSql);
  assert.equal(response.tenantRewrite.status, 'REPAIRED');
  assert.equal(executions.length, 1);
  assert.equal(executions[0][0], parameterizedSql);
  assert.deepEqual(executions[0][3], { parameters: ['101'] });
  const isolation = calls.filter((call) => call.url.endsWith('/tenant-isolation'));
  assert.deepEqual(isolation.map((call) => call.input.repair), [true, false]);
  assert.equal(isolation[1].input.sql, finalSql);
  assert.deepEqual(isolation[0].input.rules, [{ table: 'employees', column: 'tenant_id', operator: '=', value: 101 }]);
});

test('repair preview does not execute', async (t) => {
  const { server, executions } = await setup(t);
  const response = await post(server, '/api/secure-query', { user, policy, sql: original, execute: false });
  assert.equal(response.status, 'APPROVED');
  assert.equal(response.tenantRewrite.finalVerification, 'PASS');
  assert.equal(executions.length, 0);
});

test('validation-only endpoint never requests automatic repair', async (t) => {
  const { server, executions, calls } = await setup(t, (input) => {
    assert.equal(input.repair, false);
    return { status: 'CANNOT_REPAIR', applied: false, reasonCode: 'MISSING_TENANT_FILTER',
      message: 'Missing tenant restriction.', finalVerification: 'FAIL', changes: [], findings: [] };
  });
  const response = await post(server, '/api/verify-sql', { user, policy, sql: original });
  assert.equal(response.passed, false);
  assert.equal(response.tenantRewrite.reasonCode, 'MISSING_TENANT_FILTER');
  assert.equal(executions.length, 0);
  assert.equal(calls.filter((call) => call.url.endsWith('/tenant-isolation')).length, 1);
});

test('unsupported queries, outages and malformed artifacts never execute', async (t) => {
  for (const scenario of ['unsupported', 'outage', 'wrong_binding', 'changed_verification', 'unsafe_final_sql']) {
    await t.test(scenario, async (t) => {
      const { server, executions } = await setup(t, (input) => {
        if (scenario === 'outage') throw new Error('connection refused');
        if (scenario === 'unsupported') return { status: 'CANNOT_REPAIR', applied: false,
          reasonCode: 'UNSUPPORTED_QUERY_SHAPE', message: 'Unsupported query.', changes: [], findings: [], finalVerification: 'FAIL' };
        const result = artifact(input.repair);
        if (scenario === 'wrong_binding') result.parameters = ['102'];
        if (scenario === 'changed_verification' && !input.repair) result.parameterizedSql += ' ORDER BY e.id';
        if (scenario === 'unsafe_final_sql') {
          result.finalSql = 'DROP TABLE employees';
          result.parameterizedSql = 'DROP TABLE employees';
        }
        return result;
      });
      const response = await post(server, '/api/secure-query', { user, policy, sql: original, execute: true });
      assert.equal(response.status, 'BLOCKED');
      assert.equal(response.decision.passed, false);
      assert.notEqual(response.tenantRewrite.finalVerification, 'PASS');
      assert.equal(executions.length, 0);
    });
  }
});

test('missing tenant context fails before any isolation request', async (t) => {
  const { server, executions, calls } = await setup(t);
  const response = await post(server, '/api/secure-query', { user: { userId: 'no-tenant', role: 'MANAGER' },
    policy: { allowedTables: ['employees'] }, sql: original, execute: true });
  assert.equal(response.tenantRewrite.reasonCode, 'INVALID_TENANT_CONTEXT');
  assert.equal(executions.length, 0);
  assert.equal(calls.filter((call) => call.url.endsWith('/tenant-isolation')).length, 0);
});

test('a passed decision without the verified execution artifact is blocked', async (t) => {
  const server = createApp({ verifySql: async () => ({ passed: true, checks: [] }),
    executeAndMask: async () => assert.fail('unverified SQL must not execute') }).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve) => server.close(resolve)));
  const response = await post(server, '/api/secure-query', { user, policy, sql: original, execute: true });
  assert.equal(response.tenantRewrite.reasonCode, 'ISOLATION_NOT_VERIFIED');
});

test('MySQL executor binds tenant values through prepared execution', async () => {
  let prepared;
  const conn = { query: async () => {}, rollback: async () => {}, release: () => {},
    execute: async (query, parameters) => { prepared = { query, parameters }; return [[[1]], [{ name: 'id', orgTable: 'employees', orgName: 'id' }]]; } };
  const executor = createQueryExecutor({ getConnection: async () => conn });
  const sql = 'SELECT id FROM employees WHERE tenant_id = ?';
  await executor.run(sql, ['101']);
  assert.deepEqual(prepared, { query: { sql, rowsAsArray: true }, parameters: ['101'] });
});

test('SQLite execution binds the same trusted tenant parameters', async (t) => {
  const previous = process.env.DB_TYPE;
  process.env.DB_TYPE = 'sqlite';
  t.after(() => { if (previous === undefined) delete process.env.DB_TYPE; else process.env.DB_TYPE = previous; });
  const result = await executeAndMask('SELECT COUNT(*) AS total FROM employees WHERE tenant_id = ?', policy, user,
    { parameters: ['101'], nerClient: { analyze: async () => assert.fail('numeric counts do not need NER') } });
  const { DatabaseSync } = require('node:sqlite');
  const database = new DatabaseSync(require('path').resolve(__dirname, '../../shared-database/multitenant_hr.db'), { readOnly: true });
  t.after(() => database.close());
  const expected = database.prepare('SELECT COUNT(*) AS total FROM employees WHERE tenant_id = 101').get().total;
  assert.equal(result.rows[0][0], expected);
  assert.equal(result.engine, 'sqlite');
});
