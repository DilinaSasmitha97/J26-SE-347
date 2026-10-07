/**
 * Post-Generation SQL Security Validator
 *
 * Enforces security constraints on generated SQL before execution:
 * 1. Verifies no denied columns are referenced (returns DENY).
 * 2. Verifies unauthorized tables are not accessed (returns DENY).
 * 3. Verifies mandatory multi-tenant row rules (e.g. tenant_id = 101) are present.
 *    If missing, automatically injects them into the AST/query (returns REWRITE).
 * 4. If all checks pass, returns ALLOW.
 *
 * @param {string} sql - The raw generated SQL string
 * @param {object} generationContract - The active generation contract
 * @returns {object} Validation result { decision: 'ALLOW' | 'REWRITE' | 'DENY', ... }
 */
function validateGeneratedSql(sql, generationContract) {
  if (!sql || typeof sql !== 'string') {
    return {
      decision: 'DENY',
      reason: 'INVALID_SQL',
      message: 'SQL query must be a non-empty string.'
    };
  }

  const cleanSql = sql.trim();

  // 1. Check for denied columns (e.g., salary, date_of_birth)
  if (Array.isArray(generationContract.deniedColumns)) {
    for (const fullCol of generationContract.deniedColumns) {
      const parts = fullCol.split('.');
      const colName = parts.length > 1 ? parts[1] : parts[0];

      // Match either full table.column or bare column identifier
      const columnRegex = new RegExp(`\\b(${fullCol}|${colName})\\b`, 'i');
      if (columnRegex.test(cleanSql)) {
        return {
          decision: 'DENY',
          reason: 'DENIED_COLUMN_DETECTED',
          column: fullCol,
          message: `Prohibited column "${fullCol}" detected in generated SQL.`
        };
      }
    }
  }

  // 2. Check for unauthorized tables
  if (Array.isArray(generationContract.allowedTables) && generationContract.allowedTables.length > 0) {
    // Extract table from FROM clause: FROM <table_name>
    const fromMatch = cleanSql.match(/\bFROM\s+([a-zA-Z0-9_]+)/i);
    if (fromMatch) {
      const targetTable = fromMatch[1].toLowerCase();
      const isAllowed = generationContract.allowedTables.some(
        (t) => t.toLowerCase() === targetTable
      );

      if (!isAllowed) {
        return {
          decision: 'DENY',
          reason: 'TABLE_NOT_ALLOWED',
          table: targetTable,
          message: `Table "${targetTable}" is not permitted by policy.`
        };
      }
    }
  }

  // 3. Check for mandatory row filters (e.g. tenant_id = 101, department_id = 1)
  const missingFilters = [];
  const requiredFilters = generationContract.requiredFilters || [];

  for (const filter of requiredFilters) {
    const formattedVal = typeof filter.value === 'string' ? `'?${filter.value}'?` : filter.value;
    // Regex matches: tenant_id = 101 or employees.tenant_id = 101
    const filterRegex = new RegExp(
      `\\b(${generationContract.table}\\.)?${filter.field}\\b\\s*${filter.operator}\\s*${formattedVal}`,
      'i'
    );

    if (!filterRegex.test(cleanSql)) {
      missingFilters.push(filter);
    }
  }

  // If any mandatory filters are absent, REWRITE the SQL by injecting them
  if (missingFilters.length > 0) {
    const rewrittenSql = injectFiltersIntoSql(cleanSql, missingFilters);
    return {
      decision: 'REWRITE',
      reason: 'MISSING_REQUIRED_FILTERS',
      missingFilters,
      originalSql: cleanSql,
      rewrittenSql,
      message: `Enforced tenant isolation: injected ${missingFilters.length} required filter(s).`
    };
  }

  // 4. All validations passed
  return {
    decision: 'ALLOW',
    sql: cleanSql,
    message: 'Generated SQL satisfies all policy and multi-tenant isolation constraints.'
  };
}

/**
 * Deterministically injects missing filter predicates into a SQL query.
 *
 * @param {string} sql - Original SQL query
 * @param {Array<object>} filters - Missing filter rules
 * @returns {string} Rewritten SQL query with injected filters
 */
function injectFiltersIntoSql(sql, filters) {
  let baseSql = sql.trim().replace(/;$/, '');

  const filterStrings = filters.map((f) => {
    const val = typeof f.value === 'string' ? `'${f.value}'` : f.value;
    return `${f.field} ${f.operator} ${val}`;
  });

  const hasWhere = /\bWHERE\b/i.test(baseSql);

  if (hasWhere) {
    baseSql = `${baseSql}\nAND ${filterStrings.join('\nAND ')}`;
  } else {
    baseSql = `${baseSql}\nWHERE ${filterStrings.join('\nAND ')}`;
  }

  return `${baseSql};`;
}

module.exports = {
  validateGeneratedSql,
  injectFiltersIntoSql
};
