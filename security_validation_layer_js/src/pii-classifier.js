/**
 * PII column classification — decides, per result column, what personal data
 * it carries, so mask() knows what to do with every cell.
 *
 * Signals, strongest first:
 *   1. schema-tag    the column traces to a column declared in pii_columns.json
 *   2. lineage       it is *computed* from one (UPPER(name), CONCAT(...), MAX(email),
 *                    a subquery, a CTE, a derived table)
 *   3. column-name   the source/output name looks like PII (mobile_no, dob, ...)
 *   4. value-sample  most sampled values are detected as one PII type
 *      value-scan    some cells *contain* PII inside longer text
 *
 * Why lineage comes from the AST and not from MySQL: MySQL's result metadata
 * loses the trail through derived tables and CTEs —
 *   SELECT x FROM (SELECT email AS x FROM customers) d   reports  customers.x
 * — and reports nothing at all for computed columns. So each output column is
 * traced through the query itself: aliases, subqueries, CTEs, CASE branches and
 * functions. Functions whose output cannot reveal the input (COUNT, LENGTH,
 * SUM, comparisons) stop the trail; everything else carries it forward,
 * including hashes (a hash of an email is still personal data under GDPR).
 */

'use strict';

const { parse } = require('./security-middleware');
const { detectValue, detectInText } = require('./pii-detectors');

const NON_REVEALING_FUNCTIONS = new Set([
  'COUNT', 'SUM', 'AVG', 'STD', 'STDDEV', 'STDDEV_POP', 'STDDEV_SAMP', 'VARIANCE', 'VAR_POP', 'VAR_SAMP',
  'BIT_AND', 'BIT_OR', 'BIT_XOR', 'LENGTH', 'CHAR_LENGTH', 'CHARACTER_LENGTH', 'OCTET_LENGTH', 'BIT_LENGTH', 'ISNULL',
]);

// Comparisons and boolean logic return 0/1, never the operand's value.
const NON_REVEALING_OPERATORS = new Set([
  '=', '!=', '<>', '<', '>', '<=', '>=', '<=>', 'LIKE', 'NOT LIKE', 'REGEXP', 'NOT REGEXP', 'RLIKE',
  'IN', 'NOT IN', 'IS', 'IS NOT', 'BETWEEN', 'NOT BETWEEN', 'AND', 'OR', 'XOR', '&&',
]);

const NAME_HEURISTICS = [
  [/e-?mail/i, 'EMAIL'],
  [/phone|mobile|^tel$|telephone|contact_?no/i, 'PHONE'],
  [/(^|_)nic($|_)|national_?id|ssn|passport/i, 'NIC'],
  [/card_?(no|num|number)|^pan$|cc_?num/i, 'CREDIT_CARD'],
  [/iban|account_?(no|num|number)/i, 'IBAN'],
  [/(^|_)ip($|_)|ip_?addr/i, 'IP_ADDRESS'],
  [/^(first|last|middle|full|given|family|sur)_?name$|^(customer|user|employee|contact|person|holder)_?name$/i, 'PERSON'],
  [/address|street|postcode|postal_?code|zip/i, 'ADDRESS'],
  [/(^|_)dob($|_)|birth/i, 'DATE_OF_BIRTH'],
  [/password|passwd|secret|token|api_?key|_hash$/i, 'SECRET'],
];

const MAX_DEPTH = 20;
const lower = (s) => String(s).toLowerCase();

function columnName(ref) {
  const c = ref.column;
  if (typeof c === 'string') return c;
  if (c && c.expr && c.expr.value !== undefined) return String(c.expr.value);
  return null;
}

function functionName(node) {
  const parts = node.name && Array.isArray(node.name.name) ? node.name.name : [node.name];
  const last = parts[parts.length - 1];
  return String(last && last.value !== undefined ? last.value : last).toUpperCase();
}

const emptyLineage = () => ({ sources: new Set(), transforms: new Set() });

function mergeInto(target, from) {
  if (!from) return;
  for (const s of from.sources) target.sources.add(s);
  for (const t of from.transforms) target.transforms.add(t);
}

// ---- scopes ------------------------------------------------------------------
// A scope maps each FROM-clause name (alias or table) to a base table or to a
// derived source (subquery / CTE) whose own outputs are traced recursively.

function buildScope(select, parent, ctes) {
  const localCtes = new Map(ctes);
  if (Array.isArray(select.with)) {
    for (const w of select.with) {
      const name = w && w.name && (w.name.value !== undefined ? w.name.value : w.name);
      if (name && w.stmt && w.stmt.ast) localCtes.set(lower(name), { ast: w.stmt.ast, ctes: new Map(localCtes) });
    }
  }
  const entries = new Map();
  for (const f of Array.isArray(select.from) ? select.from : []) {
    if (typeof f.table === 'string' && f.table) {
      const table = lower(f.table);
      const key = lower(f.as || f.table);
      if (!f.db && localCtes.has(table)) {
        const cte = localCtes.get(table);
        entries.set(key, { kind: 'derived', ast: cte.ast, ctes: cte.ctes });
      } else {
        entries.set(key, { kind: 'table', table });
      }
    } else if (f.expr && f.expr.ast) {
      entries.set(lower(f.as || ''), { kind: 'derived', ast: f.expr.ast, ctes: localCtes });
    }
  }
  return { entries, parent, ctes: localCtes };
}

