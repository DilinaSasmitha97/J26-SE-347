const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { resolvePolicyValues } = require('../../backend/src/utils/resolvePolicyValues');
const { parse, checkAllowlist } = require('../../packages/security-validation-layer');
const read = name => JSON.parse(fs.readFileSync(path.join(__dirname, name), 'utf8'));
const schema = read('schema-allowlist.entry.json').enterprise_hrms_alpha;
const output = { resolved: {}, access_checks: [] };

for (const key of ['01-employee', '02-manager', '03-admin']) {
  const policy = read(`${key}.policy.json`);
  const user = read(`${key}.user.json`);
  const rules = read(`${key}.rules.json`);
  const resolved = resolvePolicyValues(policy, user);
  assert.equal(rules.role, user.role);
  for (const rule of policy.rowRules) {
    if (rule.valueFrom) assert.equal(rules.context[rule.valueFrom], user[rule.valueFrom]);
  }
  output.resolved[key] = resolved.rowRules.map(({ table, field, operator, value }) => ({ table, column: field, operator, value }));
  const denied = new Set(policy.deniedColumns);
  const allowlist = Object.fromEntries(policy.allowedTables.map(table => [table, schema[table].filter(col => !denied.has(`${table}.${col}`))]));
  const samples = {
    '01-employee': [
      ['self_name', 'SELECT e.full_name FROM employees e WHERE e.tenant_id=101 AND e.employee_id=1001', true],
      ['denied_id_aggregate', 'SELECT COUNT(DISTINCT e.national_id_number) FROM employees e WHERE e.tenant_id=101 AND e.employee_id=1001', false],
      ['denied_project', 'SELECT p.project_name FROM projects p WHERE p.tenant_id=101', false],
      ['denied_bank_transform', 'SELECT RIGHT(b.account_number,4) FROM employee_bank_accounts b WHERE b.tenant_id=101 AND b.employee_id=1001', false],
    ],
    '02-manager': [
      ['department_counts', 'SELECT e.employment_status,COUNT(*) AS employee_count FROM employees e WHERE e.tenant_id=101 AND e.department_id=10 GROUP BY e.employment_status', true],
      ['denied_pay_aggregate', 'SELECT SUM(p.net_pay) FROM payroll_records p WHERE p.tenant_id=101 AND p.department_id=10', false],
      ['denied_attendance', 'SELECT COUNT(*) FROM attendance_records a WHERE a.tenant_id=101', false],
    ],
    '03-admin': [
      ['allowed_pay_aggregate', 'SELECT SUM(p.net_pay) FROM payroll_records p WHERE p.tenant_id=101', true],
      ['denied_storage_uri', 'SELECT d.storage_uri FROM employee_documents_metadata d WHERE d.tenant_id=101', false],
      ['denied_inherited_table', 'SELECT c.amount FROM payroll_components c', false],
    ],
  }[key];
  for (const [name, sql, expected] of samples) {
    const violations = checkAllowlist(parse(sql).ast, allowlist);
    const allowed = violations.length === 0;
    assert.equal(allowed, expected, `${key}: ${name}`);
    output.access_checks.push({ variant: key, name, expected_allowed: expected, passed: true });
  }
}
process.stdout.write(JSON.stringify(output));
