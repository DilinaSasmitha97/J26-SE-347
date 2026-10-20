const mysql = require('mysql2/promise');
const path = require('path');
const {
  validate,
  createQueryExecutor,
  classifyColumns,
  createNerClient,
  applyNer,
  mask,
  createPiiFpe,
  loadBundledConfig
} = require('security-validation-layer');

const DEFAULT_NL_SERVICE_URL = 'http://127.0.0.1:8000/api/v1/translate';
const DEFAULT_DATABASE = 'multi_tenant_hr';

const schemaAllowlists = loadBundledConfig('schema_allowlist.json');
const piiSchemas = loadBundledConfig('pii_columns.json');
const maskingPolicy = loadBundledConfig('masking_policy.json');

let sharedPool = null;

class SecureQueryError extends Error {
  constructor(code, message, status = 500, details = null) {
    super(message);
    this.name = 'SecureQueryError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

function databaseName() {
  return process.env.MYSQL_DATABASE || process.env.DB_NAME || DEFAULT_DATABASE;
}

function normalize(value) {
  return String(value || '').trim().toLowerCase();
}

function buildPolicyAllowlist(policy, dbName = databaseName()) {
  const schema = schemaAllowlists[dbName];
  if (!schema) {
    throw new SecureQueryError(
      'SCHEMA_ALLOWLIST_MISSING',
      `No schema allowlist is configured for database "${dbName}".`,
      500
    );
  }

  const denied = new Set((policy.deniedColumns || []).map(normalize));
  const result = {};
  for (const requestedTable of policy.allowedTables || []) {
    const table = normalize(requestedTable);
    const columns = schema[table];
    if (!Array.isArray(columns)) continue;
    result[table] = columns.filter((column) => !denied.has(`${table}.${normalize(column)}`));
  }
  return result;
}

function serializeValidation(result) {
  return {
    safe: result.safe,
    statementType: result.statementType,
    violations: result.violations.map((item) => ({ type: item.type, detail: item.detail }))
  };
}

function validateWithSecurityLayer(sql) {
  return serializeValidation(validate(sql, false));
}

function policyToInjectedRules(policy) {
  const lines = [
    `Only use these tables: ${(policy.allowedTables || []).join(', ')}.`,
    'Generate exactly one read-only SELECT statement.'
  ];

  if ((policy.deniedColumns || []).length) {
    lines.push(`Never select these columns: ${policy.deniedColumns.join(', ')}.`);
  }
  for (const rule of [...(policy.rowRules || []), ...(policy.requiredFilters || []), ...(policy.mandatoryFilters || [])]) {
    const column = rule.column || rule.field;
    const value = typeof rule.value === 'string' ? `'${rule.value.replaceAll("'", "''")}'` : rule.value;
    lines.push(`Required filter: ${rule.table}.${column} ${rule.operator || '='} ${value}.`);
  }
  return lines.join('\n');
}

async function translateQuestion(question, rules = null) {
  const url = process.env.NL_SERVICE_URL || DEFAULT_NL_SERVICE_URL;
  let response;
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_query: question,
        injected_rules: rules
      }),
      signal: AbortSignal.timeout(Number(process.env.NL_SERVICE_TIMEOUT_MS || 120000))
    });
  } catch (error) {
    throw new SecureQueryError(
      'NL_SERVICE_UNAVAILABLE',
      `The NL-to-SQL service is unavailable: ${error.message}`,
      502
    );
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.status !== 'SUCCESS' || !payload.predicted_sql) {
    throw new SecureQueryError(
      'SQL_GENERATION_FAILED',
      payload.detail?.detail || payload.message || 'The NL-to-SQL service did not return SQL.',
      response.status >= 400 && response.status < 500 ? 400 : 502,
      payload
    );
  }

  return {
    sql: payload.predicted_sql,
    metadata: payload.metadata || {},
    injectedRules: rules
  };
}

function getPool() {
  if (!sharedPool) {
    sharedPool = mysql.createPool({
      host: process.env.MYSQL_HOST || process.env.DB_HOST || '127.0.0.1',
      port: Number(process.env.MYSQL_PORT || process.env.DB_PORT || 3306),
      user: process.env.MYSQL_USER || process.env.DB_USER || 'root',
      password: process.env.MYSQL_PASSWORD || process.env.DB_PASSWORD || '',
      database: databaseName(),
      connectionLimit: Number(process.env.DB_CONNECTION_LIMIT || 5),
      dateStrings: true,
      enableKeepAlive: true
    });
  }
  return sharedPool;
}

function createFpe() {
  const key = process.env.FPE_KEY || '';
  return /^[0-9a-f]{64}$/i.test(key)
    ? createPiiFpe(key, { context: databaseName() })
    : null;
}

function sqliteFallbackEnabled() {
  return process.env.SQLITE_FALLBACK !== 'false';
}

