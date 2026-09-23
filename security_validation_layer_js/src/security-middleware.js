/**
 * AI Query Security & Validation Layer — Member 2 (Navodya P G D, IT23144330)
 *
 * Public surface:
 *   validate(sql, allowWrites)  -> ValidationResult
 *   securityMiddleware(opts)    -> Express request guard around validate()
 *   validateRewritten / previewWrite / mask  -> stubs, land in Months 2-4
 *
 * Pipeline: Member 1 (NL-to-SQL) -> [this module] -> Member 3 (tenant-isolation
 * AST rewrite) -> [this module, re-validation] -> execution -> Member 4.
 *
 * Deny-by-default: only SELECT is permitted unless the caller passes
 * allowWrites, and DROP/TRUNCATE/CREATE/ALTER/GRANT/REPLACE/REVOKE are refused
 * no matter what.
 */

'use strict';

const path = require('path');
const fs = require('fs');
const { Parser } = require('node-sql-parser');

const DIALECT = 'MySQL';
const _parser = new Parser();

const DEFAULT_ALLOWED_STATEMENTS = new Set(['SELECT']);
const WRITE_STATEMENTS = new Set(['INSERT', 'UPDATE', 'DELETE']);

// Never permitted, regardless of allowWrites. REVOKE currently fails to parse
// under node-sql-parser's MySQL grammar and is caught earlier as UNPARSEABLE —
// it stays listed in case that grammar gains support for it.
const ALWAYS_BLOCKED_STATEMENTS = new Set([
  'DROP', 'TRUNCATE', 'CREATE', 'ALTER', 'COMMAND', 'GRANT', 'REPLACE', 'REVOKE',
]);

// Legitimate multi-tenant reporting queries rarely exceed 2-3 levels; beyond
// that is either obfuscation or a planner-blowup denial-of-service attempt.
const MAX_SUBQUERY_DEPTH = 6;

const CONFIG_PATH = path.resolve(__dirname, '..', 'config', 'dangerous_functions.json');

let _blocklistCache = null;

/**
 * Return { FUNCTION_NAME: reason } merged from both blocklist sections.
 * Filesystem/DoS functions and fingerprinting functions are both hard blocks —
 * extend the JSON file, not this logic.
 */
function loadFunctionBlocklist() {
  if (_blocklistCache) return _blocklistCache;
  const data = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  const merged = Object.assign({}, data.dangerous_functions, data.system_info_functions);
  _blocklistCache = {};
  for (const [name, reason] of Object.entries(merged)) {
    _blocklistCache[name.toUpperCase()] = reason;
  }
  return _blocklistCache;
}

const BLOCKED_FUNCTIONS = loadFunctionBlocklist();

/** Raised when input SQL cannot be safely parsed into an AST. */
class SQLParseError extends Error {
  constructor(message, originalSql) {
    super(message);
    this.name = 'SQLParseError';
    this.originalSql = originalSql || '';
  }
}

/**
 * Parse a single SQL statement into { sql, ast }.
 *
 * Multi-statement input is rejected rather than silently parsing the first
 * statement — that is how stacked-injection payloads get through.
 */
function parse(sql) {
  if (typeof sql !== 'string' || !sql.trim()) {
    throw new SQLParseError('Empty SQL input', sql);
  }

  let parsed;
  try {
    parsed = _parser.astify(sql, { database: DIALECT });
  } catch (e) {
    throw new SQLParseError(`Failed to parse SQL: ${String(e.message).split('\n')[0]}`, sql);
  }

  const statements = (Array.isArray(parsed) ? parsed : [parsed]).filter(Boolean);

  if (statements.length === 0) throw new SQLParseError('No valid SQL statement found', sql);
  if (statements.length > 1) {
    throw new SQLParseError(
      `Multiple statements (${statements.length}) in a single request are not allowed`,
      sql,
    );
  }

  return { sql, ast: statements[0] };
}

/** Re-serialize a (possibly rewritten) AST back to MySQL SQL text. */
function toSql(ast) {
  return _parser.sqlify(ast, { database: DIALECT });
}

// node-sql-parser AST notes that shape the helpers below:
//  - a statement is a plain object with a lowercase `type` ("select", "drop");
//  - UNION is not its own node — it is a select carrying `set_op` and `_next`;
//  - a subquery sits behind a { tableList, columnList, ast } wrapper, so a
//    generic recursive walk reaches every nesting level for free.

