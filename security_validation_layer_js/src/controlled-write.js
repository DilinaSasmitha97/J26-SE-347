/**
 * Controlled Write Protocol — Month 3 of the Security & Validation Layer.
 *
 * An authorized write never reaches the database in one step. It goes:
 *
 *   preview   BEGIN -> capture before-image -> run the write -> capture
 *             after-image + affected rows -> ROLLBACK        (status: previewed)
 *   approve   one or more *other* users sign off           (status: approved)
 *   commit    re-validate, re-run inside a transaction, COMMIT only if the
 *             affected-row count still matches the preview (status: committed)
 *
 *   pending -> previewed -> approved -> committed
 *                  |            |
 *                  +-> rejected / expired / failed
 *
 * Why each guard exists:
 *  - SQL hash: the commit caller must present the exact SQL that was previewed,
 *    so an approved request cannot be swapped for a different statement.
 *  - Row-count re-check: if the data changed between preview and commit, what
 *    the approver saw is no longer what would happen, so the commit is refused.
 *  - TTL: an approval is only valid for a short window.
 *  - Separation of duties: the requester can never approve their own write.
 *  - InnoDB only: ROLLBACK is a no-op on MyISAM/MEMORY tables, so a "preview"
 *    there would really write.
 *  - Single-table, VALUES-only writes: keeps the before/after image exact and
 *    stops INSERT ... SELECT from reading data the requester should not see.
 *  - No-op refusal: a write that would change 0 rows is rejected at preview;
 *    approving "nothing" only hides a WHERE clause that is wrong.
 *
 * Requests are held in memory. That is enough for the demo; a real deployment
 * would persist them (and their audit history) in a table.
 */

'use strict';

const crypto = require('crypto');
const { Parser } = require('node-sql-parser');
const { validate, parse, getStatementType } = require('./security-middleware');

const DIALECT = 'MySQL';
const _parser = new Parser();

const STATUS = Object.freeze({
  PENDING: 'pending',
  PREVIEWED: 'previewed',
  APPROVED: 'approved',
  COMMITTED: 'committed',
  REJECTED: 'rejected',
  EXPIRED: 'expired',
  FAILED: 'failed',
});

const TERMINAL = new Set([STATUS.COMMITTED, STATUS.REJECTED, STATUS.EXPIRED, STATUS.FAILED]);
const TRANSACTIONAL_ENGINES = new Set(['INNODB']);

/** A refused protocol step. `code` is stable for callers; `status` is the HTTP status to use. */
class WriteProtocolError extends Error {
  constructor(code, message, status = 400) {
    super(message);
    this.name = 'WriteProtocolError';
    this.code = code;
    this.status = status;
  }
}

