import React, { useMemo, useState } from 'react';

const SAMPLE_POLICY = {
  policyId: 'finance-read-policy',
  version: '1.0',
  allowedOperations: ['SELECT'],
  allowedTables: ['employees', 'departments'],
  deniedColumns: ['employees.salary', 'employees.date_of_birth'],
  requiredFilters: [
    { table: 'employees', column: 'tenant_id', operator: '=', valueFrom: 'tenantId' },
    { table: 'employees', column: 'department_id', operator: '=', valueFrom: 'departmentId' }
  ]
};

const SAMPLE_USER = {
  userId: 'usr_84f2c',
  email: 'maya@acme.example',
  role: 'MANAGER',
  tenantId: 101,
  departmentId: 1
};

const SQL_EXAMPLES = {
  allowed: 'SELECT name, job_title\nFROM employees\nWHERE tenant_id = 101 AND department_id = 1;',
  blockedColumn: 'SELECT name, salary\nFROM employees\nWHERE tenant_id = 101 AND department_id = 1;',
  blockedTable: 'SELECT *\nFROM payroll_secrets\nWHERE tenant_id = 101;'
};

const formatJson = (value) => JSON.stringify(value, null, 2);

function parseJsonInput(label, source) {
  try {
    const value = JSON.parse(source);
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      throw new Error(`${label} must be a JSON object.`);
    }
    return value;
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error(`${label} contains invalid JSON: ${error.message}`);
    }
    throw error;
  }
}

