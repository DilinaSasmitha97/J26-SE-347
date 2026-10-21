const test = require('node:test');
const assert = require('node:assert/strict');
const { traceSqlSafety } = require('../src/security/sql/astTrace');
const { validateWithSecurityLayer } = require('../src/services/secureQueryService');

const trace = (sql) => traceSqlSafety(sql, validateWithSecurityLayer(sql));
const stage = (result, id) => result.stages.find((item) => item.id === id);
const labels = (node) => (node ? [node.label, ...node.children.flatMap(labels)] : []);

test('safe query yields a clause tree and only passing rules', () => {
  const result = trace('SELECT COUNT(e.id) FROM employees e JOIN departments d ON e.department_id = d.id WHERE e.tenant_id = 101');
  assert.equal(result.safe, true);
  assert.equal(result.tree.label, 'SELECT');
  assert.deepEqual(result.tree.children.map((child) => child.label), ['SELECT list', 'FROM', 'WHERE']);
  assert.ok(labels(result.tree).includes('INNER JOIN departments d'));
  assert.ok(result.stages.every((item) => item.status === 'pass'));
});

test('rule status follows the validator and the offending nodes are flagged', () => {
  const result = trace('SELECT * FROM users WHERE id = 5 OR 1=1 UNION SELECT user, password FROM mysql.user');
  assert.equal(result.safe, false);
  for (const id of ['tautology', 'union', 'system_schemas']) assert.equal(stage(result, id).status, 'fail', id);
  assert.equal(stage(result, 'functions').status, 'pass');
  const flagged = [];
  const walk = (node) => { if (node.flagged) flagged.push(node.label); node.children.forEach(walk); };
  walk(result.tree);
  assert.deepEqual(flagged.sort(), ['UNION', 'WHERE', 'mysql.user']);
});

test('unparseable input has no tree and skips the AST rules', () => {
  const result = trace('SELECT 1; DROP TABLE x');
  assert.equal(result.tree, null);
  assert.equal(stage(result, 'single_statement').status, 'fail');
  assert.equal(stage(result, 'parse').status, 'fail');
  assert.equal(stage(result, 'functions').status, 'skipped');
  assert.equal(stage(result, 'comments').status, 'pass');
});
