const {
  getRules,
  resolveRuleValue,
  filterMatchesRule
} = require('./tenantChecker');

function checkRowFilters(sqlAnalysis, policy, user) {
  const filters = Array.isArray(sqlAnalysis?.filters) ? sqlAnalysis.filters : [];
  const usedTables = (sqlAnalysis?.tables || []).map((table) => table.name).filter(Boolean);
  const rowRules = getRules(policy).filter((rule) => {
    const column = rule.column || rule.field;
    return usedTables.includes(rule.table)
      && column !== 'tenant_id'
      && rule.valueFrom !== 'tenantId';
  });

  const missingRules = rowRules.filter((rule) => {
    const expectedValue = resolveRuleValue(rule, user);
    if (expectedValue === undefined) return true;
    return !filters.some((filter) => filterMatchesRule(filter, rule, user, usedTables));
  });

  return {
    status: missingRules.length ? 'FAIL' : 'PASS',
    reason: missingRules.length ? 'ROW_FILTER_MISMATCH' : null,
    message: missingRules.length
      ? `Missing or incorrect user-scoped filter: ${missingRules.map((rule) => `${rule.table}.${rule.column || rule.field} = ${resolveRuleValue(rule, user) ?? `<${rule.valueFrom}>`}`).join(', ')}.`
      : rowRules.length
        ? `${rowRules.length} user-scoped ${rowRules.length === 1 ? 'filter' : 'filters'} verified.`
        : 'No additional user-scoped filters are required.',
    missingRules
  };
}

module.exports = { checkRowFilters };
