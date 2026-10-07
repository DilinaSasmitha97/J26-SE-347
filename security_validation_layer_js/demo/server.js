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
const { validate, securityMiddleware, mask } = require('../src/security-middleware');
const { detectInText } = require('../src/pii-detectors');
const { classifyColumns } = require('../src/pii-classifier');
const { createNerClient, applyNer } = require('../src/pii-ner');
const { loadPolicy } = require('../src/masking-policy');
const { createPiiFpe } = require('../src/pii-fpe');
const { verifyFF1 } = require('../src/fpe-ff1');

// Dynamic masking: per-role actions from config/masking_policy.json.
const MASKING_POLICY = loadPolicy(path.join(__dirname, '..', 'config', 'masking_policy.json'));
// Format-preserving encryption. The FF1 self-test runs against the NIST
// vectors at startup; without a key, 'fpe' actions fall back to redaction.
verifyFF1();
const FPE = /^[0-9a-f]{64}$/i.test(process.env.FPE_KEY || '')
  ? createPiiFpe(process.env.FPE_KEY, { context: process.env.DB_NAME || 'svl_demo' })
  : null;

// NER side service (pii_service/ner_service.py). If it is down, the pipeline
// fails closed unless NER_FAIL_MODE=open.
const ner = createNerClient({ url: process.env.NER_URL || 'http://127.0.0.1:5002' });
const NER_FAIL_MODE = process.env.NER_FAIL_MODE === 'open' ? 'open' : 'closed';

const app = express();
const PORT = process.env.PORT || 3000;

// Schema allowlist for the configured database (config/schema_allowlist.json).
const ALLOWLISTS = require('../config/schema_allowlist.json');
const ALLOWLIST = ALLOWLISTS[process.env.DB_NAME || 'svl_demo'] || null;
// Declared PII columns for the configured database (config/pii_columns.json).
const PII_SCHEMA = require('../config/pii_columns.json')[process.env.DB_NAME || 'svl_demo'] || {};

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

/** PII detection on arbitrary text: regex detectors plus NER for names. No database involved. */
app.post('/api/pii/detect', async (req, res) => {
  const text = String((req.body && req.body.text) || '');
  const spans = detectInText(text).map((s) => ({ ...s, source: 'regex' }));
  const warnings = [];
  try {
    const [names] = await ner.analyze([text]);
    for (const n of names) {
      if (spans.some((s) => n.start < s.end && n.end > s.start)) continue; // regex already covers it
      spans.push({ type: n.type, value: text.slice(n.start, n.end), start: n.start, end: n.end, source: 'ner', score: n.score });
    }
  } catch (e) {
    warnings.push(`NER service unavailable (${e.message}) — names were not checked`);
  }
  res.json({ spans: spans.sort((a, b) => a.start - b.start), warnings });
});

/**
 * Database-backed endpoints: read-query execution and the Controlled Write
 * Protocol. Only enabled when a database is configured (see .env.example).
 * Identities come from the request body here; in the integrated system they
 * come from Member 3's validated JWT.
 */
let writes = null;
let queries = null;
if (process.env.DB_NAME) {
  const mysql = require('mysql2/promise');
  const { createWriteProtocol } = require('../src/controlled-write');
  const { createQueryExecutor } = require('../src/query-executor');
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
  queries = createQueryExecutor(pool, {
    allowlist: ALLOWLIST,
    maxRows: Number(process.env.QUERY_MAX_ROWS || 1000),
    timeoutMs: Number(process.env.QUERY_TIMEOUT_MS || 5000),
  });
}

function dbRoute(handler) {
  return async (req, res) => {
    if (!writes) {
      return res.status(503).json({ error: 'database_not_configured', detail: 'Set DB_* in .env to enable query execution and the Controlled Write Protocol.' });
    }
    try {
      res.json(await handler(req.body || {}, req.params));
    } catch (e) {
      if (e.name !== 'WriteProtocolError' && e.name !== 'QueryError') {
        console.error(e);
        return res.status(500).json({ error: 'internal_error', detail: e.message });
      }
      res.status(e.status).json({ error: e.code, detail: e.message, violations: e.violations, request: e.request });
    }
  };
}

// The full read pipeline: validate -> execute read-only -> classify -> NER -> mask.
// Only masked rows are returned; `includeRaw` exists so the demo can show the
// before/after side by side and must not be exposed in the integrated system.
app.post('/api/query', dbRoute(async (b) => {
  const result = await queries.run(b.sql);
  const classification = classifyColumns(result, { sql: b.sql, piiSchema: PII_SCHEMA });
  const nerRun = await applyNer(result, classification, ner, { failMode: NER_FAIL_MODE });
  // In the integrated system the role comes from Member 3's validated JWT, never from the request body.
  const role = typeof b.role === 'string' && b.role ? b.role : MASKING_POLICY.defaultRole;
  const masked = mask(result, classification, { role, policy: MASKING_POLICY, fpe: FPE });
  masked.classification = classification;
  masked.ner = nerRun;
  if (b.includeRaw) masked.rawRows = result.rows;
  return masked;
}));

app.post('/api/writes/preview', dbRoute((b) => writes.preview(b.sql, { requestedBy: b.requestedBy })));
app.get('/api/writes/:id', dbRoute((b, p) => writes.get(p.id)));
app.post('/api/writes/:id/approve', dbRoute((b, p) => writes.approve(p.id, { approvedBy: b.approvedBy })));
app.post('/api/writes/:id/reject', dbRoute((b, p) => writes.reject(p.id, { rejectedBy: b.rejectedBy, reason: b.reason })));
app.post('/api/writes/:id/commit', dbRoute((b, p) => writes.commit(p.id, { sql: b.sql, committedBy: b.committedBy })));

app.listen(PORT, async () => {
  console.log(`Query validation test UI running at http://localhost:${PORT}`);
  console.log(FPE ? 'Format-preserving encryption ready (FF1, NIST vectors verified)'
    : 'FPE_KEY not set - fpe actions fall back to redaction (see .env.example)');
  const h = await ner.health();
  console.log(h.status === 'ok'
    ? `NER service connected (${h.model}) at ${ner.url}`
    : `NER service NOT reachable at ${ner.url} - text columns will be ${NER_FAIL_MODE === 'closed' ? 'fully masked (fail closed)' : 'left unchecked (fail open)'}`);
  console.log(writes
    ? `Query execution + Controlled Write Protocol enabled (database: ${process.env.DB_NAME})`
    : 'Database features disabled - no DB_NAME set (see .env.example)');
});
