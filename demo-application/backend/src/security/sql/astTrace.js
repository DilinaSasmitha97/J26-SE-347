const {
  parse,
  getFunctions,
  getSystemVariables,
  getSystemSchemaRefs,
  getTableRefs,
  getLockingReads,
  getMaxLimit,
  getMaxSubqueryDepth,
  hasStackedStatements,
  hasSqlComment,
  hasUnion,
  isAlwaysTruePredicate,
  BLOCKED_FUNCTIONS,
  SYSTEM_SCHEMAS,
  MAX_LIMIT_ROWS,
  MAX_TABLE_REFERENCES,
  MAX_SUBQUERY_DEPTH
} = require('security-validation-layer');

// Explains the SQL safety (AST) check for the UI: the parsed tree and every
// rule the validator ran. Pass/fail always comes from the validator's own
// violations, so this view can never disagree with the real decision.

const MAX_TREE_NODES = 400;

// Validator rules in the order validate() runs them, keyed by violation type.
const STAGES = [
  { id: 'single_statement', label: 'Single statement', types: ['stacked_statements'], raw: true,
    description: 'Stacked queries (SELECT …; DROP …) are refused before parsing.' },
  { id: 'parse', label: 'Parse into an AST', types: ['parse_error'], raw: true,
    description: 'node-sql-parser builds the syntax tree using the MySQL grammar.' },
  { id: 'statement_type', label: 'Statement type', types: ['blocked_statement_type', 'write_not_authorized'],
    description: 'Only read-only SELECT is allowed; DDL and admin statements are always blocked.' },
  { id: 'functions', label: 'Dangerous functions', types: ['dangerous_function'],
    description: 'Every function call in the tree is checked against the blocklist (file access, sleep, fingerprinting).' },
  { id: 'system_variables', label: 'System variables', types: ['system_variable'],
    description: 'Server variables such as @@version expose configuration.' },
  { id: 'system_schemas', label: 'System schemas', types: ['system_schema_access'],
    description: `${[...SYSTEM_SCHEMAS].join(', ')} are never queryable.` },
  { id: 'tautology', label: 'Always-true predicates', types: ['tautology_predicate'],
    description: 'WHERE, HAVING and ON conditions are constant-folded to catch filters like OR 1=1.' },
  { id: 'locking', label: 'Locking reads', types: ['locking_read'],
    description: 'A read query must not take row locks (FOR UPDATE, LOCK IN SHARE MODE).' },
  { id: 'limit', label: 'Row limit', types: ['excessive_limit'],
    description: `A LIMIT above ${MAX_LIMIT_ROWS} rows is treated as a table dump.` },
  { id: 'table_count', label: 'Table references', types: ['too_many_tables'],
    description: `More than ${MAX_TABLE_REFERENCES} table references risks a cartesian blow-up.` },
  { id: 'unbounded_write', label: 'Unbounded writes', types: ['delete_without_where', 'update_without_where'],
    description: 'UPDATE or DELETE without WHERE would change every row.' },
  { id: 'union', label: 'UNION', types: ['union_query'],
    description: 'UNION can merge rows from an unrelated query.' },
  { id: 'comments', label: 'Comment markers', types: ['sql_comment_present'], raw: true,
    description: 'Comments (--, #, /* */) can hide part of the query; checked on raw text outside literals.' },
  { id: 'subquery_depth', label: 'Subquery depth', types: ['excessive_subquery_depth'],
    description: `Nesting deeper than ${MAX_SUBQUERY_DEPTH} levels is refused.` }
];

const list = (items, empty) => (items.length ? items.join(', ') : empty);

function observe(id, sql, ast, statementType) {
  switch (id) {
    case 'single_statement': return hasStackedStatements(sql) ? 'More than one statement found' : '1 statement';
    case 'parse': return ast ? 'Parsed successfully' : 'Parser rejected the text';
    case 'statement_type': return statementType;
    case 'functions': return list(getFunctions(ast), 'No function calls');
    case 'system_variables': return list(getSystemVariables(ast), 'None referenced');
    case 'system_schemas': {
      const refs = getSystemSchemaRefs(ast).map((r) => `${r.db}.${r.table}`);
      return list(refs, `None (tables: ${list([...new Set(getTableRefs(ast).map((r) => r.table))], 'none')})`);
    }
    case 'tautology': return `${countPredicates(ast)} predicate(s) evaluated`;
    case 'locking': return list(getLockingReads(ast), 'None');
    case 'limit': {
      const limit = getMaxLimit(ast);
      return limit === null ? 'No LIMIT' : `LIMIT ${limit} (max ${MAX_LIMIT_ROWS})`;
    }
    case 'table_count': return `${getTableRefs(ast).length} of max ${MAX_TABLE_REFERENCES}`;
    case 'unbounded_write': return ['UPDATE', 'DELETE'].includes(statementType) ? statementType : 'Not a write';
    case 'union': return hasUnion(ast) ? 'UNION present' : 'None';
    case 'comments': return hasSqlComment(sql) ? 'Comment marker found' : 'None';
    case 'subquery_depth': return `Depth ${getMaxSubqueryDepth(ast)} (max ${MAX_SUBQUERY_DEPTH})`;
    default: return '';
  }
}

