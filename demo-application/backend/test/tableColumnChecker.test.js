const test = require('node:test');
const assert = require('node:assert/strict');
const { checkTableColumns } = require('../src/security/sql/tableColumnChecker');
const { verifySql } = require('../src/index');

const sql = `SELECT d.department_name, COUNT(e.employee_id) AS employee_count
FROM employees e JOIN departments d
 ON e.department_id = d.department_id AND e.tenant_id = d.tenant_id
WHERE e.tenant_id = 101 AND e.employment_status = 'ACTIVE'
GROUP BY d.department_id, d.department_name ORDER BY employee_count DESC`;
const policy = { allowedTables: ['employees', 'departments'], rowRules: [
  { table: 'employees', field: 'tenant_id', value: 101 },
  { table: 'departments', field: 'tenant_id', value: 101 }
] };
const baseColumns = [
  { table: 'departments', column: 'department_name' },
  { table: 'departments', column: 'department_id' },
  { table: 'departments', column: 'tenant_id' },
  { table: 'employees', column: 'employee_id' },
  { table: 'employees', column: 'department_id' },
  { table: 'employees', column: 'tenant_id' },
  { table: 'employees', column: 'employment_status' }
];
const outputAlias = { table: null, column: 'employee_count', referenceType: 'OUTPUT_ALIAS' };
const analysis = (columns = [...baseColumns, outputAlias]) => ({
  statementType: 'SELECT', normalizedSql: sql,
  tables: [{ name: 'employees', alias: 'e' }, { name: 'departments', alias: 'd' }],
  columns, filters: [{ table: 'employees', column: 'tenant_id', operator: '=', value: 101 }], joins: []
});

function useHrms(t) {
  const previous = process.env.MYSQL_DATABASE;
  process.env.MYSQL_DATABASE = 'enterprise_hrms_alpha';
  t.after(() => { if (previous === undefined) delete process.env.MYSQL_DATABASE; else process.env.MYSQL_DATABASE = previous; });
}

test('joined aggregate ORDER BY alias is not an ambiguous physical column', (t) => {
  useHrms(t);
  const result = checkTableColumns(analysis(), policy, sql);
  assert.equal(result.status, 'PASS', result.message);
  assert.deepEqual(result.ambiguousColumns, []);
});

test('output aliases cannot conceal denied aggregate source columns', (t) => {
  useHrms(t);
  const result = checkTableColumns(analysis(), { ...policy, deniedColumns: ['employees.employee_id'] }, sql);
  assert.equal(result.status, 'FAIL');
  assert.equal(result.reason, 'BLOCKED_COLUMN');
});

test('same-named physical WHERE references and undeclared order names remain checked', (t) => {
  useHrms(t);
  const extra = { table: null, column: 'employee_count' };
  for (const [query, columns] of [
    [sql.replace('WHERE ', 'WHERE employee_count = 1 AND '), [...baseColumns, outputAlias, extra]],
    [sql.replace('AS employee_count', 'AS different_name'), [...baseColumns, extra]]
  ]) {
    const result = checkTableColumns(analysis(columns), policy, query);
    assert.equal(result.reason, 'AMBIGUOUS_COLUMN');
  }
});

test('qualified references are never exempted as output aliases', (t) => {
  useHrms(t);
  const result = checkTableColumns(analysis([...baseColumns, { ...outputAlias, table: 'employees' }]),
    policy, sql.replace('ORDER BY employee_count', 'ORDER BY e.employee_count'));
  assert.equal(result.status, 'FAIL');
  assert.equal(result.reason, 'COLUMN_NOT_ALLOWED');
});

test('aggregate alias passes access checks and reaches tenant repair and final verification', async (t) => {
  useHrms(t);
  const finalSql = sql.replace("AND e.employment_status", "AND d.tenant_id = 101 AND e.employment_status");
  const repairs = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    const request = JSON.parse(options.body);
    if (String(url).endsWith('/inspect')) return { ok: true, json: async () => ({ success: true, analysis: analysis() }) };
    assert.match(String(url), /\/tenant-isolation$/);
    repairs.push(request.repair);
    return { ok: true, json: async () => ({ success: true, tenantRewrite: {
      status: request.repair ? 'REPAIRED' : 'UNCHANGED_VERIFIED', applied: request.repair,
      finalVerification: 'PASS', rowFiltersVerified: true, finalSql,
      parameterizedSql: finalSql.replaceAll('= 101', '= ?'), parameters: ['101', '101'],
      changes: request.repair ? [{ alias: 'd', action: 'ADD_MISSING_TENANT_FILTER' }] : [], findings: [], message: 'Verified.'
    } }) };
  });
  const result = await verifySql({ sql, policy, user: { userId: 'manager', tenantId: 101, role: 'MANAGER' }, repairTenant: true });
  assert.equal(result.passed, true, JSON.stringify(result));
  assert.deepEqual(repairs, [true, false]);
  assert.equal(result.tenantRewrite.status, 'REPAIRED');
  assert.match(result.finalSql, /d\.tenant_id = 101/);
});
