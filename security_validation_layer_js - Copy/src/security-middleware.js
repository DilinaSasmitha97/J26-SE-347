/**
 * AI Query Security & Validation Layer — Member 2 (Navodya P G D, IT23144330)
 *
 * Public surface:
 *   validate(sql, allowWrites)  -> ValidationResult
 *   securityMiddleware(opts)    -> Express request guard around validate()
 *   mask(result, classification)  -> PII masking of query results (pii-masker.js)
 *   validateRewritten              -> stub, lands with Member 3's integration
 *
 * The Controlled Write Protocol (preview -> approve -> commit) lives in
 * controlled-write.js and runs every write back through validate().
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
// PII masking for query results (src/pii-masker.js) — re-exported as part of this layer's surface.
const { mask } = require('./pii-masker');

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

// MySQL's own catalog/metadata schemas. Reading them maps the whole database
// (information_schema) or leaks credentials (mysql.user), so no tenant query
// may reference them, allowlist or not.
const SYSTEM_SCHEMAS = new Set(['information_schema', 'mysql', 'performance_schema', 'sys']);

// A reporting query that asks for more rows than this is either a mistake or
// an attempt to dump a table in one request.
const MAX_LIMIT_ROWS = 10000;

// More distinct table references than this is a planner-blowup risk (cartesian
// products) rather than a real report.
const MAX_TABLE_REFERENCES = 8;

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

/**
 * True for a FROM/JOIN/INTO/UPDATE table entry. A column_ref also has a
 * `table` key (the qualifier in `o.id`) but carries a node `type`, and an
 * UPDATE ... SET entry carries `column`, so both are excluded.
 */
function isTableRef(node) {
  return typeof node.table === 'string' && node.table !== '' && !node.type && !('column' in node);
}

/** Return every table reference as { db, table, as }, including subqueries and JOINs. */
function getTableRefs(ast) {
  const refs = [];
  for (const node of walkNodes(ast)) {
    if (isTableRef(node)) refs.push({ db: node.db || null, table: node.table, as: node.as || null });
  }
  return refs;
}

/** Return all table names referenced anywhere in the AST (incl. subqueries, JOINs). */
function getTables(ast) {
  return [...new Set(getTableRefs(ast).map((r) => r.table))].sort();
}

/** Names defined by WITH ... AS (...) — they look like tables but are not. */
function getCteNames(ast) {
  const names = new Set();
  for (const node of walkNodes(ast)) {
    if (!Array.isArray(node.with)) continue;
    for (const cte of node.with) {
      const name = cte && cte.name && (cte.name.value !== undefined ? cte.name.value : cte.name);
      if (name) names.add(String(name).toLowerCase());
    }
  }
  return names;
}

/** Column name of a column_ref, across the parser's string and { expr } shapes. */
function columnName(ref) {
  const c = ref.column;
  if (typeof c === 'string') return c;
  if (c && c.expr && c.expr.value !== undefined) return String(c.expr.value);
  return null;
}

/** Tables from MySQL's system schemas (information_schema, mysql, ...). */
function getSystemSchemaRefs(ast) {
  return getTableRefs(ast).filter((r) => r.db && SYSTEM_SCHEMAS.has(String(r.db).toLowerCase()));
}

/** Server/system variables such as @@version or @@hostname. User variables (@x) are not included. */
function getSystemVariables(ast) {
  const names = new Set();
  for (const node of walkNodes(ast)) {
    if (node.type === 'var' && node.prefix === '@@') names.add('@@' + node.name);
  }
  return [...names].sort();
}

/** Locking clauses (FOR UPDATE, LOCK IN SHARE MODE) used anywhere in the query. */
function getLockingReads(ast) {
  const found = new Set();
  for (const node of walkNodes(ast)) {
    if (typeof node.locking_read === 'string' && node.locking_read) found.add(node.locking_read.toUpperCase());
  }
  return [...found];
}

/** Largest row count requested by any LIMIT in the query, or null if there is none. */
function getMaxLimit(ast) {
  let max = null;
  for (const node of walkNodes(ast)) {
    const limit = node.limit;
    if (!limit || !Array.isArray(limit.value) || !limit.value.length) continue;
    // `LIMIT offset, count` puts the count second; `LIMIT count OFFSET n` puts it first.
    const countNode = limit.seperator === ',' ? limit.value[1] : limit.value[0];
    if (countNode && countNode.type === 'number') {
      const n = Number(countNode.value);
      if (max === null || n > max) max = n;
    }
  }
  return max;
}