function countPredicates(ast) {
  let count = 0;
  const visit = (node) => {
    if (!node || typeof node !== 'object') return;
    if (Array.isArray(node)) { node.forEach(visit); return; }
    for (const key of ['where', 'having', 'on']) if (node[key] && typeof node[key] === 'object') count += 1;
    Object.values(node).forEach(visit);
  };
  visit(ast);
  return count;
}

// ---- Tree ------------------------------------------------------------------

function createTreeBuilder() {
  let count = 0;
  const node = (kind, label, children = [], extra = {}) => {
    count += 1;
    return { kind, label, children: children.filter(Boolean), ...extra };
  };
  const full = () => count >= MAX_TREE_NODES;

  const functionName = (e) => {
    const parts = Array.isArray(e.name?.name) ? e.name.name : [e.name];
    const called = parts.map((p) => (p && p.value !== undefined ? p.value : p)).filter(Boolean);
    return String(called[called.length - 1] || 'function').toUpperCase();
  };

  function expr(e) {
    if (e === null || e === undefined) return null;
    if (full()) return node('more', '…');
    if (typeof e !== 'object') return node('literal', String(e));
    if (e.ast) return node('subquery', 'Subquery', [statement(e.ast)]);
    switch (e.type) {
      case 'column_ref': {
        const col = typeof e.column === 'string' ? e.column : e.column?.expr?.value;
        return node('column', `${e.table ? `${e.table}.` : ''}${col}`);
      }
      case 'star': return node('column', '*');
      case 'number': return node('literal', String(e.value));
      case 'bool': return node('literal', e.value ? 'TRUE' : 'FALSE');
      case 'null': return node('literal', 'NULL');
      case 'single_quote_string': case 'double_quote_string': case 'string': case 'natural_string':
        return node('literal', `'${e.value}'`);
      case 'param': return node('literal', `:${e.value}`);
      case 'var':
        return node('variable', `${e.prefix || '@'}${e.name}`, [], e.prefix === '@@' ? { flagged: 'System variable' } : {});
      case 'binary_expr':
        return node('operator', String(e.operator).toUpperCase(), [expr(e.left), expr(e.right)]);
      case 'unary_expr':
        return node('operator', String(e.operator).toUpperCase(), [expr(e.expr)]);
      case 'expr_list':
        return node('list', 'List', (e.value || []).map(expr));
      case 'aggr_func': {
        const arg = e.args?.expr;
        const label = `${String(e.name).toUpperCase()}(${e.args?.distinct ? 'DISTINCT' : ''})`;
        return node('function', label, [expr(arg)]);
      }
      case 'function': {
        const name = functionName(e);
        const blocked = Object.prototype.hasOwnProperty.call(BLOCKED_FUNCTIONS, name);
        return node('function', `${name}()`, (e.args?.value || []).map(expr), blocked ? { flagged: BLOCKED_FUNCTIONS[name] } : {});
      }
      case 'case':
        return node('operator', 'CASE', (e.args || []).map((arm) => (arm.type === 'when'
          ? node('clause', 'WHEN', [expr(arm.cond), node('clause', 'THEN', [expr(arm.result)])])
          : node('clause', 'ELSE', [expr(arm.result)]))));
      case 'cast':
        return node('function', `CAST(AS ${String(e.target?.[0]?.dataType || e.target?.dataType || '').toUpperCase()})`, [expr(e.expr)]);
      default: {
        const children = Object.values(e).filter((v) => v && typeof v === 'object' && (v.type || v.ast)).map(expr);
        return node('node', String(e.type || 'expression').toUpperCase(), children);
      }
    }
  }

  function predicate(label, value) {
    if (!value || typeof value !== 'object') return null;
    return node('clause', label, [expr(value)],
      isAlwaysTruePredicate(value) ? { flagged: 'Always-true condition' } : {});
  }

  function source(t) {
    if (t.expr?.ast) {
      return node('subquery', `${t.join ? `${t.join} ` : ''}Derived table${t.as ? ` ${t.as}` : ''}`,
        [statement(t.expr.ast), predicate('ON', t.on)]);
    }
    const name = `${t.db ? `${t.db}.` : ''}${t.table}${t.as ? ` ${t.as}` : ''}`;
    const system = t.db && SYSTEM_SCHEMAS.has(String(t.db).toLowerCase());
    return node('table', `${t.join ? `${t.join} ` : ''}${name}`, [predicate('ON', t.on)],
      system ? { flagged: 'MySQL system schema' } : {});
  }

  function statement(ast) {
    if (!ast || typeof ast !== 'object') return null;
    const type = String(ast.type || 'statement').toUpperCase();
    if (type !== 'SELECT') {
      return node('statement', type, getTableRefs(ast).map((r) => node('table', `${r.db ? `${r.db}.` : ''}${r.table}`)));
    }
    const children = [];
    if (Array.isArray(ast.with) && ast.with.length) {
      children.push(node('clause', 'WITH', ast.with.map((cte) => {
        const name = cte.name?.value ?? cte.name;
        return node('subquery', `CTE ${name}`, [statement(cte.stmt?.ast || cte.stmt)]);
      })));
    }
    const columns = Array.isArray(ast.columns) ? ast.columns : [{ expr: { type: 'star' } }];
    children.push(node('clause', ast.distinct ? 'SELECT DISTINCT' : 'SELECT list', columns.map((c) => (c.as
      ? node('alias', `AS ${c.as}`, [expr(c.expr)])
      : expr(c.expr)))));
    if (Array.isArray(ast.from) && ast.from.length) children.push(node('clause', 'FROM', ast.from.map(source)));
    children.push(predicate('WHERE', ast.where));
    const groupBy = Array.isArray(ast.groupby) ? ast.groupby : ast.groupby?.columns;
    if (Array.isArray(groupBy) && groupBy.length) children.push(node('clause', 'GROUP BY', groupBy.map(expr)));
    children.push(predicate('HAVING', ast.having));
    if (Array.isArray(ast.orderby) && ast.orderby.length) {
      children.push(node('clause', 'ORDER BY', ast.orderby.map((o) => node('alias', o.type || 'ASC', [expr(o.expr)]))));
    }
    const limit = getMaxLimit({ limit: ast.limit });
    if (Array.isArray(ast.limit?.value) && ast.limit.value.length) {
      children.push(node('clause', `LIMIT ${ast.limit.value.map((v) => v.value).join(ast.limit.seperator === ',' ? ', ' : ' OFFSET ')}`, [],
        limit !== null && limit > MAX_LIMIT_ROWS ? { flagged: `Above ${MAX_LIMIT_ROWS} rows` } : {}));
    }
    if (ast.locking_read) children.push(node('clause', String(ast.locking_read).toUpperCase(), [], { flagged: 'Locking read' }));
    if (ast._next) {
      children.push(node('clause', String(ast.set_op || 'UNION').toUpperCase(), [statement(ast._next)], { flagged: 'UNION query' }));
    }
    return node('statement', 'SELECT', children);
  }

  return { statement, truncated: () => full() };
}

