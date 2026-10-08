const { randomUUID, createHash } = require('node:crypto');

function policyFingerprint(user, policy) {
  return createHash('sha256').update(JSON.stringify({ user, policy })).digest('hex');
}

// Each app instance owns its store. Only already-masked rows enter it.
function createResultStore({ ttlMs = 10 * 60 * 1000, maxEntries = 100, now = Date.now } = {}) {
  const entries = new Map();
  function prune() {
    for (const [id, entry] of entries) if (entry.expiresAt <= now()) entries.delete(id);
  }
  return {
    save({ user, policy, question, result }) {
      prune();
      while (entries.size >= maxEntries) entries.delete(entries.keys().next().value);
      const id = randomUUID();
      entries.set(id, {
        userId: user.userId, tenantId: user.tenantId,
        fingerprint: policyFingerprint(user, policy), question,
        result: structuredClone(result), expiresAt: now() + ttlMs
      });
      return id;
    },
    get(id, user, policy) {
      prune();
      const entry = entries.get(id);
      if (!entry || entry.userId !== user.userId || entry.tenantId !== user.tenantId
          || entry.fingerprint !== policyFingerprint(user, policy)) return null;
      return structuredClone(entry);
    }
  };
}

module.exports = { createResultStore };
