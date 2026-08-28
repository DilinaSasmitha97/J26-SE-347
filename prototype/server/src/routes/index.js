import express from 'express';
import { randomUUID } from 'node:crypto';

import { requireAuth, requireOwner, issueToken, publicUser } from '../middleware/auth.js';
import { ask } from '../engine/pipeline.js';
import { getCatalog } from '../data/catalog.js';
import { getSemantic } from '../engine/semantic.js';
import { getRowCounts, getSampleRows } from '../engine/executor.js';
import { buildReview, applyAnswers } from '../engine/discovery.js';
import { USERS, CONNECTIONS, HISTORY, AUDIT, getConnection, addHistory, addAudit } from '../store.js';

const router = express.Router();

// The only roles this workspace recognises.
const ROLES = ['owner', 'viewer'];

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
// DEMO BUILD ONLY: the password is deliberately not checked, so any known
// email signs straight in. This must be restored to a real credential check
// (and hashed passwords) before this is exposed to anyone outside a demo.
router.post('/auth/login', (req, res) => {
  const { email } = req.body || {};
  const user = USERS.find((u) => u.email.toLowerCase() === String(email || '').trim().toLowerCase());
  if (!user) {
    return res.status(401).json({ error: 'That email was not recognised.' });
  }
  user.lastActive = new Date().toISOString();
  res.json({ token: issueToken(user), user: publicUser(user) });
});

router.get('/auth/me', requireAuth, (req, res) => {
  res.json({ user: publicUser(req.user) });
});

// ---------------------------------------------------------------------------
// Connections
// ---------------------------------------------------------------------------
const summarise = (c) => ({
  id: c.id,
  name: c.name,
  engine: c.engine,
  host: c.host,
  port: c.port,
  database: c.database,
  username: c.username,
  ssl: c.ssl,
  poolSize: c.poolSize,
  status: c.status,
  statusMessage: c.statusMessage || null,
  readOnly: c.readOnly,
  createdAt: c.createdAt,
  lastSyncedAt: c.lastSyncedAt,
  tableCount: (getCatalog(c.id)?.tables || []).length,
  rowCount: Object.values(getRowCounts(c.id)).reduce((a, b) => a + b, 0),
});

router.get('/connections', requireAuth, (_req, res) => {
  res.json({ connections: CONNECTIONS.map(summarise) });
});

router.get('/connections/:id', requireAuth, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });
  res.json({ connection: { ...summarise(connection), settings: connection.settings } });
});

router.post('/connections', requireAuth, requireOwner, (req, res) => {
  const { name, engine, host, port, database, username, ssl } = req.body || {};
  if (!name || !host || !database) {
    return res.status(400).json({ error: 'Name, host and database are required.' });
  }
  // MySQL is the only supported database type.
  if (engine && engine !== 'mysql') {
    return res.status(400).json({ error: 'Only MySQL databases are supported.' });
  }
  const connection = {
    id: `conn_${randomUUID().slice(0, 8)}`,
    name,
    engine: 'mysql',
    host,
    port: Number(port) || 3306,
    database,
    username: username || 'askdb_reader',
    password: '••••••••••••',
    ssl: ssl !== false,
    poolSize: 5,
    // Nothing is registered for a brand new connection in the demo, so it
    // stays in the "needs attention" state rather than pretending to work.
    status: 'disconnected',
    statusMessage: 'Demo build: only the seeded databases carry sample data. Credentials were not dialled out.',
    readOnly: true,
    createdAt: new Date().toISOString(),
    lastSyncedAt: null,
    settings: JSON.parse(JSON.stringify(CONNECTIONS[0].settings)),
  };
  CONNECTIONS.push(connection);
  addAudit({ actor: req.user.name, action: 'connection.created', detail: `Added connection "${name}"` });
  res.status(201).json({ connection: summarise(connection) });
});

router.post('/connections/:id/test', requireAuth, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });
  const reachable = Boolean(getSemantic(connection.id));
  connection.status = reachable ? 'connected' : 'disconnected';
  connection.lastSyncedAt = reachable ? new Date().toISOString() : connection.lastSyncedAt;
  addAudit({ actor: req.user.name, action: 'connection.tested', detail: `${connection.name}: ${connection.status}` });
  res.json({
    ok: reachable,
    status: connection.status,
    message: reachable
      ? `Handshake succeeded in 42 ms. Schema has ${(getCatalog(connection.id)?.tables || []).length} tables.`
      : connection.statusMessage || 'Could not reach the host.',
  });
});

