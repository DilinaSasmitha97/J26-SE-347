// src/security/sql/tenantChecker.js

const TENANT_COLUMN = 'tenant_id';
const SUPPORTED_TENANT_OPERATOR = '=';

function normalizeName(value) {
  return value === null || value === undefined
    ? ''
    : String(value).trim().toLowerCase();
}

function valuesEqual(actual, expected) {
  if (actual === null || actual === undefined || expected === null || expected === undefined) {
    return actual === expected;
  }
  return String(actual).trim() === String(expected).trim();
}

function getPolicyRules(policy) {
  const sources = [
    policy?.rowRules,
    policy?.requiredFilters,
    policy?.mandatoryFilters
  ];
  const rules = [];
  const seen = new Set();

  for (const source of sources) {
    if (!Array.isArray(source)) continue;

    for (const rule of source) {
      const normalizedRule = {
        table: normalizeName(rule?.table),
        column: normalizeName(rule?.column || rule?.field),
        operator: String(rule?.operator || '=').trim().toUpperCase(),
        value: rule?.value,
        valueFrom: rule?.valueFrom || null
      };
      const key = JSON.stringify(normalizedRule);
      if (!seen.has(key)) {
        seen.add(key);
        rules.push(normalizedRule);
      }
    }
  }

  return rules;
}

function getTenantRules(policy) {
  return getPolicyRules(policy).filter((rule) => rule.column === TENANT_COLUMN);
}

function resolveExpectedValue(rule, user, policy) {
  if (rule.value !== undefined && rule.value !== null) return rule.value;
  if (rule.valueFrom) return user?.[rule.valueFrom];
  return user?.tenantId ?? policy?.tenantId;
}

function resolveFilterTable(filter, usedTables) {
  const explicitTable = normalizeName(filter?.table);
  if (explicitTable) return explicitTable;
  return usedTables.length === 1 ? usedTables[0] : null;
}

function filterMatchesRule(filter, rule, user, usedTables, policy = {}) {
  if (!filter || filter.type === 'UNSUPPORTED') return false;
  const table = resolveFilterTable(filter, usedTables);
  const expectedValue = resolveExpectedValue(rule, user, policy);
  return table === normalizeName(rule.table)
    && normalizeName(filter.column) === normalizeName(rule.column || rule.field)
    && String(filter.operator || '').trim().toUpperCase() === String(rule.operator || '=').trim().toUpperCase()
    && valuesEqual(filter.value, expectedValue);
}

function failure(reason, message, details = {}) {
  return {
    status: 'FAIL',
    reason,
    message,
    ...details
  };
}

/**
 * Validates tenant isolation using SQLGlot's extracted tables and filters.
 * Policy values may be literal or resolved from authenticated user claims.
 * Any ambiguous or unsupported tenant expression fails closed.
 */
