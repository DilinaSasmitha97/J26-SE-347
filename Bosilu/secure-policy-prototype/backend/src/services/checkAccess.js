/**
 * Evaluates whether a requested query is permitted by the effective policy.
 * If permitted, collects and attaches row-level filters scoped to the requested table.
 *
 * @param {object} policy - The resolved effective policy object
 * @param {object} request - The query request containing table and columns
 * @returns {object} Decision object (ALLOW with attached filters or DENY with reason)
 */
function checkAccess(policy, request) {
  // 1. Check if the requested table is allowed
  if (!policy.allowedTables || !policy.allowedTables.includes(request.table)) {
    return {
      decision: "DENY",
      reason: "TABLE_NOT_ALLOWED"
    };
  }

  // 2. Check if any requested column is denied
  if (Array.isArray(request.columns)) {
    for (const column of request.columns) {
      const fullColumnName = `${request.table}.${column}`;

      if (policy.deniedColumns && policy.deniedColumns.includes(fullColumnName)) {
        return {
          decision: "DENY",
          reason: "COLUMN_NOT_ALLOWED",
          column: fullColumnName
        };
      }
    }
  }

  // 4. Collect only rowRules that belong to the requested table
  // 5. Put those rules into a "filters" array (extracting field, operator, value)
  const filters = (policy.rowRules || [])
    .filter((rule) => rule.table === request.table)
    .map((rule) => ({
      field: rule.field,
      operator: rule.operator,
      value: rule.value
    }));

  // 6. Return ALLOW + table + columns + filters
  return {
    decision: "ALLOW",
    table: request.table,
    columns: request.columns,
    filters
  };
}

module.exports = { checkAccess };
