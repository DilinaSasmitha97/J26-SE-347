const { checkTableColumns } = require('./tableColumnChecker');
const { checkTenant } = require('./tenantChecker');
const { checkRowFilters } = require('./rowFilterChecker');

function toCheck(label, result) {
  return {
    label,
    passed: result.status === 'PASS',
    status: result.status,
    reason: result.reason,
    message: result.message
  };
}

function evaluateSqlSecurity(sqlAnalysis, policy, user, sql, verifiedIsolation = null) {
  const operation = String(sqlAnalysis?.statementType || 'UNKNOWN').toUpperCase();
  const allowedOperations = Array.isArray(policy?.allowedOperations)
    ? policy.allowedOperations.map((item) => String(item).toUpperCase())
    : ['SELECT'];
  const operationResult = {
    status: allowedOperations.includes(operation) ? 'PASS' : 'FAIL',
    reason: allowedOperations.includes(operation) ? null : 'OPERATION_NOT_ALLOWED',
    message: allowedOperations.includes(operation)
      ? `${operation} is permitted by this policy.`
      : `${operation} is not an allowed operation.`
  };
  const tableColumnResult = checkTableColumns(sqlAnalysis, policy, sql);
  // This optional result is produced only by the server's independent AST
  // verification stage; never populate it from request JSON.
  const tenantResult = verifiedIsolation?.tenantResult || checkTenant(sqlAnalysis, policy, user);
  const rowFilterResult = verifiedIsolation?.rowFilterResult || checkRowFilters(sqlAnalysis, policy, user);
  const checks = [
    toCheck('Statement type', operationResult),
    toCheck('Table & column access', tableColumnResult),
    toCheck('Tenant isolation', tenantResult),
    toCheck('Required filters', rowFilterResult)
  ];
  const passed = checks.every((check) => check.passed);

  return {
    passed,
    decision: passed ? 'PASS' : 'FAIL',
    message: passed
      ? 'Query complies with the active user policy and can proceed.'
      : 'Query was stopped because one or more policy checks failed.',
    checks,
    context: {
      policyId: policy.policyId || 'Unnamed policy',
      userId: user.userId || user.sub || 'Unknown user',
      role: user.role || 'Unspecified',
      tables: tableColumnResult.usedTables || [],
      columns: (tableColumnResult.checkedColumns || []).map((column) => column.column),
      normalizedSql: sqlAnalysis.normalizedSql || ''
    }
  };
}

module.exports = { evaluateSqlSecurity };
