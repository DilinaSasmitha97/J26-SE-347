const test = require('node:test');
const assert = require('node:assert/strict');
const { checkTenant } = require('../src/security/sql/tenantChecker');

const user = { userId: 'user-1', tenantId: 101, departmentId: 1 };
const policy = {
  allowedTables: ['employees', 'departments'],
  requiredFilters: [
    { table: 'employees', column: 'tenant_id', operator: '=', valueFrom: 'tenantId' }
  ]
};

function analysis(overrides = {}) {
  return {
    tables: [{ name: 'employees' }],
    filters: [{ table: null, column: 'tenant_id', operator: '=', value: 101 }],
    ...overrides
  };
}

test('resolves an unqualified tenant filter for one table', () => {
  const result = checkTenant(analysis(), policy, user);
  assert.equal(result.status, 'PASS');
  assert.equal(result.checkedRules[0].value, 101);
});

test('resolves a valueFrom policy rule from authenticated user claims', () => {
  const result = checkTenant(analysis(), policy, { ...user, tenantId: '101' });
  assert.equal(result.status, 'PASS');
});

test('fails when the tenant filter is missing', () => {
  const result = checkTenant(analysis({ filters: [] }), policy, user);
  assert.equal(result.reason, 'MISSING_TENANT_FILTER');
});

test('fails when a different tenant is requested', () => {
  const result = checkTenant(analysis({
    filters: [{ table: null, column: 'tenant_id', operator: '=', value: 202 }]
  }), policy, user);
  assert.equal(result.reason, 'WRONG_TENANT');
});

test('fails unsafe tenant operators', () => {
  const result = checkTenant(analysis({
    filters: [{ table: null, column: 'tenant_id', operator: '!=', value: 101 }]
  }), policy, user);
  assert.equal(result.reason, 'INVALID_TENANT_OPERATOR');
});

test('fails unsupported tenant expressions', () => {
  const result = checkTenant(analysis({
    filters: [{ type: 'UNSUPPORTED', raw: 'tenant_id = 101 OR tenant_id = 202' }]
  }), policy, user);
  assert.equal(result.reason, 'UNSAFE_TENANT_EXPRESSION');
});

test('fails ambiguous unqualified tenant filters across joined tables', () => {
  const joinedPolicy = {
    requiredFilters: [
      { table: 'employees', field: 'tenant_id', valueFrom: 'tenantId' },
      { table: 'departments', field: 'tenant_id', valueFrom: 'tenantId' }
    ]
  };
  const result = checkTenant(analysis({
    tables: [{ name: 'employees' }, { name: 'departments' }]
  }), joinedPolicy, user);
  assert.equal(result.reason, 'AMBIGUOUS_TENANT_COLUMN');
});

test('requires tenant isolation for every referenced tenant-scoped table', () => {
  const joinedPolicy = {
    requiredFilters: [
      { table: 'employees', field: 'tenant_id', valueFrom: 'tenantId' },
      { table: 'departments', field: 'tenant_id', valueFrom: 'tenantId' }
    ]
  };
  const result = checkTenant(analysis({
    tables: [{ name: 'employees' }, { name: 'departments' }],
    filters: [{ table: 'employees', column: 'tenant_id', operator: '=', value: 101 }]
  }), joinedPolicy, user);
  assert.equal(result.reason, 'MISSING_TENANT_FILTER');
  assert.match(result.message, /departments/);
});

test('fails when literal policy tenant conflicts with authenticated tenant', () => {
  const conflictingPolicy = {
    requiredFilters: [{ table: 'employees', field: 'tenant_id', value: 202 }]
  };
  const result = checkTenant(analysis(), conflictingPolicy, user);
  assert.equal(result.reason, 'POLICY_USER_TENANT_MISMATCH');
});

test('fails when the policy has no tenant rules', () => {
  const result = checkTenant(analysis(), { allowedTables: ['employees'] }, user);
  assert.equal(result.reason, 'NO_TENANT_POLICY');
});