function sha256(text) {
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

function quoteIdent(name) {
  return '`' + String(name).replace(/`/g, '``') + '`';
}

/**
 * Pull the single target table out of a write AST and refuse the shapes the
 * protocol cannot preview exactly (multi-table UPDATE/DELETE, INSERT ... SELECT).
 */
function describeWrite(ast) {
  const type = getStatementType(ast);

  if (type === 'UPDATE' || type === 'DELETE') {
    const tables = type === 'UPDATE' ? ast.table : ast.from;
    if (!Array.isArray(tables) || tables.length !== 1 || tables[0].join) {
      throw new WriteProtocolError('multi_table_write', `${type} must target exactly one table (no JOINs)`);
    }
    return { type, db: tables[0].db || null, table: tables[0].table };
  }

  if (type === 'INSERT') {
    const target = Array.isArray(ast.table) ? ast.table[0] : null;
    if (!target || !target.table) throw new WriteProtocolError('unsupported_write', 'INSERT has no target table');
    if (!ast.values || ast.values.type !== 'values') {
      throw new WriteProtocolError('insert_select', 'Only INSERT ... VALUES is allowed; INSERT ... SELECT can read unauthorized data');
    }
    return { type, db: target.db || null, table: target.table };
  }

  throw new WriteProtocolError('not_a_write', `Controlled Write Protocol only handles INSERT/UPDATE/DELETE, got ${type}`);
}

/** Build `SELECT * FROM <table> WHERE <same predicate> [ORDER BY/LIMIT] FOR UPDATE` from a write AST. */
function beforeImageSql(ast, target) {
  const selectAst = {
    type: 'select',
    columns: [{ expr: { type: 'column_ref', table: null, column: '*' }, as: null }],
    from: [{ db: target.db, table: target.table, as: null }],
    where: ast.where || null,
    orderby: ast.orderby || null,
    limit: ast.limit || null,
  };
  return _parser.sqlify(selectAst, { database: DIALECT }) + ' FOR UPDATE';
}

function tableRef(target) {
  return (target.db ? quoteIdent(target.db) + '.' : '') + quoteIdent(target.table);
}

async function tableEngine(conn, target) {
  const [rows] = await conn.query(
    'SELECT ENGINE AS engine FROM information_schema.TABLES WHERE TABLE_SCHEMA = COALESCE(?, DATABASE()) AND TABLE_NAME = ?',
    [target.db, target.table],
  );
  if (!rows.length) throw new WriteProtocolError('unknown_table', `Table ${target.table} does not exist`, 404);
  return String(rows[0].engine || '').toUpperCase();
}

async function primaryKey(conn, target) {
  const [rows] = await conn.query(
    `SELECT COLUMN_NAME AS col FROM information_schema.KEY_COLUMN_USAGE
      WHERE TABLE_SCHEMA = COALESCE(?, DATABASE()) AND TABLE_NAME = ? AND CONSTRAINT_NAME = 'PRIMARY'
      ORDER BY ORDINAL_POSITION`,
    [target.db, target.table],
  );
  return rows.map((r) => r.col);
}

/** Select rows by primary key; `keys` is a list of PK value tuples. */
async function rowsByKey(conn, target, pk, keys) {
  if (!pk.length || !keys.length) return [];
  const cols = pk.length === 1 ? quoteIdent(pk[0]) : `(${pk.map(quoteIdent).join(', ')})`;
  const values = pk.length === 1 ? keys.map((k) => k[0]) : keys;
  const [rows] = await conn.query(`SELECT * FROM ${tableRef(target)} WHERE ${cols} IN (?)`, [values]);
  return rows;
}

/**
 * Create a protocol instance bound to a mysql2/promise pool.
 *
 * options:
 *   maxAffectedRows    refuse any write that would touch more rows (default 100)
 *   approvalTtlMs      how long a preview/approval stays valid (default 15 min)
 *   requiredApprovals  distinct approvers needed before commit (default 1)
 *   lockWaitTimeoutSec how long preview/commit wait on row locks (default 5)
 *   allowlist          schema allowlist ({ table: '*' | [columns] }) every write must satisfy
 *   now                clock, injectable for tests
 */
function createWriteProtocol(pool, options = {}) {
  const {
    maxAffectedRows = 100,
    approvalTtlMs = 15 * 60 * 1000,
    requiredApprovals = 1,
    lockWaitTimeoutSec = 5,
    allowlist = null,
    now = () => Date.now(),
  } = options;

  const requests = new Map();

  function record(req, event, by, detail) {
    req.history.push({ at: new Date(now()).toISOString(), event, by: by || null, detail: detail || null });
  }

  function load(id) {
    const req = requests.get(id);
    if (!req) throw new WriteProtocolError('not_found', `No write request ${id}`, 404);
    if (!TERMINAL.has(req.status) && now() > req.expiresAt) {
      req.status = STATUS.EXPIRED;
      record(req, 'expired');
    }
    return req;
  }

  function view(req) {
    return {
      id: req.id,
      status: req.status,
      statementType: req.statementType,
      table: req.table,
      sql: req.sql,
      sqlHash: req.sqlHash,
      requestedBy: req.requestedBy,
      approvals: req.approvals.slice(),
      requiredApprovals,
      expiresAt: new Date(req.expiresAt).toISOString(),
      preview: req.preview,
      reason: req.reason,
      history: req.history.slice(),
    };
  }

  /** Validation shared by preview and commit — same rules, run fresh each time. */
  function checkSql(sql) {
    const result = validate(sql, true, { allowlist });
    if (!result.safe) {
      const err = new WriteProtocolError('validation_failed', 'Write failed security validation', 403);
      err.violations = result.violations.map((v) => ({ type: v.type, detail: v.detail }));
      throw err;
    }
    const { ast } = parse(sql);
    return { ast, target: describeWrite(ast) };
  }

  async function withTransaction(fn) {
    const conn = await pool.getConnection();
    try {
      await conn.query('SET SESSION innodb_lock_wait_timeout = ?', [lockWaitTimeoutSec]);
      await conn.query('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
      await conn.beginTransaction();
      try {
        return await fn(conn);
      } catch (e) {
        // Never hand a connection back to the pool with a transaction still open.
        await conn.rollback().catch(() => {});
        throw e;
      }
    } finally {
      conn.release();
    }
  }

  /** Run the write inside an open transaction and return what it did. Caller commits or rolls back. */
  async function runWrite(conn, sql, ast, target) {
    const engine = await tableEngine(conn, target);
    if (!TRANSACTIONAL_ENGINES.has(engine)) {
      throw new WriteProtocolError('non_transactional_table', `Table ${target.table} uses ${engine}; ROLLBACK cannot undo writes there`);
    }
    const pk = await primaryKey(conn, target);

    let before = [];
    if (target.type !== 'INSERT') {
      [before] = await conn.query(beforeImageSql(ast, target));
    }

    const [res] = await conn.query(sql);
    const affectedRows = res.affectedRows;

    let after = [];
    if (target.type === 'UPDATE') {
      after = await rowsByKey(conn, target, pk, before.map((r) => pk.map((c) => r[c])));
    } else if (target.type === 'INSERT' && pk.length === 1 && res.insertId) {
      // Simple multi-row INSERTs get consecutive auto-increment ids.
      const ids = Array.from({ length: affectedRows }, (_, i) => res.insertId + i);
      after = await rowsByKey(conn, target, pk, ids.map((v) => [v]));
    }

    return { affectedRows, before, after, primaryKey: pk };
  }

  /** Step 1: validate, execute inside a transaction, capture the change, always roll back. */
  async function preview(sql, { requestedBy } = {}) {
    if (!requestedBy) throw new WriteProtocolError('missing_identity', 'requestedBy is required');
    const { ast, target } = checkSql(sql);

    const req = {
      id: crypto.randomUUID(),
      status: STATUS.PENDING,
      statementType: target.type,
      table: target.table,
      sql,
      sqlHash: sha256(sql),
      requestedBy,
      approvals: [],
      createdAt: now(),
      expiresAt: now() + approvalTtlMs,
      preview: null,
      reason: null,
      history: [],
    };
    requests.set(req.id, req);
    record(req, 'requested', requestedBy);

    try {
      req.preview = await withTransaction(async (conn) => {
        try {
          return await runWrite(conn, sql, ast, target);
        } finally {
          await conn.rollback();
        }
      });
    } catch (e) {
      req.status = STATUS.FAILED;
      req.reason = e.message;
      record(req, 'preview_failed', null, e.message);
      if (e instanceof WriteProtocolError) throw Object.assign(e, { request: view(req) });
      throw new WriteProtocolError('preview_failed', `Preview failed: ${e.message}`, 422);
    }
    record(req, 'previewed_and_rolled_back', null, `${req.preview.affectedRows} row(s) would change`);

    if (req.preview.affectedRows === 0) {
      req.status = STATUS.REJECTED;
      req.reason = 'Write would not change any rows — check the WHERE clause';
      record(req, 'auto_rejected', null, req.reason);
    } else if (req.preview.affectedRows > maxAffectedRows) {
      req.status = STATUS.REJECTED;
      req.reason = `Would affect ${req.preview.affectedRows} rows (limit ${maxAffectedRows})`;
      record(req, 'auto_rejected', null, req.reason);
    } else {
      req.status = STATUS.PREVIEWED;
    }
    return view(req);
  }

  /** Step 2: a different user signs off. Enough distinct approvals move it to `approved`. */
  function approve(id, { approvedBy } = {}) {
    const req = load(id);
    if (!approvedBy) throw new WriteProtocolError('missing_identity', 'approvedBy is required');
    if (req.status !== STATUS.PREVIEWED) {
      throw new WriteProtocolError('invalid_state', `Cannot approve a request that is ${req.status}`, 409);
    }
    if (approvedBy === req.requestedBy) {
      throw new WriteProtocolError('self_approval', 'The requester cannot approve their own write', 403);
    }
    if (req.approvals.some((a) => a.by === approvedBy)) {
      throw new WriteProtocolError('duplicate_approval', `${approvedBy} has already approved this write`, 409);
    }
    req.approvals.push({ by: approvedBy, at: new Date(now()).toISOString() });
    record(req, 'approved', approvedBy);
    if (req.approvals.length >= requiredApprovals) req.status = STATUS.APPROVED;
    return view(req);
  }

  function reject(id, { rejectedBy, reason } = {}) {
    const req = load(id);
    if (TERMINAL.has(req.status)) {
      throw new WriteProtocolError('invalid_state', `Cannot reject a request that is ${req.status}`, 409);
    }
    req.status = STATUS.REJECTED;
    req.reason = reason || 'Rejected by reviewer';
    record(req, 'rejected', rejectedBy, req.reason);
    return view(req);
  }

  /**
   * Step 3: the caller presents the SQL again; it must hash to what was previewed.
   * The write is re-validated and re-run, and only committed if it still
   * touches exactly as many rows as the approver saw.
   */
  async function commit(id, { sql, committedBy } = {}) {
    const req = load(id);
    if (req.status !== STATUS.APPROVED) {
      throw new WriteProtocolError('invalid_state', `Cannot commit a request that is ${req.status}`, 409);
    }
    if (typeof sql !== 'string' || sha256(sql) !== req.sqlHash) {
      record(req, 'commit_refused', committedBy, 'SQL does not match the previewed statement');
      throw new WriteProtocolError('sql_mismatch', 'SQL does not match the statement that was previewed and approved', 409);
    }
    const { ast, target } = checkSql(sql);

    let outcome;
    try {
      outcome = await withTransaction(async (conn) => {
        const result = await runWrite(conn, sql, ast, target);
        if (result.affectedRows !== req.preview.affectedRows) {
          await conn.rollback();
          return { drifted: true, result };
        }
        await conn.commit();
        return { drifted: false, result };
      });
    } catch (e) {
      req.status = STATUS.FAILED;
      req.reason = e.message;
      record(req, 'commit_failed', committedBy, e.message);
      throw new WriteProtocolError('commit_failed', `Commit failed and was rolled back: ${e.message}`, 422);
    }

    if (outcome.drifted) {
      req.status = STATUS.FAILED;
      req.reason = `Data changed since preview: ${outcome.result.affectedRows} row(s) now affected, ${req.preview.affectedRows} approved`;
      record(req, 'commit_refused', committedBy, req.reason);
      throw Object.assign(new WriteProtocolError('preview_drift', req.reason, 409), { request: view(req) });
    }

    req.status = STATUS.COMMITTED;
    record(req, 'committed', committedBy, `${outcome.result.affectedRows} row(s) changed`);
    return view(req);
  }

  function get(id) {
    return view(load(id));
  }

  return { preview, approve, reject, commit, get };
}

module.exports = {
  createWriteProtocol,
  WriteProtocolError,
  STATUS,
  // exported for inspection/tests
  describeWrite,
  beforeImageSql,
};
