const test = require('node:test');
const assert = require('node:assert/strict');
const {
  buildPolicyAllowlist,
  validateWithSecurityLayer,
  policyToInjectedRules
} = require('../src/services/secureQueryService');

const policy = {
  allowedTables: ['employees', 'departments'],
  deniedColumns: ['employees.date_of_birth', 'employees.nic_number'],
  rowRules: [
    { table: 'employees', field: 'tenant_id', operator: '=', value: 101 },
    { table: 'employees', field: 'department_id', operator: '=', value: 1 }
  ]
};

test('builds an allowlist from the canonical schema and removes denied columns', () => {
  const allowlist = buildPolicyAllowlist(policy, 'multi_tenant_hr');
  assert.deepEqual(Object.keys(allowlist), ['employees', 'departments']);
  assert.ok(allowlist.employees.includes('work_email'));
  assert.ok(!allowlist.employees.includes('date_of_birth'));
  assert.ok(!allowlist.employees.includes('nic_number'));
});

test('Navodya validation accepts a compliant read query', () => {
  const result = validateWithSecurityLayer(
    'SELECT e.first_name, e.work_email FROM employees e WHERE e.tenant_id = 101 AND e.department_id = 1',
    policy
  );
  assert.equal(result.safe, true);
  assert.equal(result.statementType, 'SELECT');
});

test('Navodya validation blocks policy-denied columns', () => {
  const result = validateWithSecurityLayer(
    'SELECT e.nic_number FROM employees e WHERE e.tenant_id = 101 AND e.department_id = 1',
    policy
  );
  assert.equal(result.safe, false);
  assert.ok(result.violations.some((item) => item.type === 'column_not_allowed'));
});

test('Navodya validation blocks destructive statements', () => {
  const result = validateWithSecurityLayer('DROP TABLE employees', policy);
  assert.equal(result.safe, false);
  assert.ok(result.violations.some((item) => item.type === 'blocked_statement_type'));
});

test('authoritative prompt rules contain resolved policy filters', () => {
  const rules = policyToInjectedRules(policy);
  assert.match(rules, /employees\.tenant_id = 101/);
  assert.match(rules, /employees\.department_id = 1/);
  assert.match(rules, /employees\.nic_number/);
});