const _STATEMENT_TYPE_MAP = {
  select: 'SELECT',
  insert: 'INSERT',
  update: 'UPDATE',
  delete: 'DELETE',
  drop: 'DROP',
  create: 'CREATE',
  alter: 'ALTER',
  truncate: 'TRUNCATE',
  grant: 'GRANT',
  revoke: 'REVOKE',
  replace: 'REPLACE',
};

/** Walk every nested object/array in the AST, yielding each object node. */
function* walkNodes(node) {
  if (node === null || typeof node !== 'object') return;
  if (Array.isArray(node)) {
    for (const item of node) yield* walkNodes(item);
    return;
  }
  yield node;
  for (const value of Object.values(node)) yield* walkNodes(value);
}

/**
 * Return a coarse statement-type label, e.g. SELECT/INSERT/DROP/UNKNOWN.
 * Unmapped admin statements (SHOW, SET, USE) keep their own upper-cased
 * keyword so violation logs name the real statement.
 */
function getStatementType(ast) {
  const type = ast && ast.type;
  if (!type) return 'UNKNOWN';
  return _STATEMENT_TYPE_MAP[String(type).toLowerCase()] || String(type).toUpperCase();
}

/**
 * Recover a statement type from the raw text's leading keyword when the grammar
 * refused the statement outright (`GRANT ALL PRIVILEGES ...`, `REVOKE ...`).
 * Only ever returns an always-blocked keyword, so it cannot promote anything
 * harmless; without it these would degrade to a generic parse_error.
 */
function getStatementTypeFromText(sql) {
  const match = typeof sql === 'string' ? sql.match(/^\s*([A-Za-z_]+)/) : null;
  if (!match) return null;
  const keyword = match[1].toUpperCase();
  return ALWAYS_BLOCKED_STATEMENTS.has(keyword) ? keyword : null;
}

/** Return all table names referenced anywhere in the AST (incl. subqueries, JOINs). */
function getTables(ast) {
  const names = new Set();
  for (const node of walkNodes(ast)) {
    // A column_ref also has a `table` key (the qualifier in `o.id`), so require
    // the absence of a node `type` to keep only FROM/INTO entries.
    if (typeof node.table === 'string' && node.table && !node.type) names.add(node.table);
  }
  return [...names].sort();
}

/**
 * Return all function/aggregate names invoked anywhere in the AST, upper-cased.
 * Two node shapes carry a call: `function` nodes hold the name under
 * `name.name[].value`, aggregates (`aggr_func`) hold a plain string `name`.
 */
function getFunctions(ast) {
  const names = new Set();
  for (const node of walkNodes(ast)) {
    if (node.type === 'function' && node.name) {
      const parts = Array.isArray(node.name.name) ? node.name.name : [node.name];
      const called = parts.map((p) => (p && p.value !== undefined ? p.value : p)).filter(Boolean);
      if (called.length) names.add(String(called[called.length - 1]).toUpperCase());
    } else if (node.type === 'aggr_func' && typeof node.name === 'string') {
      names.add(node.name.toUpperCase());
    }
  }
  return [...names].sort();
}

/** Return the WHERE predicate of a statement, if any. */
function getWhereClause(ast) {
  const where = ast && ast.where;
  return where && typeof where === 'object' ? where : null;
}

function hasWhereClause(ast) {
  return getWhereClause(ast) !== null;
}

const _LITERAL_TYPES = new Set([
  'number', 'single_quote_string', 'double_quote_string', 'string', 'bool', 'hex_string',
]);

/**
 * Detect tautologies like `1=1` or `'a'='a'` anywhere in a WHERE tree — a
 * common injection artifact used to bypass row filtering.
 */
function isAlwaysTruePredicate(where) {
  for (const node of walkNodes(where)) {
    if (node.type !== 'binary_expr' || node.operator !== '=') continue;
    const { left, right } = node;
    if (!left || !right) continue;
    if (_LITERAL_TYPES.has(left.type) && _LITERAL_TYPES.has(right.type)) {
      if (String(left.value) === String(right.value)) return true;
    }
  }
  return false;
}

/**
 * Detect stacked queries (`SELECT ...; DROP ...`) from the raw SQL text.
 * Takes text rather than an AST because a stacked payload's first statement is
 * usually perfectly valid.
 */
function hasStackedStatements(sql) {
  if (typeof sql !== 'string') return false;
  try {
    const parsed = _parser.astify(sql, { database: DIALECT });
    return Array.isArray(parsed) && parsed.filter(Boolean).length > 1;
  } catch (e) {
    // An unparseable trailing fragment after `;` is itself suspicious.
    return sql.includes(';') && sql.trim().replace(/;+$/, '').includes(';');
  }
}

