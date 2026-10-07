const managerPolicy = require('../policies/managerPolicy.json');
const employeePolicy = require('../policies/employeePolicy.json');

/**
 * Retrieves the base policy template for a given role.
 * Ensures the original policy definition is never mutated by returning a deep copy.
 *
 * @param {string} role - The user's role (e.g., 'MANAGER', 'EMPLOYEE')
 * @returns {object} A cloned policy object matching the role
 * @throws {Error} If the role is missing or has no associated policy
 */
function getPolicyForRole(role) {
  if (!role || typeof role !== 'string') {
    throw new Error('Invalid role provided. Role must be a non-empty string.');
  }

  const normalizedRole = role.trim().toUpperCase();

  switch (normalizedRole) {
    case 'MANAGER':
      return structuredClone(managerPolicy);
    case 'EMPLOYEE':
      return structuredClone(employeePolicy);
    default:
      throw new Error(`No policy defined for role: "${role}"`);
  }
}

module.exports = {
  getPolicyForRole
};
