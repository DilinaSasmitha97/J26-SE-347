/**
 * Resolves context placeholders (valueFrom) in a policy template using values
 * from the provided authorization context.
 *
 * Ensures the original policy object is not mutated.
 *
 * @param {object} policy - The policy template containing rowRules
 * @param {object} authorizationContext - The user's authorization context
 * @returns {object} A new policy object with resolved values
 * @throws {Error} If policy or authorizationContext are invalid, or if a required valueFrom key is missing
 */
function resolvePolicyValues(policy, authorizationContext) {
  if (!policy || typeof policy !== 'object') {
    throw new Error('A valid policy object is required.');
  }

  if (!authorizationContext || typeof authorizationContext !== 'object') {
    throw new Error('A valid authorization context object is required.');
  }

  // Deep clone to guarantee original policy is not mutated
  const effectivePolicy = structuredClone(policy);

  for (const rulesKey of ['rowRules', 'requiredFilters', 'mandatoryFilters']) {
    if (effectivePolicy[rulesKey] === undefined) continue;
    if (!Array.isArray(effectivePolicy[rulesKey])) throw new Error(`Policy ${rulesKey} must be an array.`);
    effectivePolicy[rulesKey] = effectivePolicy[rulesKey].map((rule) => {
      if (!rule || typeof rule !== 'object' || Array.isArray(rule)) throw new Error(`Policy ${rulesKey} entries must be JSON objects.`);
      if ('valueFrom' in rule) {
        const contextKey = rule.valueFrom;

        if (!(contextKey in authorizationContext) || authorizationContext[contextKey] === undefined) {
          throw new Error(
            `Authorization context is missing required key "${contextKey}" for rule on field "${rule.field || 'unknown'}".`
          );
        }

        // Replace valueFrom with the resolved value, preserving natural property order
        const resolvedRule = {};
        for (const [k, v] of Object.entries(rule)) {
          if (k === 'valueFrom') {
            resolvedRule.value = authorizationContext[contextKey];
          } else {
            resolvedRule[k] = v;
          }
        }
        return resolvedRule;
      }

      return rule;
    });
  }

  return effectivePolicy;
}

module.exports = {
  resolvePolicyValues
};
