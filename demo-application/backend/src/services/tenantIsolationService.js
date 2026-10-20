const { resolvePolicyValues } = require('../utils/resolvePolicyValues');
const { getRules } = require('../security/sql/tenantChecker');

const VERIFIED = new Set(['REPAIRED', 'UNCHANGED_VERIFIED']);

function stopped(status, reasonCode, message, sql) {
  return { status, applied: false, reasonCode, message, originalSql: sql, finalSql: null,
    changes: [], findings: [], finalVerification: 'FAIL', method: 'DETERMINISTIC_AST' };
}

async function enforceTenantIsolation({ sql, policy, user, dialect = 'mysql', repair = true }) {
  const tenantId = user?.tenantId;
  if ((typeof tenantId !== 'string' && typeof tenantId !== 'number')
      || (typeof tenantId === 'number' && !Number.isSafeInteger(tenantId))
      || !/^[1-9][0-9]{0,18}$/.test(String(tenantId))) {
    return stopped('BLOCKED', 'INVALID_TENANT_CONTEXT', 'Supply a positive integer tenantId; use a string for large identifiers.', sql);
  }
  let rules;
  try {
    const effective = resolvePolicyValues(policy, user);
    rules = getRules(effective).map(({ table, column, operator, value }) => ({ table, column, operator, value }));
  } catch (error) {
    return stopped('BLOCKED', 'INVALID_POLICY', error.message, sql);
  }
  const inspectionUrl = process.env.SQLGLOT_SERVICE_URL || 'http://127.0.0.1:8001/inspect';
  try {
    const url = process.env.TENANT_ISOLATION_SERVICE_URL || new URL('tenant-isolation', inspectionUrl).href;
    const response = await fetch(url, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql, tenant_id: String(tenantId), rules, dialect, repair }),
      signal: AbortSignal.timeout(5000)
    });
    const payload = await response.json();
    const result = payload.tenantRewrite;
    if (!response.ok || payload.success !== true || !result
        || !['REPAIRED', 'UNCHANGED_VERIFIED', 'CANNOT_REPAIR', 'BLOCKED'].includes(result.status)
        || !Array.isArray(result.changes) || !Array.isArray(result.findings)) {
      throw new Error('Invalid isolation service response');
    }
    if (VERIFIED.has(result.status) && (result.finalVerification !== 'PASS'
        || result.rowFiltersVerified !== true || typeof result.finalSql !== 'string' || !result.finalSql.trim()
        || typeof result.parameterizedSql !== 'string' || !Array.isArray(result.parameters)
        || !result.parameters.length || result.parameters.some((value) => value !== String(tenantId))
        || (!repair && (result.status !== 'UNCHANGED_VERIFIED' || result.applied || result.changes.length)))) {
      throw new Error('Invalid verified isolation artifact');
    }
    return { ...result, originalSql: sql };
  } catch {
    return stopped('UNAVAILABLE', 'TENANT_ISOLATION_UNAVAILABLE',
      'Tenant isolation could not be verified. Check or restart the SQLGlot service; no query was executed.', sql);
  }
}

module.exports = { enforceTenantIsolation, stopped, VERIFIED };
