/**
 * Test harness for the AI Query Security & Validation Layer.
 *
 * Serves a single page that posts SQL at validate() and renders the verdict,
 * so rules can be exercised by hand without writing a script per query.
 *
 *   npm start   ->   http://localhost:3000
 *
 * This is a demo surface, not part of the validation layer itself — nothing
 * here is imported by src/security-middleware.js, and no SQL is ever executed
 * against a database.
 */

'use strict';

const path = require('path');
const express = require('express');
const { validate, securityMiddleware } = require('../src/security-middleware');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(__dirname));

/**
 * The page calls validate() directly rather than going through
 * securityMiddleware(), because a test harness needs to render the full
 * result for *safe* queries too — the middleware's job is to make blocked
 * requests never reach a handler at all.
 */
app.post('/api/validate', (req, res) => {
  const { sql, allowWrites } = req.body || {};
  const result = validate(sql, Boolean(allowWrites));
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

app.listen(PORT, () => {
  console.log(`Query validation test UI running at http://localhost:${PORT}`);
});
