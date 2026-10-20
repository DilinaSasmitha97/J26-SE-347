const test = require('node:test');
const assert = require('node:assert/strict');
const { evaluateSqlSecurity } = require('../src/security/sql/securityEvaluator');

const policy = {
  policyId: 'test-policy',
  allowedOperations: ['SELECT'],
  allowedTables: ['employees'],
  deniedColumns: ['employees.salary'],
  requiredFilters: [
    { table: 'employees', column: 'tenant_id', operator: '=', valueFrom: 'tenantId' },
    { table: 'employees', column: 'department_id', operator: '=', valueFrom: 'departmentId' }
  ]
};

const user = {
  userId: 'user-1',
  role: 'MANAGER',
  tenantId: 101,
  departmentId: 1
};

function analysis(overrides = {}) {
  return {
    statementType: 'SELECT',
    normalizedSql: 'SELECT first_name FROM employees WHERE tenant_id = 101 AND department_id = 1',
    tables: [{ name: 'employees', alias: null }],
    columns: [
      { table: null, column: 'first_name' },
      { table: null, column: 'tenant_id' },
      { table: null, column: 'department_id' }
    ],
    filters: [
      { table: null, column: 'tenant_id', operator: '=', value: 101 },
      { table: null, column: 'department_id', operator: '=', value: 1 }
    ],
    joins: [],
    ...overrides
  };
}

test('passes a compliant query', () => {
  const result = evaluateSqlSecurity(analysis(), policy, user);
  assert.equal(result.decision, 'PASS');
  assert.ok(result.checks.every((check) => check.passed));
});

test('fails a restricted column', () => {
  const result = evaluateSqlSecurity(analysis({
    columns: [{ table: null, column: 'salary' }]
  }), policy, user);
  assert.equal(result.decision, 'FAIL');
  assert.match(result.checks[1].message, /employees\.salary/);
});

test('fails a cross-tenant filter', () => {
  const result = evaluateSqlSecurity(analysis({
    filters: [
      { table: null, column: 'tenant_id', operator: '=', value: 102 },
      { table: null, column: 'department_id', operator: '=', value: 1 }
    ]
  }), policy, user);
  assert.equal(result.decision, 'FAIL');
  assert.equal(result.checks[2].reason, 'WRONG_TENANT');
});

test('fails an unauthorized table', () => {
  const result = evaluateSqlSecurity(analysis({
    tables: [{ name: 'payroll_secrets', alias: null }],
    columns: [{ table: null, column: '*' }],
    filters: []
  }), policy, user);
  assert.equal(result.decision, 'FAIL');
  assert.equal(result.checks[1].reason, 'TABLE_NOT_ALLOWED');
});

test('fails closed when a column cannot be assigned to one of multiple tables', () => {
  const result = evaluateSqlSecurity(analysis({
    tables: [{ name: 'employees' }, { name: 'departments' }],
    columns: [{ table: null, column: 'name' }]
  }), { ...policy, allowedTables: ['employees', 'departments'] }, user);
  assert.equal(result.decision, 'FAIL');
  assert.equal(result.checks[1].reason, 'AMBIGUOUS_COLUMN');
});