/**
 * Return how many levels deep the most nested subquery/UNION branch goes.
 * A flat query is depth 0; each SELECT inside another one adds a level.
 */
function getMaxSubqueryDepth(ast) {
  function walk(node, depth) {
    if (node === null || typeof node !== 'object') return depth;
    let best = depth;
    for (const value of Object.values(node)) {
      const children = Array.isArray(value) ? value : [value];
      for (const child of children) {
        if (child === null || typeof child !== 'object') continue;
        const childDepth = child.type === 'select' ? depth + 1 : depth;
        best = Math.max(best, walk(child, childDepth));
      }
    }
    return best;
  }
  return walk(ast, 0);
}

// Comment markers can truncate or hide the rest of a query. Checked against raw
// text because the parser silently discards comments.
function hasSqlComment(sql) {
  if (typeof sql !== 'string') return false;
  return sql.includes('--') || sql.includes('#') || sql.includes('/*');
}

/** True when a SELECT is part of a UNION anywhere in the tree, not just at the top level. */
function hasUnion(ast) {
  for (const node of walkNodes(ast)) {
    if (node.set_op && String(node.set_op).toLowerCase().startsWith('union')) return true;
  }
  return false;
}

/**
 * A single reason a query was rejected — machine-readable (`type`) for
 * logging/metrics branching, human-readable (`detail`) for display.
 */
class Violation {
  constructor(type, detail = '') {
    this.type = type;
    this.detail = detail;
  }

  toString() {
    return this.detail ? `${this.type}: ${this.detail}` : this.type;
  }
}

class ValidationResult {
  constructor({ safe, statementType, violations = [], rewrittenAst = null }) {
    this.safe = safe;
    this.statementType = statementType;
    this.violations = violations;
    this.rewrittenAst = rewrittenAst;
  }
}

/**
 * Validate raw SQL against the allowlist + injection-artifact rules.
 *
 * Returns ValidationResult { safe, statementType, violations, rewrittenAst }.
 * `rewrittenAst` is null here; Member 3's tenant-isolation pass populates it,
 * and this module re-validates that AST via validateRewritten() before execution.
 */
function validate(sql, allowWrites = false) {
  const violations = [];

  // Must run on raw text, before parsing — see hasStackedStatements().
  if (hasStackedStatements(sql)) {
    violations.push(new Violation('stacked_statements', 'Multiple SQL statements found in one request'));
  }

  let parsed;
  try {
    parsed = parse(sql);
  } catch (e) {
    if (!(e instanceof SQLParseError)) throw e;
    const adminKeyword = getStatementTypeFromText(sql);
    if (adminKeyword) {
      return new ValidationResult({
        safe: false,
        statementType: adminKeyword,
        violations: [new Violation('blocked_statement_type', adminKeyword)],
      });
    }
    return new ValidationResult({
      safe: false,
      statementType: 'UNPARSEABLE',
      violations: [new Violation('parse_error', e.message)],
    });
  }

  const ast = parsed.ast;
  const stmtType = getStatementType(ast);

  if (ALWAYS_BLOCKED_STATEMENTS.has(stmtType)) {
    violations.push(new Violation('blocked_statement_type', stmtType));
  } else if (WRITE_STATEMENTS.has(stmtType) && !allowWrites) {
    violations.push(new Violation('write_not_authorized', stmtType));
  } else if (!DEFAULT_ALLOWED_STATEMENTS.has(stmtType) && !WRITE_STATEMENTS.has(stmtType)) {
    violations.push(new Violation('blocked_statement_type', stmtType));
  }

  for (const fn of getFunctions(ast)) {
    if (Object.prototype.hasOwnProperty.call(BLOCKED_FUNCTIONS, fn)) {
      violations.push(new Violation('dangerous_function', `${fn} — ${BLOCKED_FUNCTIONS[fn]}`));
    }
  }

  // INTO OUTFILE/DUMPFILE are clause syntax, not function calls, so they are
  // checked structurally rather than via getFunctions().
  const into = ast.into;
  if (into && into.keyword) {
    const keyword = String(into.keyword).toUpperCase();
    if (keyword === 'OUTFILE') {
      violations.push(new Violation('dangerous_function', `INTO OUTFILE — ${BLOCKED_FUNCTIONS.INTO_OUTFILE || 'writes results to a server-side file'}`));
    } else if (keyword === 'DUMPFILE') {
      violations.push(new Violation('dangerous_function', `INTO DUMPFILE — ${BLOCKED_FUNCTIONS.INTO_DUMPFILE || 'writes results to a server-side file'}`));
    }
  }

  const where = getWhereClause(ast);
  if (where !== null && isAlwaysTruePredicate(where)) {
    violations.push(new Violation('tautology_predicate', 'Always-true condition found in WHERE clause'));
  }

  if (stmtType === 'DELETE' && !hasWhereClause(ast)) {
    violations.push(new Violation('delete_without_where', 'DELETE has no WHERE clause — would affect every row'));
  }
  if (stmtType === 'UPDATE' && !hasWhereClause(ast)) {
    violations.push(new Violation('update_without_where', 'UPDATE has no WHERE clause — would affect every row'));
  }

  if (hasUnion(ast)) {
    violations.push(new Violation('union_query', 'UNION can merge in rows from an unrelated query'));
  }

  if (hasSqlComment(sql)) {
    violations.push(new Violation('sql_comment_present', 'Comment marker could truncate/hide part of the query'));
  }

  const depth = getMaxSubqueryDepth(ast);
  if (depth > MAX_SUBQUERY_DEPTH) {
    violations.push(new Violation('excessive_subquery_depth', `Nested ${depth} levels deep (max allowed: ${MAX_SUBQUERY_DEPTH})`));
  }

  return new ValidationResult({
    safe: violations.length === 0,
    statementType: stmtType,
    violations,
  });
}