/**
 * The output columns of a SELECT, in order. Each is either
 *   { name, lineage }  an expression (or a column of a derived source), or
 *   { star: table }    a `*` over a base table, whose width only the result knows.
 */
function expandOutputs(select, parentScope, ctes, depth) {
  if (!select || depth > MAX_DEPTH) return [];
  const scope = buildScope(select, parentScope, ctes);
  const outputs = [];
  for (const item of Array.isArray(select.columns) ? select.columns : []) {
    const expr = item.expr || item;
    if (expr.type === 'column_ref' && columnName(expr) === '*') {
      const targets = expr.table ? [scope.entries.get(lower(expr.table))].filter(Boolean) : [...scope.entries.values()];
      for (const entry of targets) {
        if (entry.kind === 'table') outputs.push({ star: entry.table });
        else outputs.push(...expandOutputs(entry.ast, null, entry.ctes, depth + 1));
      }
      continue;
    }
    const name = item.as ? lower(item.as) : (expr.type === 'column_ref' ? lower(columnName(expr)) : null);
    outputs.push({ name, lineage: resolveExpr(expr, scope, depth) });
  }
  return outputs;
}

function fromEntry(entry, col, depth) {
  if (entry.kind === 'table') {
    const l = emptyLineage();
    l.sources.add(`${entry.table}.${col}`);
    return l;
  }
  const outputs = expandOutputs(entry.ast, null, entry.ctes, depth + 1);
  const named = outputs.find((o) => o.name === col);
  if (named) return named.lineage;
  const star = outputs.find((o) => o.star);
  if (star) {
    const l = emptyLineage();
    l.sources.add(`${star.star}.${col}`);
    return l;
  }
  return null;
}

function resolveColumn(ref, scope, depth) {
  const col = lower(columnName(ref));
  if (ref.table) {
    const q = lower(ref.table);
    for (let s = scope; s; s = s.parent) {
      if (s.entries.has(q)) return fromEntry(s.entries.get(q), col, depth);
    }
    return null;
  }
  // Unqualified: innermost scope that can supply the column wins.
  for (let s = scope; s; s = s.parent) {
    const found = emptyLineage();
    let hit = false;
    for (const entry of s.entries.values()) {
      const l = fromEntry(entry, col, depth);
      if (l && (l.sources.size || entry.kind === 'derived')) {
        mergeInto(found, l);
        hit = true;
      }
    }
    if (hit) return found;
  }
  return null;
}

/** Trace which source columns an expression's *value* can reveal. */
function resolveExpr(node, scope, depth) {
  const out = emptyLineage();
  const visit = (n) => {
    if (!n || typeof n !== 'object' || depth > MAX_DEPTH) return;
    if (Array.isArray(n)) return n.forEach(visit);
    if (n.ast && n.ast.type === 'select') {
      // Scalar subquery: its first output column is the value.
      const first = expandOutputs(n.ast, scope, scope.ctes, depth + 1).find((o) => o.lineage);
      if (first) {
        out.transforms.add('SUBQUERY');
        mergeInto(out, first.lineage);
      }
      return;
    }
    switch (n.type) {
      case 'column_ref':
        mergeInto(out, resolveColumn(n, scope, depth));
        return;
      case 'aggr_func': {
        const name = String(n.name).toUpperCase();
        if (NON_REVEALING_FUNCTIONS.has(name)) return;
        out.transforms.add(name);
        visit(n.args && n.args.expr);
        return;
      }
      case 'function': {
        const name = functionName(n);
        if (NON_REVEALING_FUNCTIONS.has(name)) return;
        out.transforms.add(name);
        visit(n.args);
        return;
      }
      case 'binary_expr': {
        const op = String(n.operator).toUpperCase();
        if (NON_REVEALING_OPERATORS.has(op)) return;
        out.transforms.add(op);
        visit(n.left);
        visit(n.right);
        return;
      }
      case 'case':
        // Only the THEN/ELSE results reach the output; WHEN conditions do not.
        out.transforms.add('CASE');
        for (const arm of n.args || []) visit(arm.result);
        return;
      case 'cast':
        out.transforms.add('CAST');
        visit(n.expr);
        return;
      default:
        for (const v of Object.values(n)) visit(v);
    }
  };
  visit(node);
  return out;
}

/**
 * Line traced outputs up with the actual result columns. A `*` over a base
 * table spans as many result columns as come from that table — capped so the
 * explicit columns after it still get their own result column.
 */