/**
 * Builds the UI explanation for one validateWithSecurityLayer() result.
 * `validation` is the serialized { safe, statementType, violations } object.
 */
function traceSqlSafety(sql, validation) {
  let ast = null;
  let parseError = null;
  try {
    ({ ast } = parse(sql));
  } catch (error) {
    parseError = error.message;
  }

  const violations = validation?.violations || [];
  const statementType = validation?.statementType || 'UNKNOWN';
  const stages = STAGES.map((stage) => {
    const found = violations.filter((v) => stage.types.includes(v.type)).map((v) => v.detail || v.type);
    const evaluated = Boolean(ast) || stage.raw;
    let observed = '';
    try {
      observed = evaluated ? observe(stage.id, sql, ast, statementType) : 'Not evaluated (no AST)';
    } catch {
      observed = '';
    }
    if (stage.id === 'parse' && parseError) observed = parseError;
    return {
      id: stage.id,
      label: stage.label,
      description: stage.description,
      status: found.length ? 'fail' : evaluated ? 'pass' : 'skipped',
      observed,
      violations: found
    };
  });
  const known = new Set(STAGES.flatMap((stage) => stage.types));
  const other = violations.filter((v) => !known.has(v.type));
  if (other.length) {
    stages.push({ id: 'other', label: 'Other rules', description: 'Additional validator findings.', status: 'fail',
      observed: '', violations: other.map((v) => `${v.type}: ${v.detail}`) });
  }

  const builder = createTreeBuilder();
  return {
    sql,
    safe: Boolean(validation?.safe),
    statementType,
    parser: 'node-sql-parser (MySQL)',
    parseError,
    tree: ast ? builder.statement(ast) : null,
    truncated: ast ? builder.truncated() : false,
    stages
  };
}

module.exports = { traceSqlSafety };