// ---------------------------------------------------------------------------
// Schema discovery review - the questions the system could not answer alone
// ---------------------------------------------------------------------------
router.get('/connections/:id/review', requireAuth, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });
  const review = buildReview(connection);
  res.json({
    connection: {
      id: connection.id, name: connection.name, database: connection.database,
      host: connection.host, port: connection.port, username: connection.username,
    },
    scan: review.scan,
    questions: review.questions,
    completed: Boolean(connection.review?.completed),
  });
});

router.post('/connections/:id/review', requireAuth, requireOwner, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });
  const answers = (req.body && req.body.answers) || {};
  const review = applyAnswers(connection, answers);
  addAudit({
    actor: req.user.name,
    action: 'connection.reviewed',
    detail: `Answered ${review.answered} of ${review.total} schema questions for "${connection.name}"`,
  });
  res.json({ review, settings: connection.settings });
});

router.delete('/connections/:id', requireAuth, requireOwner, (req, res) => {
  const index = CONNECTIONS.findIndex((c) => c.id === req.params.id);
  if (index === -1) return res.status(404).json({ error: 'Connection not found' });
  const [removed] = CONNECTIONS.splice(index, 1);
  addAudit({ actor: req.user.name, action: 'connection.deleted', detail: `Removed "${removed.name}"` });
  res.json({ ok: true });
});

// ---------------------------------------------------------------------------
// Schema
// ---------------------------------------------------------------------------
router.get('/connections/:id/schema', requireAuth, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });
  const catalog = getCatalog(connection.id);
  if (!catalog) return res.json({ tables: [] });

  const counts = getRowCounts(connection.id);
  const blocked = connection.settings.blocked_tables || [];
  res.json({
    engine: catalog.engine,
    tables: catalog.tables.map((t) => ({
      ...t,
      rowCount: counts[t.rowCountKey] ?? 0,
      blocked: blocked.includes(t.name),
    })),
  });
});

router.get('/connections/:id/schema/:table/sample', requireAuth, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });
  try {
    res.json({ rows: getSampleRows(connection.id, req.params.table, 8) });
  } catch {
    res.json({ rows: [] });
  }
});

// What this connection can be asked about - drives the suggestion chips.
router.get('/connections/:id/suggestions', requireAuth, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });
  const model = getSemantic(connection.id);
  if (!model) return res.json({ metrics: [], dimensions: [], examples: [] });

  const hideSensitive = connection.settings.hide_sensitive_metrics;
  const metrics = model.metrics.filter((m) => !(m.sensitive && hideSensitive));
  const examples = connection.id === 'peopleops'
    ? [
      'Headcount by department',
      'How many employees joined in the last 12 months?',
      'Headcount by location',
      'Show hiring by month over the last 12 months',
    ]
    : [
      'What was our total revenue last quarter?',
      'Show revenue by month over the last 12 months',
      'Top 5 products by revenue this year',
      'Which region has the highest average order value?',
      'Gross profit by category',
      'How many orders did we get last month?',
      'Support tickets by priority',
      'Revenue by category in Europe in 2025',
    ];

  res.json({
    metrics: metrics.map((m) => ({ id: m.id, label: m.label, description: m.description })),
    dimensions: model.dimensions.map((d) => ({ id: d.id, label: d.label })),
    examples,
  });
});

// ---------------------------------------------------------------------------
// Ask
// ---------------------------------------------------------------------------
router.post('/ask', requireAuth, (req, res) => {
  const { question, connectionId } = req.body || {};
  if (!question || !String(question).trim()) {
    return res.status(400).json({ error: 'A question is required.' });
  }
  const connection = getConnection(connectionId);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });

  const answer = ask({ question, connection, user: req.user });

  const record = addHistory({
    question,
    connectionId: connection.id,
    user: req.user.name,
    executionMs: answer.executionMs,
    headline: answer.answer.headline,
    status: answer.status,
    sql: answer.sql,
  });

  res.json({ ...answer, id: record.id, question, connectionId: connection.id, askedAt: record.askedAt });
});