function alignOutputs(outputs, columns) {
  const aligned = new Array(columns.length).fill(null);
  if (!outputs) return aligned;
  let i = 0;
  for (let k = 0; k < outputs.length && i < columns.length; k++) {
    const item = outputs[k];
    if (!item.star) {
      aligned[i++] = { sources: [...item.lineage.sources], transforms: [...item.lineage.transforms] };
      continue;
    }
    const explicitAfter = outputs.slice(k + 1).filter((o) => !o.star).length;
    const maxWidth = columns.length - i - explicitAfter;
    let width = 0;
    while (width < maxWidth && lower(columns[i + width].sourceTable || '') === item.star) width++;
    for (let w = 0; w < width; w++, i++) {
      aligned[i] = { sources: [`${item.star}.${lower(columns[i].sourceColumn || columns[i].name)}`], transforms: [] };
    }
  }
  return aligned;
}

/** Output-column lineage for a SELECT, aligned to the result's columns. */
function traceColumns(sql, columns) {
  let outputs = null;
  try {
    outputs = expandOutputs(parse(sql).ast, null, new Map(), 0);
  } catch (e) {
    outputs = null; // fall back to MySQL metadata + value evidence
  }
  return alignOutputs(outputs, columns);
}

function normalizeSchema(piiSchema) {
  const map = new Map();
  for (const [table, cols] of Object.entries(piiSchema || {})) {
    for (const [col, type] of Object.entries(cols)) map.set(`${lower(table)}.${lower(col)}`, type);
  }
  return map;
}

function typeFromName(name) {
  for (const [re, type] of NAME_HEURISTICS) if (re.test(name)) return type;
  return null;
}

/**
 * Classify every column of a query result.
 *
 *   result     { columns: [{ name, sourceTable, sourceColumn }], rows: [[...]] }
 *   sql        the query that produced it (for lineage)
 *   piiSchema  { table: { column: PII_TYPE } } — the declared tags
 *
 * Returns one entry per column:
 *   { name, piiType, sourceTypes, method, confidence, sources, transforms, evidence }
 * piiType is null for non-PII, a PII type, 'MIXED' when several tagged
 * sources feed one column, or 'CONTAINS_PII' when only some cells hold PII
 * inside longer text (mask() then masks those spans cell by cell).
 */
function classifyColumns(result, { sql, piiSchema = {}, sampleSize = 50, sampleThreshold = 0.6 } = {}) {
  const tags = normalizeSchema(piiSchema);
  const lineages = traceColumns(sql, result.columns);

  return result.columns.map((col, i) => {
    const lineage = lineages[i] || {
      // No AST trace: trust MySQL's metadata for this column.
      sources: col.sourceTable ? [`${lower(col.sourceTable)}.${lower(col.sourceColumn || col.name)}`] : [],
      transforms: [],
    };

    let piiType = null;
    let method = null;
    let confidence = null;

    const tagged = [...new Set(lineage.sources.map((s) => tags.get(s)).filter(Boolean))];
    if (tagged.length) {
      piiType = tagged.length === 1 ? tagged[0] : 'MIXED';
      method = lineage.transforms.length ? 'lineage' : 'schema-tag';
      confidence = 'high';
    } else {
      const names = [...lineage.sources.map((s) => s.split('.')[1]), col.name];
      const guessed = names.map(typeFromName).find(Boolean);
      if (guessed) {
        piiType = guessed;
        method = 'column-name';
        confidence = 'medium';
      }
    }

    // Value evidence: always gathered, and decisive when nothing above matched.
    const values = [];
    for (const row of result.rows) {
      const v = row[i];
      if (v !== null && v !== undefined && String(v).trim() !== '') values.push(v);
      if (values.length >= sampleSize) break;
    }
    const counts = {};
    let containing = 0;
    for (const v of values) {
      const t = detectValue(v);
      if (t) counts[t] = (counts[t] || 0) + 1;
      else if (typeof v === 'string' && detectInText(v).length) containing++;
    }
    const [bestType, bestCount] = Object.entries(counts).sort((a, b) => b[1] - a[1])[0] || [null, 0];
    const evidence = values.length ? { sampled: values.length, matched: bestCount, type: bestType } : null;

    if (!piiType && values.length) {
      if (bestCount / values.length >= sampleThreshold) {
        piiType = bestType;
        method = 'value-sample';
        confidence = bestCount === values.length ? 'high' : 'medium';
      } else if (bestCount + containing > 0) {
        piiType = 'CONTAINS_PII';
        method = 'value-scan';
        confidence = 'medium';
      }
    }

    return {
      name: col.name,
      piiType,
      sourceTypes: tagged, // every declared type feeding the column (several when MIXED)
      method,
      confidence,
      sources: lineage.sources,
      transforms: lineage.transforms,
      evidence,
    };
  });
}

module.exports = { classifyColumns, traceColumns, NAME_HEURISTICS, NON_REVEALING_FUNCTIONS };
