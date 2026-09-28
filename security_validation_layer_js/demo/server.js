/**
 * Test harness for the AI Query Security & Validation Layer.
 *
 * Serves a single page that posts SQL at validate() and renders the verdict,
 * so rules can be exercised by hand without writing a script per query.
 *
 *   npm start   ->   http://localhost:3000
 *
 * This is a demo surface, not part of the validation layer itself — nothing
 * here is imported by src/. /api/validate never touches a database; only the
 * /api/writes/* endpoints do, and only when DB_* is set in .env.
 */

'use strict';

const path = require('path');
const express = require('express');
const { validate, securityMiddleware } = require('../src/security-middleware');

const app = express();
const PORT = process.env.PORT || 3000;

// Schema allowlist for the configured database (config/schema_allowlist.json).
const ALLOWLISTS = require('../config/schema_allowlist.json');
const ALLOWLIST = ALLOWLISTS[process.env.DB_NAME || 'svl_demo'] || null;

app.use(express.json());
app.use(express.static(__dirname));

/**
 * The page calls validate() directly rather than going through
 * securityMiddleware(), because a test harness needs to render the full
 * result for *safe* queries too — the middleware's job is to make blocked
 * requests never reach a handler at all.
 */
app.post('/api/validate', (req, res) => {
  const { sql, allowWrites, enforceAllowlist } = req.body || {};
  const result = validate(sql, Boolean(allowWrites), { allowlist: enforceAllowlist ? ALLOWLIST : null });
  res.json({
    safe: result.safe,
    statementType: result.statementType,
    violations: result.violations.map((v) => ({ type: v.type, detail: v.detail })),
  });
});

/**
 * The same query run through the real Express middleware, so the demo can
 * show what an integrating service (Member 1's NL-to-SQL engine) actually
 * receives: a 403 with the violation list, or a handler response.
 */
app.post('/api/guarded-query', securityMiddleware({ allowWrites: (req) => Boolean(req.body.allowWrites) }), (req, res) => {
  res.json({ ok: true, statementType: req.validation.statementType, note: 'Query passed validation and would now be sent for execution.' });
});

/**
 * Controlled Write Protocol endpoints. Only mounted when a database is
 * configured (see .env.example) — the protocol needs a real transaction to
 * preview and roll back. Identities come from the request body here; in the
 * integrated system they come from Member 3's validated JWT.
 */
let writes = null;
if (process.env.DB_NAME) {
  const mysql = require('mysql2/promise');
  const { createWriteProtocol } = require('../src/controlled-write');
  const pool = mysql.createPool({
    host: process.env.DB_HOST || 'localhost',
    port: Number(process.env.DB_PORT || 3306),
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME,
    connectionLimit: 5,
    dateStrings: true,
  });
  writes = createWriteProtocol(pool, {
    maxAffectedRows: Number(process.env.WRITE_MAX_AFFECTED_ROWS || 100),
    approvalTtlMs: Number(process.env.WRITE_APPROVAL_TTL_MINUTES || 15) * 60 * 1000,
    requiredApprovals: Number(process.env.WRITE_REQUIRED_APPROVALS || 1),
    allowlist: ALLOWLIST,
  });
}

function writeRoute(handler) {
  return async (req, res) => {
    if (!writes) {
      return res.status(503).json({ error: 'database_not_configured', detail: 'Set DB_* in .env to enable the Controlled Write Protocol.' });
    }
    try {
      res.json(await handler(req.body || {}, req.params));
    } catch (e) {
      if (e.name !== 'WriteProtocolError') {
        console.error(e);
        return res.status(500).json({ error: 'internal_error', detail: e.message });
      }
      res.status(e.status).json({ error: e.code, detail: e.message, violations: e.violations, request: e.request });
    }
  };
}

app.post('/api/writes/preview', writeRoute((b) => writes.preview(b.sql, { requestedBy: b.requestedBy })));
app.get('/api/writes/:id', writeRoute((b, p) => writes.get(p.id)));
app.post('/api/writes/:id/approve', writeRoute((b, p) => writes.approve(p.id, { approvedBy: b.approvedBy })));
app.post('/api/writes/:id/reject', writeRoute((b, p) => writes.reject(p.id, { rejectedBy: b.rejectedBy, reason: b.reason })));
app.post('/api/writes/:id/commit', writeRoute((b, p) => writes.commit(p.id, { sql: b.sql, committedBy: b.committedBy })));

app.listen(PORT, () => {
  console.log(`Query validation test UI running at http://localhost:${PORT}`);
  console.log(writes
    ? `Controlled Write Protocol enabled (database: ${process.env.DB_NAME})`
    : 'Controlled Write Protocol disabled - no DB_NAME set (see .env.example)');
});