// AST ownership convention agreed with Member 3: he rewrites the AST produced
// here to inject row-level tenant isolation, and this module re-validates it
// before it is sent to the database. No execution without that second pass.

/** Re-validate an AST after Member 3's tenant-isolation rewrite. */
function validateRewritten(rewrittenAst) {
  throw new Error(
    'validateRewritten() lands once the AST-rewriting integration contract with Member 3 is finalized.',
  );
}

/** Placeholder for the Controlled Write Protocol state object (Month 3). */
class WriteApprovalRequest {
  constructor(sql, previewRows = null, status = 'pending') {
    this.sql = sql;
    this.previewRows = previewRows;
    // pending -> previewed -> approved -> committed | rejected
    this.status = status;
  }
}

/** Run an authorized write in a transaction, capture a row preview, roll back. */
function previewWrite(sql) {
  throw new Error('previewWrite() lands in Month 3 (Controlled Write Protocol).');
}

/** Apply PII detection + masking before results reach Member 4's layer. */
function mask(resultSet) {
  throw new Error('mask() lands in Month 4 (PII detection & masking pipeline).');
}

/**
 * Build an Express request guard around validate(). The result is always
 * attached as `req.validation`; unsafe queries never reach the route handler.
 *
 * options:
 *   getSql(req)   -> where to read the SQL from (default: req.body.sql)
 *   allowWrites   -> boolean, or (req) => boolean for per-request
 *                    Controlled Write Protocol authorization
 *   onBlock(req, res, result) -> custom rejection response (default: 403 JSON)
 */
function securityMiddleware(options = {}) {
  const {
    getSql = (req) => req.body && req.body.sql,
    allowWrites = false,
    onBlock = null,
  } = options;

  return function validateSqlRequest(req, res, next) {
    const sql = getSql(req);
    const writesAllowed = typeof allowWrites === 'function' ? Boolean(allowWrites(req)) : Boolean(allowWrites);
    const result = validate(sql, writesAllowed);
    req.validation = result;

    if (result.safe) return next();
    if (onBlock) return onBlock(req, res, result);

    return res.status(403).json({
      error: 'query_blocked',
      statementType: result.statementType,
      violations: result.violations.map((v) => ({ type: v.type, detail: v.detail })),
    });
  };
}

module.exports = {
  // main surface
  validate,
  securityMiddleware,
  // contract stubs
  validateRewritten,
  previewWrite,
  mask,
  WriteApprovalRequest,
  // types
  Violation,
  ValidationResult,
  SQLParseError,
  // parsing + AST helpers (exported for Member 3's rewriting layer)
  parse,
  toSql,
  getStatementType,
  getStatementTypeFromText,
  getTables,
  getFunctions,
  getWhereClause,
  hasWhereClause,
  isAlwaysTruePredicate,
  hasStackedStatements,
  getMaxSubqueryDepth,
  hasSqlComment,
  hasUnion,
  loadFunctionBlocklist,
  // config
  DEFAULT_ALLOWED_STATEMENTS,
  WRITE_STATEMENTS,
  ALWAYS_BLOCKED_STATEMENTS,
  BLOCKED_FUNCTIONS,
  MAX_SUBQUERY_DEPTH,
};
