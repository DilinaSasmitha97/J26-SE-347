/**
 * Declarative masking policy — which masking action each role gets for each
 * PII type, kept in config/masking_policy.json instead of code.
 *
 *   {
 *     "defaultRole": "viewer",
 *     "roles":   { "support": { "default": "partial", "SECRET": "redact" }, ... },
 *     "columns": { "customers.phone": { "support": "redact" } }
 *   }
 *
 * Resolution for a column of PII type T built from source columns S:
 *   1. a column override for any source in S and this role (the most
 *      restrictive one wins when several sources disagree), else
 *   2. roles[role][T], else roles[role].default, else 'redact'.
 * An unknown role is always 'redact': a missing or mistyped role in the
 * caller's token must not unlock data.
 */

'use strict';

const fs = require('fs');

// Most to least restrictive.
const ACTIONS = ['redact', 'fpe', 'partial', 'clear'];

function mostRestrictive(actions) {
  return actions.reduce((best, a) => (ACTIONS.indexOf(a) < ACTIONS.indexOf(best) ? a : best));
}

function resolveAction(policy, role, piiType, sources = []) {
  const rules = policy && policy.roles && policy.roles[role];
  if (!rules) return 'redact';
  const overrides = sources
    .map((s) => policy.columns && policy.columns[s] && policy.columns[s][role])
    .filter(Boolean);
  if (overrides.length) return mostRestrictive(overrides);
  return rules[piiType] || rules.default || 'redact';
}

/** Load and check a policy file; throws on unknown actions so a typo cannot silently weaken masking. */
function loadPolicy(file) {
  const policy = JSON.parse(fs.readFileSync(file, 'utf8'));
  const check = (where, action) => {
    if (!ACTIONS.includes(action)) throw new Error(`masking policy: unknown action "${action}" at ${where}`);
  };
  for (const [role, rules] of Object.entries(policy.roles || {})) {
    for (const [type, action] of Object.entries(rules)) check(`roles.${role}.${type}`, action);
  }
  for (const [col, byRole] of Object.entries(policy.columns || {})) {
    for (const [role, action] of Object.entries(byRole)) check(`columns.${col}.${role}`, action);
  }
  if (policy.defaultRole && !(policy.roles || {})[policy.defaultRole]) {
    throw new Error(`masking policy: defaultRole "${policy.defaultRole}" is not defined`);
  }
  return policy;
}

module.exports = { resolveAction, loadPolicy, ACTIONS };