/** Normalise an allowlist into Map<lowercase table, '*' | Set<lowercase column>>. */
function normalizeAllowlist(allowlist) {
  const map = new Map();
  for (const [table, rule] of Object.entries(allowlist || {})) {
    map.set(table.toLowerCase(), rule === '*' ? '*' : new Set(rule.map((c) => String(c).toLowerCase())));
  }
  return map;
}

/**
 * Check every table and column the query touches against a schema allowlist:
 *   { orders: '*', customers: ['id', 'name', 'email'] }
 * '*' allows every column of that table; a list allows only those columns, and
 * SELECT * on such a table is refused because it would pull the others too.
 * CTE names, derived-table aliases and SELECT-list aliases are not real
 * columns/tables and are skipped; their inner queries are checked directly.
 */
function checkAllowlist(ast, allowlist) {
  const allowed = normalizeAllowlist(allowlist);
  const violations = [];
  const reported = new Set();
  const report = (type, key, detail) => {
    if (reported.has(type + key)) return;
    reported.add(type + key);
    violations.push(new Violation(type, detail));
  };

  const cteNames = getCteNames(ast);
  const aliasToTable = new Map(); // qualifier -> real table, or null for derived/CTE sources
  const realTables = new Set();
  const selectAliases = new Set();

  for (const node of walkNodes(ast)) {
    if (isTableRef(node)) {
      const table = node.table.toLowerCase();
      if (!node.db && cteNames.has(table)) {
        aliasToTable.set(String(node.as || node.table).toLowerCase(), null);
        continue;
      }
      realTables.add(table);
      aliasToTable.set(table, table);
      if (node.as) aliasToTable.set(String(node.as).toLowerCase(), table);
      if (!allowed.has(table)) report('table_not_allowed', table, `${node.table} is not in the schema allowlist`);
    } else if (node.expr && node.expr.ast && node.as) {
      aliasToTable.set(String(node.as).toLowerCase(), null);
    }
    if (node.type === 'select' && Array.isArray(node.columns)) {
      for (const c of node.columns) if (c && c.as) selectAliases.add(String(c.as).toLowerCase());
    }
  }

  const allows = (table, col) => {
    const rule = allowed.get(table);
    if (rule === '*') return true;
    return Boolean(rule) && col !== '*' && rule.has(col);
  };
  const refuse = (table, col) => {
    if (col === '*') {
      report('column_not_allowed', `${table}.*`, `SELECT * is not allowed on ${table} (restricted columns) — list the columns explicitly`);
    } else {
      report('column_not_allowed', `${table}.${col}`, `${table ? table + '.' : ''}${col} is not in the schema allowlist`);
    }
  };

  const checkColumn = (qualifier, col) => {
    const lc = col.toLowerCase();
    if (qualifier) {
      const key = String(qualifier).toLowerCase();
      if (!aliasToTable.has(key)) return; // unknown qualifier: MySQL itself will reject it
      const table = aliasToTable.get(key);
      if (table === null || !allowed.has(table)) return; // derived source, or table already reported
      if (!allows(table, lc)) refuse(table, lc);
      return;
    }
    if (lc !== '*' && selectAliases.has(lc)) return;
    const candidates = [...realTables].filter((t) => allowed.has(t));
    if (!candidates.length) return;
    if (lc === '*') {
      for (const t of candidates) if (!allows(t, '*')) refuse(t, '*');
    } else if (!candidates.some((t) => allows(t, lc))) {
      refuse(candidates.length === 1 ? candidates[0] : '', lc);
    }
  };

  for (const node of walkNodes(ast)) {
    if (node.type === 'column_ref') {
      const col = columnName(node);
      if (col) checkColumn(node.table, col);
    }
  }

  // Write targets: INSERT column list and UPDATE ... SET columns.
  const type = String(ast.type || '').toLowerCase();
  const target = Array.isArray(ast.table) && ast.table[0] && ast.table[0].table;
  if (type === 'insert' && target) {
    if (Array.isArray(ast.columns) && ast.columns.length) {
      for (const c of ast.columns) checkColumn(target, typeof c === 'string' ? c : columnName({ column: c }) || '');
    } else {
      checkColumn(target, '*'); // INSERT without a column list writes every column
    }
  }
  if (type === 'update' && Array.isArray(ast.set)) {
    for (const s of ast.set) if (s && s.column) checkColumn(s.table || null, String(s.column));
  }

  return violations;
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

// ---- Constant folding for tautology detection ------------------------------
// constEval() returns the value MySQL would compute for an expression built
// only from literals, or NOT_CONST as soon as a column/function is involved.
// Values follow MySQL semantics: numbers, strings, and null for SQL NULL.

const NOT_CONST = undefined;
const _STRING_TYPES = new Set(['single_quote_string', 'double_quote_string', 'string', 'natural_string']);

/** MySQL's string-to-number cast: leading numeric prefix, otherwise 0. */
function sqlToNumber(v) {
  if (v === null) return null;
  if (typeof v === 'number') return v;
  const m = String(v).match(/^\s*[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?/i);
  return m ? Number(m[0]) : 0;
}

/** true / false / null (SQL NULL) / undefined (not a constant). */
function sqlTruth(v) {
  if (v === NOT_CONST) return undefined;
  if (v === null) return null;
  return sqlToNumber(v) !== 0;
}

function sqlCompare(a, b) {
  if (typeof a === 'string' && typeof b === 'string') {
    const x = a.toLowerCase(); // default collations are case-insensitive
    const y = b.toLowerCase();
    return x < y ? -1 : x > y ? 1 : 0;
  }
  const x = sqlToNumber(a);
  const y = sqlToNumber(b);
  return x < y ? -1 : x > y ? 1 : 0;
}

function likeToRegExp(pattern) {
  let re = '';
  for (let i = 0; i < pattern.length; i++) {
    const ch = pattern[i];
    if (ch === '\\' && i + 1 < pattern.length) re += pattern[++i].replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    else if (ch === '%') re += '.*';
    else if (ch === '_') re += '.';
    else re += ch.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }
  return new RegExp('^' + re + '$', 'is');
}

function constEval(node) {
  if (!node || typeof node !== 'object') return NOT_CONST;
  if (node.type === 'number') return Number(node.value);
  if (node.type === 'bool') return node.value ? 1 : 0;
  if (node.type === 'null') return null;
  if (_STRING_TYPES.has(node.type)) return String(node.value);

  if (node.type === 'unary_expr') {
    const v = constEval(node.expr);
    if (v === NOT_CONST) return NOT_CONST;
    const op = String(node.operator).toUpperCase();
    if (op === 'NOT' || op === '!') return v === null ? null : (sqlTruth(v) ? 0 : 1);
    if (op === '-') return v === null ? null : -sqlToNumber(v);
    if (op === '+') return v;
    return NOT_CONST;
  }

  if (node.type !== 'binary_expr') return NOT_CONST;
  const op = String(node.operator).toUpperCase();

  // OR / AND short-circuit, so `col = 5 OR 1` still folds to true.
  if (op === 'OR' || op === '||' || op === 'AND' || op === '&&') {
    const l = sqlTruth(constEval(node.left));
    const r = sqlTruth(constEval(node.right));
    if (op === 'OR' || op === '||') {
      if (l === true || r === true) return 1;
      if (l === undefined || r === undefined) return NOT_CONST;
      return l === false && r === false ? 0 : null;
    }
    if (l === false || r === false) return 0;
    if (l === undefined || r === undefined) return NOT_CONST;
    return l === true && r === true ? 1 : null;
  }

  if (op === 'IN' || op === 'NOT IN') {
    const l = constEval(node.left);
    const list = node.right && node.right.type === 'expr_list' ? node.right.value.map(constEval) : null;
    if (l === NOT_CONST || !list || list.some((x) => x === NOT_CONST)) return NOT_CONST;
    if (l === null) return null;
    const hit = list.some((x) => x !== null && sqlCompare(l, x) === 0);
    return (op === 'IN') === hit ? 1 : 0;
  }

  const l = constEval(node.left);
  const r = constEval(node.right);
  if (l === NOT_CONST || r === NOT_CONST) return NOT_CONST;

  if (op === 'IS') return r === null ? (l === null ? 1 : 0) : NOT_CONST;
  if (op === 'IS NOT') return r === null ? (l !== null ? 1 : 0) : NOT_CONST;
  if (op === '<=>') return l === null || r === null ? (l === r ? 1 : 0) : (sqlCompare(l, r) === 0 ? 1 : 0);
  if (l === null || r === null) return null;

  switch (op) {
    case '=': return sqlCompare(l, r) === 0 ? 1 : 0;
    case '!=': case '<>': return sqlCompare(l, r) !== 0 ? 1 : 0;
    case '<': return sqlCompare(l, r) < 0 ? 1 : 0;
    case '>': return sqlCompare(l, r) > 0 ? 1 : 0;
    case '<=': return sqlCompare(l, r) <= 0 ? 1 : 0;
    case '>=': return sqlCompare(l, r) >= 0 ? 1 : 0;
    case '+': return sqlToNumber(l) + sqlToNumber(r);
    case '-': return sqlToNumber(l) - sqlToNumber(r);
    case '*': return sqlToNumber(l) * sqlToNumber(r);
    case '/': return sqlToNumber(r) === 0 ? null : sqlToNumber(l) / sqlToNumber(r);
    case 'LIKE': return likeToRegExp(String(r)).test(String(l)) ? 1 : 0;
    case 'NOT LIKE': return likeToRegExp(String(r)).test(String(l)) ? 0 : 1;
    default: return NOT_CONST;
  }
}

const _SELF_TRUE_OPERATORS = new Set(['=', '<=', '>=', '<=>', 'LIKE']);

/** `id = id`, `o.total >= o.total` — true for every non-NULL row. */
function isSelfComparison(node) {
  if (!node || node.type !== 'binary_expr' || !_SELF_TRUE_OPERATORS.has(String(node.operator).toUpperCase())) return false;
  const { left, right } = node;
  if (!left || !right || left.type !== 'column_ref' || right.type !== 'column_ref') return false;
  const l = columnName(left);
  const r = columnName(right);
  return Boolean(l) && String(l).toLowerCase() === String(r).toLowerCase()
    && String(left.table || '').toLowerCase() === String(right.table || '').toLowerCase();
}

function isAlwaysTrue(node) {
  if (!node || typeof node !== 'object') return false;
  if (sqlTruth(constEval(node)) === true) return true;
  if (isSelfComparison(node)) return true;
  if (node.type === 'binary_expr') {
    const op = String(node.operator).toUpperCase();
    if (op === 'OR' || op === '||') return isAlwaysTrue(node.left) || isAlwaysTrue(node.right);
    if (op === 'AND' || op === '&&') return isAlwaysTrue(node.left) && isAlwaysTrue(node.right);
  }
  return false;
}

/**
 * True when a filter can no longer filter anything: the whole predicate is
 * always true (`WHERE 1`, `WHERE 1=1`, `WHERE NOT 0`), or any OR branch inside
 * it is (`id = 5 OR 1`, `... OR 2 > 1`, `... OR id = id`) — the classic
 * injection shape for bypassing row filtering. `WHERE 1=1 AND tenant_id = 1`
 * is not flagged: the AND still filters.
 */
function isAlwaysTruePredicate(predicate) {
  if (!predicate || typeof predicate !== 'object') return false;
  if (isAlwaysTrue(predicate)) return true;
  for (const node of walkNodes(predicate)) {
    if (node.type !== 'binary_expr') continue;
    const op = String(node.operator).toUpperCase();
    if ((op === 'OR' || op === '||') && (isAlwaysTrue(node.left) || isAlwaysTrue(node.right))) return true;
  }
  return false;
}

/** Check every WHERE, HAVING and JOIN ... ON in the query, including subqueries. */
function hasTautology(ast) {
  for (const node of walkNodes(ast)) {
    for (const key of ['where', 'having', 'on']) {
      if (node[key] && typeof node[key] === 'object' && isAlwaysTruePredicate(node[key])) return true;
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
    const code = stripQuoted(sql);
    return code.includes(';') && code.trim().replace(/;+$/, '').includes(';');
  }
}

/**
 * Blank out the contents of '...', "..." and `...` so text inside a literal
 * (`note = 'item #3'`) is not mistaken for SQL syntax. Handles backslash
 * escapes and doubled quotes; the quote characters themselves are kept.
 */
function stripQuoted(sql) {
  let out = '';
  let quote = null;
  for (let i = 0; i < sql.length; i++) {
    const ch = sql[i];
    if (quote) {
      if (ch === '\\' && quote !== '`') { i++; continue; }
      if (ch === quote) {
        if (sql[i + 1] === quote) { i++; continue; }
        quote = null;
        out += ch;
      }
      continue;
    }
    if (ch === "'" || ch === '"' || ch === '`') quote = ch;
    out += ch;
  }
  return out;
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
// text because the parser silently discards comments — but with string
// literals blanked out first, so `'item #3'` is not a comment.
// Any `--` outside a literal is flagged, even without the whitespace MySQL
// requires: the parser treats `--'` as a comment and drops the rest of the
// query (`'admin'--' AND password = 'x'`), so the validator would check a
// different query from the one MySQL receives. The cost is that `5--3`
// (five minus minus three) is refused too.
function hasSqlComment(sql) {
  if (typeof sql !== 'string') return false;
  const code = stripQuoted(sql);
  return code.includes('--') || code.includes('#') || code.includes('/*');
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
 * options.allowlist — optional schema allowlist, { table: '*' | [columns] }.
 * When given, every table and column the query touches must be on it.
 *
 * Returns ValidationResult { safe, statementType, violations, rewrittenAst }.
 * `rewrittenAst` is null here; Member 3's tenant-isolation pass populates it,
 * and this module re-validates that AST via validateRewritten() before execution.
 */
function validate(sql, allowWrites = false, options = {}) {
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
    // Keep the stacked_statements finding: it says *why* the text did not parse as one query.
    return new ValidationResult({
      safe: false,
      statementType: 'UNPARSEABLE',
      violations: [...violations, new Violation('parse_error', e.message)],
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

  for (const name of getSystemVariables(ast)) {
    violations.push(new Violation('system_variable', `${name} — exposes server configuration (fingerprinting)`));
  }

  for (const ref of getSystemSchemaRefs(ast)) {
    violations.push(new Violation('system_schema_access', `${ref.db}.${ref.table} — MySQL system schemas are never queryable`));
  }

  if (options.allowlist) {
    violations.push(...checkAllowlist(ast, options.allowlist));
  }

  if (hasTautology(ast)) {
    violations.push(new Violation('tautology_predicate', 'Always-true condition makes a WHERE/HAVING/ON filter match every row'));
  }

  for (const lock of getLockingReads(ast)) {
    violations.push(new Violation('locking_read', `${lock} — a read query must not take row locks`));
  }

  const limit = getMaxLimit(ast);
  if (limit !== null && limit > MAX_LIMIT_ROWS) {
    violations.push(new Violation('excessive_limit', `LIMIT ${limit} (max allowed: ${MAX_LIMIT_ROWS})`));
  }

  const tableCount = getTableRefs(ast).length;
  if (tableCount > MAX_TABLE_REFERENCES) {
    violations.push(new Violation('too_many_tables', `${tableCount} table references (max allowed: ${MAX_TABLE_REFERENCES})`));
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


/**
 * Build an Express request guard around validate(). The result is always
 * attached as `req.validation`; unsafe queries never reach the route handler.
 *
 * options:
 *   getSql(req)   -> where to read the SQL from (default: req.body.sql)
 *   allowWrites   -> boolean, or (req) => boolean for per-request
 *                    Controlled Write Protocol authorization
 *   allowlist     -> schema allowlist passed to validate(), or (req) => allowlist
 *                    to pick one per tenant
 *   onBlock(req, res, result) -> custom rejection response (default: 403 JSON)
 */
function securityMiddleware(options = {}) {
  const {
    getSql = (req) => req.body && req.body.sql,
    allowWrites = false,
    allowlist = null,
    onBlock = null,
  } = options;

  return function validateSqlRequest(req, res, next) {
    const sql = getSql(req);
    const writesAllowed = typeof allowWrites === 'function' ? Boolean(allowWrites(req)) : Boolean(allowWrites);
    const tableAllowlist = typeof allowlist === 'function' ? allowlist(req) : allowlist;
    const result = validate(sql, writesAllowed, { allowlist: tableAllowlist });
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
  mask,
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
  getTableRefs,
  getFunctions,
  getWhereClause,
  hasWhereClause,
  isAlwaysTruePredicate,
  hasTautology,
  constEval,
  checkAllowlist,
  getSystemVariables,
  getSystemSchemaRefs,
  getLockingReads,
  getMaxLimit,
  stripQuoted,
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
  SYSTEM_SCHEMAS,
  MAX_LIMIT_ROWS,
  MAX_TABLE_REFERENCES,
};