export function Icon({ name, size = 18 }) {
  const paths = {
    shield: <path d="M12 3 5 6v5c0 4.6 2.9 7.7 7 9 4.1-1.3 7-4.4 7-9V6l-7-3Z" />,
    user: <><circle cx="12" cy="8" r="3" /><path d="M5.5 20c.7-3.8 2.9-6 6.5-6s5.8 2.2 6.5 6" /></>,
    code: <><path d="m8 9-3 3 3 3M16 9l3 3-3 3M14 5l-4 14" /></>,
    file: <><path d="M7 3h7l4 4v14H7z" /><path d="M14 3v5h4M10 12h5M10 16h5" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    close: <path d="m6 6 12 12M18 6 6 18" />,
    refresh: <><path d="M20 7v5h-5" /><path d="M19 12a7 7 0 1 0-2 5" /></>,
    bolt: <path d="m13 2-8 12h7l-1 8 8-12h-7l1-8Z" />
  };

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function JsonEditor({ number, icon, title, description, value, onChange, error }) {
  return (
    <section className={`input-card ${error ? 'has-error' : ''}`}>
      <div className="card-heading">
        <span className="step-number">{number}</span>
        <span className="card-icon"><Icon name={icon} /></span>
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
      </div>
      <textarea
        className="code-input json-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-label={title}
        spellCheck="false"
      />
      {error && <p className="field-error"><Icon name="close" size={15} /> {error}</p>}
    </section>
  );
}

function EmptyResult() {
  return (
    <div className="empty-result">
      <div className="empty-orbit">
        <span><Icon name="shield" size={32} /></span>
      </div>
      <h2>Ready to verify</h2>
      <p>Your decision and detailed policy checks will appear here.</p>
      <div className="empty-list">
        <span><Icon name="check" size={15} /> Statement type</span>
        <span><Icon name="check" size={15} /> Table &amp; column access</span>
        <span><Icon name="check" size={15} /> User-scoped filters</span>
      </div>
    </div>
  );
}

function ResultPanel({ result, loading }) {
  if (loading) {
    return (
      <div className="loading-result" aria-live="polite">
        <span className="spinner" />
        <h2>Inspecting query</h2>
        <p>SQLGlot is parsing the statement before policy evaluation.</p>
      </div>
    );
  }

  if (!result) return <EmptyResult />;

  if (result.kind === 'error') {
    return (
      <div className="error-result" role="alert">
        <span className="result-symbol"><Icon name="close" size={28} /></span>
        <span className="eyebrow">Verification error</span>
        <h2>Unable to complete the check</h2>
        <p>{result.message}</p>
        {result.hint && <div className="service-hint">{result.hint}</div>}
      </div>
    );
  }

  return (
    <div className={`decision-result ${result.passed ? 'is-pass' : 'is-fail'}`} aria-live="polite">
      <div className="decision-topline">
        <span className="result-symbol"><Icon name={result.passed ? 'check' : 'close'} size={28} /></span>
        <span className="eyebrow">Final decision</span>
      </div>
      <div className="decision-title-row">
        <h2>{result.decision}</h2>
        <span className="decision-pill">{result.passed ? 'Query approved' : 'Query blocked'}</span>
      </div>
      <p className="decision-message">{result.message}</p>

      <div className="check-list">
        {result.checks.map((check) => (
          <div className="check-item" key={check.label}>
            <span className={`check-mark ${check.passed ? 'pass' : 'fail'}`}>
              <Icon name={check.passed ? 'check' : 'close'} size={15} />
            </span>
            <div>
              <strong>{check.label}</strong>
              <p>{check.message}</p>
            </div>
            <span className={`mini-status ${check.passed ? 'pass' : 'fail'}`}>
              {check.passed ? 'Passed' : 'Failed'}
            </span>
          </div>
        ))}
      </div>

      <div className="inspection-summary">
        <div className="summary-heading">
          <span>Inspection summary</span>
          <span className="source-badge">SQLGlot</span>
        </div>
        <dl>
          <div><dt>User</dt><dd>{result.context.userId}</dd></div>
          <div><dt>Policy</dt><dd>{result.context.policyId}</dd></div>
          <div><dt>Tables</dt><dd>{result.context.tables.join(', ') || 'None'}</dd></div>
          <div><dt>Columns</dt><dd>{result.context.columns.join(', ') || 'None'}</dd></div>
        </dl>
      </div>
    </div>
  );
}

export default function App() {
  const [policyText, setPolicyText] = useState(formatJson(SAMPLE_POLICY));
  const [userText, setUserText] = useState(formatJson(SAMPLE_USER));
  const [sql, setSql] = useState(SQL_EXAMPLES.allowed);
  const [errors, setErrors] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const lineCount = useMemo(() => sql.split('\n').length, [sql]);

  const resetSample = () => {
    setPolicyText(formatJson(SAMPLE_POLICY));
    setUserText(formatJson(SAMPLE_USER));
    setSql(SQL_EXAMPLES.allowed);
    setErrors({});
    setResult(null);
  };

  const verify = async () => {
    const nextErrors = {};
    let policy;
    let user;

    try { policy = parseJsonInput('Policy', policyText); }
    catch (error) { nextErrors.policy = error.message; }

    try { user = parseJsonInput('Authenticated user', userText); }
    catch (error) { nextErrors.user = error.message; }

    if (!sql.trim()) nextErrors.sql = 'Enter a SQL query to verify.';
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) {
      setResult({ kind: 'error', message: 'Fix the highlighted input before running verification.' });
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch('/api/verify-sql', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ policy, user, sql, dialect: 'mysql' })
      });
      const payload = await response.json().catch(() => ({}));

      if (!response.ok) {
        const error = new Error(payload.message || 'The backend could not verify this query.');
        error.code = payload.code;
        throw error;
      }

      setResult(payload);
    } catch (error) {
      const networkError = error instanceof TypeError;
      setResult({
        kind: 'error',
        message: networkError ? 'The policy verification backend is not reachable.' : error.message,
        hint: networkError
          ? 'Start the backend on port 5000 and SQLGlot on port 8001, then try again.'
          : (error.code === 'SQLGLOT_UNAVAILABLE'
            ? 'Start the SQLGlot service on port 8001, then try again.'
            : 'Review the submitted values and try again.')
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><Icon name="shield" size={22} /></span>
          <div>
            <strong>PolicyGate</strong>
            <span>SQL verification console</span>
          </div>
        </div>
        <div className="topbar-actions">
          <span className="environment"><span /> Development</span>
          <a className="reset-button pl-link" href="#/pipeline"><Icon name="bolt" size={16} /> NL → SQL pipeline</a>
          <button className="reset-button" type="button" onClick={resetSample}>
            <Icon name="refresh" size={16} /> Reset sample
          </button>
        </div>
      </header>

      <main>
        <div className="page-heading">
          <div>
            <p className="kicker">Policy enforcement playground</p>
            <h1>Verify a SQL query</h1>
            <p>Inspect the query structure, then evaluate it against the authenticated user and access policy.</p>
          </div>
          <div className="pipeline" aria-label="Verification pipeline">
            <span className="active"><b>1</b> Inputs</span><i />
            <span><b>2</b> SQLGlot</span><i />
            <span><b>3</b> Policy check</span><i />
            <span><b>4</b> Decision</span>
          </div>
        </div>

        <div className="workspace">
          <div className="input-stack">
            <div className="json-grid">
              <JsonEditor number="01" icon="file" title="User policy" description="Tables, columns, operations and required filters" value={policyText}
                onChange={(value) => { setPolicyText(value); setErrors((current) => ({ ...current, policy: null })); }} error={errors.policy} />
              <JsonEditor number="02" icon="user" title="Authenticated user" description="Trusted identity claims supplied by authentication" value={userText}
                onChange={(value) => { setUserText(value); setErrors((current) => ({ ...current, user: null })); }} error={errors.user} />
            </div>

            <section className={`input-card sql-card ${errors.sql ? 'has-error' : ''}`}>
              <div className="card-heading sql-heading">
                <span className="step-number">03</span>
                <span className="card-icon"><Icon name="code" /></span>
                <div><h2>SQL query</h2><p>Sent to the backend for SQLGlot inspection and policy evaluation</p></div>
                <span className="line-count">{lineCount} {lineCount === 1 ? 'line' : 'lines'}</span>
              </div>
              <textarea className="code-input sql-input" value={sql}
                onChange={(event) => { setSql(event.target.value); setErrors((current) => ({ ...current, sql: null })); }}
                aria-label="SQL query" spellCheck="false" />
              {errors.sql && <p className="field-error"><Icon name="close" size={15} /> {errors.sql}</p>}
              <div className="sql-footer">
                <div className="examples" aria-label="SQL examples">
                  <span>Try an example:</span>
                  <button type="button" onClick={() => setSql(SQL_EXAMPLES.allowed)}>Allowed</button>
                  <button type="button" onClick={() => setSql(SQL_EXAMPLES.blockedColumn)}>Blocked column</button>
                  <button type="button" onClick={() => setSql(SQL_EXAMPLES.blockedTable)}>Blocked table</button>
                </div>
                <button className="verify-button" type="button" onClick={verify} disabled={loading}>
                  <Icon name="bolt" size={17} /> {loading ? 'Verifying…' : 'Verify query'}
                </button>
              </div>
            </section>
          </div>

          <aside className="result-panel">
            <div className="result-panel-header">
              <div><span className="step-number">04</span><h2>Verification result</h2></div>
              <span className="live-label"><i /> Live result</span>
            </div>
            <div className="result-panel-body"><ResultPanel result={result} loading={loading} /></div>
          </aside>
        </div>
      </main>

      <footer>
        <span><Icon name="shield" size={14} /> Queries are inspected only; they are never executed.</span>
        <span>SQLGlot → Table &amp; column checker → Decision</span>
      </footer>
    </div>
  );
}