function executeSqliteRead(sql) {
  const { DatabaseSync } = require('node:sqlite');
  const dbPath = process.env.SQLITE_DATABASE_PATH
    || path.resolve(__dirname, '..', '..', '..', 'shared-database', 'multitenant_hr.db');
  const maxRows = Number(process.env.QUERY_MAX_ROWS || 100);
  const started = process.hrtime.bigint();
  const database = new DatabaseSync(dbPath, { readOnly: true });
  try {
    const objectRows = database.prepare(sql).all();
    const names = objectRows.length ? Object.keys(objectRows[0]) : [];
    const elapsedMs = Number(process.hrtime.bigint() - started) / 1e6;
    return {
      statementType: 'SELECT',
      engine: 'sqlite',
      columns: names.map((name) => ({ name, sourceTable: null, sourceColumn: null })),
      rows: objectRows.slice(0, maxRows).map((row) => names.map((name) => row[name])),
      rowCount: objectRows.length,
      truncated: objectRows.length > maxRows,
      elapsedMs: Math.round(elapsedMs * 10) / 10
    };
  } finally {
    database.close();
  }
}

async function executeAndMask(sql, policy, user, options = {}) {
  // The gateway's policy stage authorizes table/column access before execution.
  // Recheck SQL safety here without repeating policy checks in the validator.
  const validation = validate(sql, false);
  if (!validation.safe) {
    throw new SecureQueryError(
      'SECURITY_LAYER_REJECTED',
      'Query failed security validation before execution.',
      403,
      { violations: serializeValidation(validation).violations }
    );
  }
  const executor = createQueryExecutor(options.pool || getPool(), {
    maxRows: Number(process.env.QUERY_MAX_ROWS || 100),
    timeoutMs: Number(process.env.QUERY_TIMEOUT_MS || 5000)
  });

  let result;
  const preferSqlite = process.env.DB_TYPE === 'sqlite';
  if (preferSqlite) {
    result = executeSqliteRead(sql);
  } else {
    try {
      result = await executor.run(sql);
      result.engine = 'mysql';
    } catch (error) {
      const connectionFailure = !error.status || [
        'ECONNREFUSED',
        'ETIMEDOUT',
        'ER_ACCESS_DENIED_ERROR',
        'ER_BAD_DB_ERROR'
      ].includes(error.code);
      if (sqliteFallbackEnabled() && connectionFailure && !options.pool) {
        result = executeSqliteRead(sql);
        result.fallbackReason = `MySQL unavailable: ${error.message}`;
      } else {
        throw new SecureQueryError(
          error.code || 'QUERY_EXECUTION_FAILED',
          error.message,
          error.status || 503,
          { violations: error.violations || [] }
        );
      }
    }
  }

  const piiSchema = piiSchemas[databaseName()] || {};
  const classification = classifyColumns(result, { sql, piiSchema });
  const nerClient = options.nerClient || createNerClient({
    url: process.env.NER_URL || 'http://127.0.0.1:5002',
    timeoutMs: Number(process.env.NER_TIMEOUT_MS || 5000)
  });
  const ner = await applyNer(result, classification, nerClient, {
    failMode: process.env.NER_FAIL_MODE === 'open' ? 'open' : 'closed'
  });
  const masked = mask(result, classification, {
    role: String(user.role || maskingPolicy.defaultRole).toUpperCase(),
    policy: maskingPolicy,
    fpe: createFpe()
  });

  return {
    ...masked,
    classification,
    ner
  };
}

async function getSecurityRuntimeHealth() {
  const ner = await createNerClient({
    url: process.env.NER_URL || 'http://127.0.0.1:5002',
    timeoutMs: 1500
  }).health();
  let database = { status: 'unavailable' };
  try {
    const connection = await getPool().getConnection();
    try {
      await connection.query('SELECT 1');
      database = { status: 'ok', database: databaseName() };
    } finally {
      connection.release();
    }
  } catch (error) {
    if (sqliteFallbackEnabled()) {
      try {
        const { DatabaseSync } = require('node:sqlite');
        const dbPath = process.env.SQLITE_DATABASE_PATH
          || path.resolve(__dirname, '..', '..', '..', 'shared-database', 'multitenant_hr.db');
        const sqlite = new DatabaseSync(dbPath, { readOnly: true });
        sqlite.prepare('SELECT 1').get();
        sqlite.close();
        database = {
          status: 'ok',
          database: DEFAULT_DATABASE,
          engine: 'sqlite-fallback',
          mysqlDetail: error.message
        };
      } catch (sqliteError) {
        database = {
          status: 'unavailable',
          database: databaseName(),
          detail: `${error.message}; SQLite fallback failed: ${sqliteError.message}`
        };
      }
    } else {
      database = { status: 'unavailable', database: databaseName(), detail: error.message };
    }
  }
  return { database, ner };
}

module.exports = {
  SecureQueryError,
  buildPolicyAllowlist,
  validateWithSecurityLayer,
  policyToInjectedRules,
  translateQuestion,
  executeAndMask,
  getSecurityRuntimeHealth
};