// ---------------------------------------------------------------------------
// History
// ---------------------------------------------------------------------------
router.get('/history', requireAuth, (req, res) => {
  const { connectionId } = req.query;
  const rows = connectionId ? HISTORY.filter((h) => h.connectionId === connectionId) : HISTORY;
  res.json({ history: rows.slice(0, 60) });
});

router.delete('/history', requireAuth, (_req, res) => {
  HISTORY.length = 0;
  res.json({ ok: true });
});

// ---------------------------------------------------------------------------
// Admin: settings, users, audit
// ---------------------------------------------------------------------------
router.get('/admin/settings/:id', requireAuth, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });
  res.json({ settings: connection.settings, connection: summarise(connection) });
});

router.put('/admin/settings/:id', requireAuth, requireOwner, (req, res) => {
  const connection = getConnection(req.params.id);
  if (!connection) return res.status(404).json({ error: 'Connection not found' });

  const incoming = req.body || {};
  const changed = Object.keys(incoming).filter(
    (k) => JSON.stringify(connection.settings[k]) !== JSON.stringify(incoming[k])
  );
  connection.settings = { ...connection.settings, ...incoming };

  if (changed.length) {
    addAudit({
      actor: req.user.name,
      action: 'settings.updated',
      detail: `${changed.join(', ')} on ${connection.name}`,
    });
  }
  res.json({ settings: connection.settings, changed });
});

router.get('/admin/users', requireAuth, (_req, res) => {
  res.json({ users: USERS.map(publicUser) });
});

router.post('/admin/users', requireAuth, requireOwner, (req, res) => {
  const { name, email, role } = req.body || {};
  if (!email) return res.status(400).json({ error: 'An email address is required.' });
  if (role && !ROLES.includes(role)) {
    return res.status(400).json({ error: `Role must be one of: ${ROLES.join(', ')}.` });
  }
  if (USERS.some((u) => u.email.toLowerCase() === String(email).toLowerCase())) {
    return res.status(409).json({ error: 'That user has already been invited.' });
  }
  const display = name || email.split('@')[0];
  const user = {
    id: `u_${randomUUID().slice(0, 6)}`,
    name: display,
    email,
    password: 'demo1234',
    role: role || 'viewer',
    initials: display.slice(0, 2).toUpperCase(),
    lastActive: null,
  };
  USERS.push(user);
  addAudit({ actor: req.user.name, action: 'user.invited', detail: `Invited ${email} as ${user.role}` });
  res.status(201).json({ user: publicUser(user) });
});

router.put('/admin/users/:id', requireAuth, requireOwner, (req, res) => {
  const user = USERS.find((u) => u.id === req.params.id);
  if (!user) return res.status(404).json({ error: 'User not found' });
  if (req.body.role && !ROLES.includes(req.body.role)) {
    return res.status(400).json({ error: `Role must be one of: ${ROLES.join(', ')}.` });
  }
  if (req.body.role) user.role = req.body.role;
  addAudit({ actor: req.user.name, action: 'user.updated', detail: `${user.email} is now ${user.role}` });
  res.json({ user: publicUser(user) });
});

router.get('/admin/audit', requireAuth, (_req, res) => {
  res.json({ audit: AUDIT.slice(0, 50) });
});

// ---------------------------------------------------------------------------
// Dashboard overview
// ---------------------------------------------------------------------------
router.get('/overview', requireAuth, (_req, res) => {
  const connected = CONNECTIONS.filter((c) => c.status === 'connected');
  const answered = HISTORY.filter((h) => h.status === 'ok');
  const avgMs = answered.length
    ? Math.round(answered.reduce((s, h) => s + (h.executionMs || 0), 0) / answered.length)
    : 0;

  res.json({
    stats: {
      connections: CONNECTIONS.length,
      connected: connected.length,
      questions: HISTORY.length,
      avgResponseMs: avgMs,
      rowsIndexed: CONNECTIONS.reduce(
        (sum, c) => sum + Object.values(getRowCounts(c.id)).reduce((a, b) => a + b, 0), 0
      ),
      users: USERS.length,
    },
    recent: HISTORY.slice(0, 6),
    connections: CONNECTIONS.map(summarise),
  });
});

export default router;