function checkTenant(sqlAnalysis, effectivePolicy, authenticatedUser) {
  if (!sqlAnalysis || typeof sqlAnalysis !== 'object') {
    return failure('MISSING_SQL_ANALYSIS', 'SQL analysis was not provided.');
  }
  if (!effectivePolicy || typeof effectivePolicy !== 'object') {
    return failure('MISSING_POLICY', 'Effective policy was not provided.');
  }
  if (!authenticatedUser || typeof authenticatedUser !== 'object') {
    return failure('MISSING_AUTHENTICATED_USER', 'Authenticated user data was not provided.');
  }

  const filters = Array.isArray(sqlAnalysis.filters) ? sqlAnalysis.filters : [];
  const usedTables = (Array.isArray(sqlAnalysis.tables) ? sqlAnalysis.tables : [])
    .map((table) => normalizeName(table?.name))
    .filter(Boolean);
  const tenantRules = getTenantRules(effectivePolicy);

  if (tenantRules.length === 0) {
    return failure(
      'NO_TENANT_POLICY',
      'No tenant restriction was found in the effective policy.'
    );
  }

  for (const rule of tenantRules) {
    if (!rule.table) {
      return failure(
        'INVALID_TENANT_POLICY',
        'A tenant policy rule does not identify its table.',
        { rule }
      );
    }
    if (rule.operator !== SUPPORTED_TENANT_OPERATOR) {
      return failure(
        'INVALID_TENANT_POLICY_OPERATOR',
        `Tenant policy for '${rule.table}' must use the equality operator.`,
        { rule }
      );
    }

    const expectedValue = resolveExpectedValue(rule, authenticatedUser, effectivePolicy);
    if (expectedValue === undefined || expectedValue === null || String(expectedValue).trim() === '') {
      return failure(
        'UNRESOLVED_TENANT_VALUE',
        `Tenant value for '${rule.table}' could not be resolved from the authenticated user.`,
        { rule }
      );
    }

    if (
      authenticatedUser.tenantId !== undefined
      && authenticatedUser.tenantId !== null
      && !valuesEqual(expectedValue, authenticatedUser.tenantId)
    ) {
      return failure(
        'POLICY_USER_TENANT_MISMATCH',
        `Tenant policy for '${rule.table}' does not match the authenticated tenant.`,
        { expectedTenantId: authenticatedUser.tenantId, policyTenantId: expectedValue }
      );
    }
  }

  const unsupportedTenantFilters = filters.filter((filter) => {
    if (filter?.type !== 'UNSUPPORTED') return false;
    return /(^|\W)tenant_id(\W|$)/i.test(String(filter.raw || ''));
  });
  if (unsupportedTenantFilters.length) {
    return failure(
      'UNSAFE_TENANT_EXPRESSION',
      'A tenant condition could not be safely evaluated.',
      { filters: unsupportedTenantFilters }
    );
  }

  const normalizedTenantFilters = filters
    .filter((filter) => filter?.type !== 'UNSUPPORTED')
    .filter((filter) => normalizeName(filter?.column) === TENANT_COLUMN)
    .map((filter) => ({
      ...filter,
      table: resolveFilterTable(filter, usedTables),
      operator: String(filter.operator || '').trim().toUpperCase()
    }));

  const ambiguousFilters = normalizedTenantFilters.filter((filter) => !filter.table);
  if (ambiguousFilters.length) {
    return failure(
      'AMBIGUOUS_TENANT_COLUMN',
      'An unqualified tenant_id condition is ambiguous across multiple tables.',
      { filters: ambiguousFilters }
    );
  }

  const applicableRules = tenantRules.filter((rule) => usedTables.includes(rule.table));
  const tenantScopedTables = new Set(tenantRules.map((rule) => rule.table));
  const unexpectedTenantFilters = normalizedTenantFilters.filter(
    (filter) => !tenantScopedTables.has(filter.table)
  );
  if (unexpectedTenantFilters.length) {
    return failure(
      'UNEXPECTED_TENANT_FILTER',
      'The query applies tenant_id to a table not covered by the tenant policy.',
      { filters: unexpectedTenantFilters }
    );
  }

  const checkedRules = [];
  for (const rule of applicableRules) {
    const expectedValue = resolveExpectedValue(rule, authenticatedUser, effectivePolicy);
    const tableFilters = normalizedTenantFilters.filter((filter) => filter.table === rule.table);

    if (tableFilters.length === 0) {
      return failure(
        'MISSING_TENANT_FILTER',
        `Required tenant filter is missing for table '${rule.table}'.`,
        { expected: { table: rule.table, column: TENANT_COLUMN, operator: '=', value: expectedValue } }
      );
    }

    const unsafeOperator = tableFilters.find(
      (filter) => filter.operator !== SUPPORTED_TENANT_OPERATOR
    );
    if (unsafeOperator) {
      return failure(
        'INVALID_TENANT_OPERATOR',
        `Tenant filter for '${rule.table}' must use the equality operator.`,
        { filter: unsafeOperator }
      );
    }

    const wrongValue = tableFilters.find(
      (filter) => !valuesEqual(filter.value, expectedValue)
    );
    if (wrongValue) {
      return failure(
        'WRONG_TENANT',
        `Wrong tenant ID used for table '${rule.table}'.`,
        { expectedTenantId: expectedValue, actualTenantId: wrongValue.value }
      );
    }

    checkedRules.push({
      table: rule.table,
      column: TENANT_COLUMN,
      operator: SUPPORTED_TENANT_OPERATOR,
      value: expectedValue,
      status: 'PASS'
    });
  }

  return {
    status: 'PASS',
    reason: null,
    message: applicableRules.length
      ? `Tenant isolation verified for ${applicableRules.length} referenced ${applicableRules.length === 1 ? 'table' : 'tables'}.`
      : 'No referenced table requires tenant isolation.',
    tenantId: authenticatedUser.tenantId ?? effectivePolicy.tenantId ?? null,
    checkedRules
  };
}

module.exports = {
  checkTenant,
  getRules: getPolicyRules,
  getTenantRules,
  resolveRuleValue: (rule, user) => resolveExpectedValue(rule, user, {}),
  resolveExpectedValue,
  filterMatchesRule,
  valuesEqual
};
