/**
 * Read-query execution — the step between validation and the PII pipeline.
 *
 *   validate(sql) -> run inside START TRANSACTION READ ONLY -> ROLLBACK
 *                 -> { columns, rows } handed to mask() and then Member 4
 *
 * Defense in depth: validate() only lets a SELECT through, but the query also
 * runs in a READ ONLY transaction, so MySQL itself refuses any write that got
 * past the validator. MAX_EXECUTION_TIME caps runaway SELECTs.
 *
 * Every result column carries its *source* table.column as reported by MySQL
 * (orgTable/orgName). The PII pipeline classifies on that, so renaming a
 * column (`SELECT email AS x`) cannot hide what it contains.
 */

'use strict';

const { validate } = require('./security-middleware');

/** A refused or failed query. `code` is stable for callers; `status` is the HTTP status to use. */
class QueryError extends Error {
  constructor(code, message, status = 400) {
    super(message);
    this.name = 'QueryError';
    this.code = code;
    this.status = status;
  }
}

/**
 * Create an executor bound to a mysql2/promise pool.
 *
 * options:
 *   allowlist  schema allowlist ({ table: '*' | [columns] }) every query must satisfy
 *   maxRows    rows returned to the caller; more are cut off and flagged (default 1000)
 *   timeoutMs  MySQL MAX_EXECUTION_TIME for the query (default 5000)
 */
function createQueryExecutor(pool, options = {}) {
  const { allowlist = null, maxRows = 1000, timeoutMs = 5000 } = options;

  async function run(sql, parameters = []) {
    const result = validate(sql, false, { allowlist });
    if (!result.safe) {
      const err = new QueryError('validation_failed', 'Query failed security validation', 403);
      err.statementType = result.statementType;
      err.violations = result.violations.map((v) => ({ type: v.type, detail: v.detail }));
      throw err;
    }

    const conn = await pool.getConnection();
    try {
      await conn.query('SET SESSION MAX_EXECUTION_TIME = ?', [timeoutMs]);
      await conn.query('START TRANSACTION READ ONLY');
      const started = process.hrtime.bigint();
      // rowsAsArray keeps duplicate column names (a.id, b.id) instead of collapsing them.
      const [rows, fields] = parameters.length
        ? await conn.execute({ sql, rowsAsArray: true }, parameters)
        : await conn.query({ sql, rowsAsArray: true });
      const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6;
      await conn.rollback();

      return {
        statementType: result.statementType,
        columns: fields.map((f) => ({
          name: f.name,
          sourceTable: f.orgTable || null,
          sourceColumn: f.orgName || null,
        })),
        rows: rows.slice(0, maxRows),
        rowCount: rows.length,
        truncated: rows.length > maxRows,
        elapsedMs: Math.round(elapsedMs * 10) / 10,
      };
    } catch (e) {
      await conn.rollback().catch(() => {});
      if (e instanceof QueryError) throw e;
      throw new QueryError('execution_failed', `Query failed: ${e.sqlMessage || e.message}`, 422);
    } finally {
      conn.release();
    }
  }

  return { run };
}

module.exports = { createQueryExecutor, QueryError };
