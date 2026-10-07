const { checkAccess } = require('./checkAccess');

/**
 * Maps a sample natural language question to its corresponding table and column intent.
 * (In later phases, this will be handled by an LLM parser / semantic router).
 *
 * @param {string} question - User question
 * @returns {object|null} Intent object { table, columns } or null if unknown
 */
function resolveQuestionIntent(question) {
  const normalized = (question || '').trim().toLowerCase();

  if (normalized.includes('employee name') || normalized.includes('employee names')) {
    return { table: 'employees', columns: ['name'] };
  }
  if (normalized.includes('department') || normalized.includes('departments')) {
    return { table: 'departments', columns: ['name'] };
  }
  if (normalized.includes('job title') || normalized.includes('job titles')) {
    return { table: 'employees', columns: ['job_title'] };
  }
  if (normalized.includes('salary') || normalized.includes('salaries')) {
    return { table: 'employees', columns: ['salary'] };
  }
  if (normalized.includes('project') || normalized.includes('audit')) {
    return { table: 'financial_audits', columns: ['amount'] };
  }

  // Fallback default: attempt to parse basic table and column
  return null;
}

/**
 * Creates a pre-generation security contract for an incoming natural language question
 * based on the user's effective policy.
 *
 * @param {object} effectivePolicy - The resolved policy for the current user
 * @param {string} question - The user's natural language question
 * @returns {object} Pre-generation contract defining allowed constraints or denial reason
 */
function createGenerationContract(effectivePolicy, question) {
  const intent = resolveQuestionIntent(question);

  if (!intent) {
    return {
      status: 'BLOCKED',
      decision: 'DENY',
      question,
      reason: 'UNRECOGNIZED_INTENT'
    };
  }

  // Validate the requested table and columns against the effective policy
  const accessCheck = checkAccess(effectivePolicy, intent);

  if (accessCheck.decision === 'DENY') {
    return {
      status: 'BLOCKED',
      decision: 'DENY',
      question,
      reason: accessCheck.reason,
      column: accessCheck.column || null
    };
  }

  // Build the generation contract
  return {
    status: 'APPROVED',
    decision: 'ALLOW',
    question,
    table: intent.table,
    columns: intent.columns,
    allowedTables: effectivePolicy.allowedTables || [],
    deniedColumns: effectivePolicy.deniedColumns || [],
    requiredFilters: accessCheck.filters || []
  };
}

module.exports = {
  createGenerationContract,
  resolveQuestionIntent
};
