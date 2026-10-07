/**
 * Simulates a natural language to SQL generation step.
 * In production, an LLM would generate the query guided by prompt-injected policy rules.
 * Here, it deterministically crafts SQL respecting the Generation Contract.
 *
 * Supported questions:
 * - "Show employee names"
 * - "Show departments"
 * - "Show employee job titles"
 *
 * @param {string} question - The user's question
 * @param {object} generationContract - Pre-generation contract with allowed table, columns, and required filters
 * @returns {string} The generated SQL query
 * @throws {Error} If generation contract blocks access or question is unhandled
 */
function generateSql(question, generationContract) {
  if (!generationContract || generationContract.status === 'BLOCKED') {
    throw new Error(
      `SQL generation blocked by policy contract. Reason: ${generationContract?.reason || 'UNKNOWN_REASON'}`
    );
  }

  const { table, columns, requiredFilters } = generationContract;
  const selectClause = `SELECT ${columns.join(', ')}`;
  const fromClause = `FROM ${table}`;

  let whereClause = '';
  if (Array.isArray(requiredFilters) && requiredFilters.length > 0) {
    const filterClauses = requiredFilters.map((filter) => {
      const formattedValue = typeof filter.value === 'string' ? `'${filter.value}'` : filter.value;
      return `${filter.field} ${filter.operator} ${formattedValue}`;
    });
    whereClause = `\nWHERE ${filterClauses.join('\nAND ')}`;
  }

  return `${selectClause}\n${fromClause}${whereClause};`;
}

module.exports = {
  generateSql
};
