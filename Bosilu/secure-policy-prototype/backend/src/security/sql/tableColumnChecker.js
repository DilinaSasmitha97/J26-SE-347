function normalized(value) {
  return String(value || '').trim().toLowerCase();
}

function checkTableColumns(sqlAnalysis, policy) {
  const tables = Array.isArray(sqlAnalysis?.tables) ? sqlAnalysis.tables : [];
  const columns = Array.isArray(sqlAnalysis?.columns) ? sqlAnalysis.columns : [];
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

  return {
    status: problems.length ? 'FAIL' : 'PASS',
    reason: blockedTables.length
      ? 'TABLE_NOT_ALLOWED'
      : (blockedColumns.length
        ? 'BLOCKED_COLUMN'
        : (ambiguousColumns.length ? 'AMBIGUOUS_COLUMN' : null)),
    message: problems.length
      ? `${problems.join('. ')}.`
      : `${usedTables.join(', ')} and ${resolvedColumns.length} referenced ${resolvedColumns.length === 1 ? 'column are' : 'columns are'} allowed.`,
    usedTables,
    checkedColumns: resolvedColumns,
    blockedTables,
    blockedColumns,
    ambiguousColumns
  };
}

module.exports = { checkTableColumns };
