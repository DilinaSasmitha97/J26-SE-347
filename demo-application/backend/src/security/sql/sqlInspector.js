const DEFAULT_SQLGLOT_URL = 'http://127.0.0.1:8001/inspect';

class SqlInspectionError extends Error {
  constructor(message, { code = 'SQL_INSPECTION_ERROR', status = 502 } = {}) {
    super(message);
    this.name = 'SqlInspectionError';
    this.code = code;
    this.status = status;
  }
}

async function inspectSql(sql, dialect = 'mysql') {
  const serviceUrl = process.env.SQLGLOT_SERVICE_URL || DEFAULT_SQLGLOT_URL;
  let response;

  try {
    response = await fetch(serviceUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql, dialect }),
      signal: AbortSignal.timeout(5000)
    });
  } catch {
    throw new SqlInspectionError(
      'The SQLGlot inspection service is unavailable.',
      { code: 'SQLGLOT_UNAVAILABLE', status: 502 }
    );
  }

  const payload = await response.json().catch(() => ({}));

  if (!response.ok || !payload.success || !payload.analysis) {
    const message = payload.detail?.message
      || payload.detail?.detail?.message
      || 'SQLGlot could not parse the submitted query.';
    throw new SqlInspectionError(message, {
      code: 'SQL_PARSE_FAILED',
      status: response.status >= 400 && response.status < 500 ? 400 : 502
    });
  }

  return payload.analysis;
}

module.exports = { inspectSql, SqlInspectionError };
