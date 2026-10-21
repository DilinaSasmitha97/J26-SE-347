const { parse, checkAllowlist } = require('security-validation-layer');
const { buildPolicyAllowlist } = require('../../services/secureQueryService');

function normalized(value) {
  return String(value || '').trim().toLowerCase();
}

function checkTableColumns(sqlAnalysis, policy, sql = sqlAnalysis?.normalizedSql) {
  const tables = Array.isArray(sqlAnalysis?.tables) ? sqlAnalysis.tables : [];
  const references = Array.isArray(sqlAnalysis?.columns) ? sqlAnalysis.columns : [];
  // SQLGlot marks only bare ORDER BY aliases in their own SELECT. Their
  // underlying expressions remain physical references and must pass access
  // checks. Do not exempt a qualified or same-named WHERE column.
  const columns = references.filter((column) => column.referenceType !== 'OUTPUT_ALIAS' || column.table);
  const allowedTables = new Set(
    (Array.isArray(policy?.allowedTables) ? policy.allowedTables : []).map(normalized)
  );
  const deniedColumns = new Set(
    (Array.isArray(policy?.deniedColumns) ? policy.deniedColumns : []).map(normalized)
  );
  const usedTables = tables.map((table) => normalized(table.name)).filter(Boolean);

  if (usedTables.length === 0) {
    return {
      status: 'FAIL',
      reason: 'NO_TABLE_FOUND',
      message: 'No table reference was found in the query.',
      usedTables,
      checkedColumns: []
    };
  }

  const blockedTables = usedTables.filter((table) => !allowedTables.has(table));
  const resolvedColumns = columns.map((column) => {
    const table = normalized(column.table)
      || (usedTables.length === 1 ? usedTables[0] : '');
    const name = normalized(column.column);
    return {
      table: table || null,
      column: name,
      qualifiedName: table ? `${table}.${name}` : name
    };
  });
  const ambiguousColumns = resolvedColumns
    .filter((column) => !column.table)
    .map((column) => column.column);
  const blockedColumns = resolvedColumns
    .map((column) => column.qualifiedName)
    .filter((column) => deniedColumns.has(column));

  const problems = [];
  if (blockedTables.length) problems.push(`Blocked table: ${blockedTables.join(', ')}`);
  if (blockedColumns.length) problems.push(`Restricted column: ${blockedColumns.join(', ')}`);
  if (ambiguousColumns.length) {
    problems.push(`Column ownership could not be resolved safely: ${ambiguousColumns.join(', ')}`);
  }

  // Run the schema/policy allowlist here, after SQLGlot inspection. The AST
  // check also covers wildcards and nested queries absent from column summaries.
  const accessViolations = sql
    ? checkAllowlist(parse(sql).ast, buildPolicyAllowlist(policy))
    : [];
  problems.push(...accessViolations.map((violation) => violation.detail));
  let reason = null;
  if (blockedTables.length) reason = 'TABLE_NOT_ALLOWED';
  else if (blockedColumns.length) reason = 'BLOCKED_COLUMN';
  else if (ambiguousColumns.length) reason = 'AMBIGUOUS_COLUMN';
  else if (accessViolations.some((violation) => violation.type === 'table_not_allowed')) reason = 'TABLE_NOT_ALLOWED';
  else if (accessViolations.length) reason = 'COLUMN_NOT_ALLOWED';

  return {
    status: problems.length ? 'FAIL' : 'PASS',
    reason,
    message: problems.length
      ? `${problems.join('. ')}.`
      : `${usedTables.join(', ')} and ${resolvedColumns.length} referenced ${resolvedColumns.length === 1 ? 'column are' : 'columns are'} allowed.`,
    usedTables,
    checkedColumns: resolvedColumns,
    blockedTables,
    blockedColumns,
    ambiguousColumns,
    accessViolations
  };
}

module.exports = { checkTableColumns };
