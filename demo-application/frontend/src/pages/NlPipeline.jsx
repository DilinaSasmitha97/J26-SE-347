import React, { useEffect, useRef, useState } from 'react';
import { Icon } from '../App.jsx';

// Requests go through the Vite dev proxy (vite.config.js), so the browser
// never talks to the Python services directly and needs no CORS setup.
const NL_TRANSLATE_URL = '/nl-api/api/v1/translate';
const SQLGLOT_INSPECT_URL = '/sqlglot-api/inspect';
const VERIFY_URL = '/api/verify-sql';

const MAX_FILE_BYTES = 256 * 1024; // matches the backend's JSON body limit
const MAX_QUESTION_CHARS = 2000;
const NL_TIMEOUT_MS = 120000; // LLM calls with self-refinement can be slow
const SERVICE_TIMEOUT_MS = 30000;
const KNOWN_STATEMENTS = ['SELECT', 'INSERT', 'UPDATE', 'DELETE'];

const SAMPLE_QUESTION = 'Show the first name, last name and work email of employees in the IT department';

const SAMPLE_POLICY = {
  policyId: 'policy-manager-hr-read',
  version: '1.0',
  role: 'MANAGER',
  allowedOperations: ['SELECT'],
  allowedTables: ['employees', 'departments'],
  deniedColumns: ['employees.nic_number', 'employees.passport_number', 'employees.personal_email'],
  requiredFilters: [
    { table: 'employees', column: 'tenant_id', operator: '=', valueFrom: 'tenantId' }
  ]
};

const SAMPLE_USER = {
  userId: 'user-101-manager',
  name: 'Manager A',
  role: 'MANAGER',
  tenantId: 101,
  departmentId: 1
};

const SAMPLE_RULES = {
  constraints: [
    'STRICT CONSTRAINT: Filter all results by employees.tenant_id = 101.',
    'Only use the tables employees and departments.',
    'Never select nic_number, passport_number or personal_email.'
  ]
};

const pretty = (value) => JSON.stringify(value, null, 2);

function parseObject(label, text) {
  if (!text.trim()) return { error: `${label} is empty. Paste JSON or upload a .json file.` };
  try {
    const value = JSON.parse(text);
    if (!value || Array.isArray(value) || typeof value !== 'object') {
      return { error: `${label} must be a JSON object ({ … }), not ${Array.isArray(value) ? 'an array' : typeof value}.` };
    }
    return { value };
  } catch (error) {
    return { error: `${label} is not valid JSON: ${error.message}` };
  }
}

/**
 * The translate API takes injected_rules as plain text. A rules file may give
 * that text directly, a list of constraint lines, or any other JSON object
 * (sent as formatted JSON so the LLM still sees every field).
 */
function rulesToText(rules) {
  if (typeof rules.injected_rules === 'string') return rules.injected_rules;
  if (Array.isArray(rules.constraints)) return rules.constraints.map(String).join('\n');
  return pretty(rules);
}

async function postJson(url, body, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const started = performance.now();
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal
    });
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { /* non-JSON body */ }
    return { ok: response.ok, status: response.status, data, ms: Math.round(performance.now() - started) };
  } catch (error) {
    return {
      ok: false, status: 0, data: null, network: true,
      aborted: error.name === 'AbortError', ms: Math.round(performance.now() - started)
    };
  } finally {
    clearTimeout(timer);
  }
}

// SQLGlot underlines the bad token with terminal colour codes; they render as junk in HTML.
const stripAnsi = (text) => String(text).replace(/\u001b\[[0-9;]*m/g, '');

/** Normalises the three error shapes: FastAPI detail object/list, and the backend's { code, message }. */
function describeError(result, timeoutMs) {
  return stripAnsi(rawError(result, timeoutMs));
}

function rawError(result, timeoutMs) {
  if (result.aborted) return `No response within ${Math.round(timeoutMs / 1000)} s (request cancelled).`;
  if (result.network) return 'Network error: the dev server could not be reached.';
  const data = result.data;
  if (!data) return `Service unreachable or returned a non-JSON response (HTTP ${result.status}).`;
  if (Array.isArray(data.detail)) {
    return data.detail.map((item) => `${(item.loc || []).join('.')}: ${item.msg}`).join('; ');
  }
  if (data.detail && typeof data.detail === 'object') {
    return [data.detail.error_code || data.detail.code, data.detail.detail || data.detail.message].filter(Boolean).join(': ');
  }
  if (typeof data.detail === 'string') return data.detail;
  return [data.code, data.message].filter(Boolean).join(': ') || `HTTP ${result.status}`;
}

/**
 * SQLGlot leaves table = null for unqualified columns (`SELECT nic_number FROM
 * employees`). Like the backend's checkers, attribute them to the only table
 * when the query uses exactly one.
 */
function qualify(item, analysis) {
  if (item.table) return item.table;
  return analysis.tables.length === 1 ? analysis.tables[0].name : '?';
}

const timeStamp = () => {
  const d = new Date();
  return `${d.toLocaleTimeString([], { hour12: false })}.${String(d.getMilliseconds()).padStart(3, '0')}`;
};

// ---------------------------------------------------------------------------

function StatusPill({ state }) {
  const labels = { idle: 'Waiting', loading: 'Running', pass: 'Pass', fail: 'Fail', invalid: 'Fail', error: 'Error', done: 'Done' };
  return <span className={`pl-pill pl-pill-${state === 'invalid' ? 'fail' : state}`}>{state === 'loading' && <i className="pl-dot-spin" />}{labels[state]}</span>;
}

function JsonUpload({ number, icon, title, description, text, onText, fileName, onFileName, log }) {
  const input = useRef(null);
  const parsed = parseObject(title, text);

  const readFile = (file) => {
    if (!file) return;
    if (!/\.json$/i.test(file.name) && file.type !== 'application/json') {
      log('INPUT', 'error', `${title}: "${file.name}" is not a .json file. Upload rejected.`);
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      log('INPUT', 'error', `${title}: "${file.name}" is ${(file.size / 1024).toFixed(0)} KB; the limit is ${MAX_FILE_BYTES / 1024} KB.`);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const content = String(reader.result);
      onText(content);
      onFileName(file.name);
      const check = parseObject(title, content);
      log('INPUT', check.error ? 'error' : 'success',
        check.error ? `${title}: uploaded "${file.name}" but ${check.error}` : `${title}: loaded "${file.name}" (${file.size} bytes, ${Object.keys(check.value).length} top-level keys).`);
    };
    reader.onerror = () => log('INPUT', 'error', `${title}: could not read "${file.name}".`);
    reader.readAsText(file);
  };

  return (
    <section className={`input-card pl-json-card ${parsed.error ? 'has-error' : ''}`}>
      <div className="card-heading">
        <span className="step-number">{number}</span>
        <span className="card-icon"><Icon name={icon} /></span>
        <div><h2>{title}</h2><p>{description}</p></div>
      </div>
      <div className="pl-upload-row">
        <button type="button" className="pl-ghost" onClick={() => input.current?.click()}>
          <Icon name="file" size={15} /> Upload .json
        </button>
        <span className="pl-file-name">{fileName || 'sample (edit or upload)'}</span>
        <input ref={input} type="file" accept=".json,application/json" hidden
          onChange={(event) => { readFile(event.target.files[0]); event.target.value = ''; }} />
      </div>
      <textarea className="code-input pl-json-input" value={text} spellCheck="false" aria-label={title}
        onChange={(event) => { onText(event.target.value); onFileName(fileName ? `${fileName} (edited)` : ''); }} />
      {parsed.error
        ? <p className="field-error"><Icon name="close" size={15} /> {parsed.error}</p>
        : <p className="pl-field-ok"><Icon name="check" size={15} /> Valid JSON · {Object.keys(parsed.value).length} keys</p>}
    </section>
  );
}

function Stepper({ steps }) {
  return (
    <div className="pipeline pl-stepper" aria-label="Pipeline progress">
      {steps.map((step, i) => (
        <React.Fragment key={step.label}>
          {i > 0 && <i />}
          <span className={`pl-step-${step.state}`}><b>{step.state === 'pass' ? '✓' : step.state === 'fail' ? '✕' : i + 1}</b> {step.label}</span>
        </React.Fragment>
      ))}
    </div>
  );
}

function InspectionCard({ inspect, policy }) {
  if (!inspect) return null;
  if (inspect.error) {
    return (
      <div className="pl-result-card is-fail">
        <div className="pl-result-head"><h3>SQLGlot inspection</h3><StatusPill state="error" /></div>
        <p className="pl-error-text">{inspect.error}</p>
      </div>
    );
  }
  const a = inspect.analysis;
  const allowed = new Set((policy?.allowedTables || []).map((t) => String(t).toLowerCase()));
  const denied = new Set((policy?.deniedColumns || []).map((c) => String(c).toLowerCase()));
  const parsedOk = KNOWN_STATEMENTS.includes(a.statementType);

  return (
    <div className={`pl-result-card ${parsedOk ? '' : 'is-fail'}`}>
      <div className="pl-result-head">
        <h3>SQLGlot inspection <small>{inspect.ms} ms</small></h3>
        <StatusPill state={parsedOk ? 'done' : 'fail'} />
      </div>
      <dl className="pl-facts">
        <div><dt>Statement</dt><dd>{a.statementType}</dd></div>
        <div><dt>Normalised SQL</dt><dd className="pl-mono">{a.normalizedSql}</dd></div>
        <div><dt>Tables</dt><dd>{a.tables.length ? a.tables.map((t) => (
          <span key={t.name + t.alias} className={`pl-chip ${allowed.has(String(t.name).toLowerCase()) ? 'ok' : 'bad'}`}
            title={allowed.has(String(t.name).toLowerCase()) ? 'Allowed by policy' : 'Not in policy allowedTables'}>
            {t.name}{t.alias ? ` AS ${t.alias}` : ''}
          </span>)) : '—'}</dd></div>
        <div><dt>Columns</dt><dd>{a.columns.length ? a.columns.map((c, i) => {
          const name = `${qualify(c, a)}.${c.column}`;
          return <span key={name + i} className={`pl-chip ${denied.has(name.toLowerCase()) ? 'bad' : ''}`}
            title={denied.has(name.toLowerCase()) ? 'Denied by policy' : ''}>{name}</span>;
        }) : '—'}</dd></div>
        <div><dt>Filters</dt><dd>{a.filters.length ? a.filters.map((f, i) => (
          <span key={i} className={`pl-chip ${f.column === 'tenant_id' ? 'ok' : ''}`}>
            {qualify(f, a)}.{f.column} {f.operator} {String(f.value)}
          </span>)) : '—'}</dd></div>
        <div><dt>Joins</dt><dd>{a.joins.length ? a.joins.map((j, i) => (
          <span key={i} className="pl-chip">{j.type} JOIN {j.table}</span>)) : '—'}</dd></div>
      </dl>
    </div>
  );
}

function DecisionCard({ verify }) {
  if (!verify) return null;
  if (verify.error) {
    return (
      <div className="pl-result-card is-fail">
        <div className="pl-result-head"><h3>Security backend decision</h3><StatusPill state="error" /></div>
        <p className="pl-error-text">{verify.error}</p>
        {verify.hint && <div className="service-hint">{verify.hint}</div>}
      </div>
    );
  }
  const r = verify.result;
  return (
    <div className={`decision-result pl-result-card ${r.passed ? 'is-pass' : 'is-fail'}`} aria-live="polite">
      <div className="decision-topline">
        <span className="result-symbol"><Icon name={r.passed ? 'check' : 'close'} size={26} /></span>
        <span className="eyebrow">Security backend decision · {verify.ms} ms</span>
      </div>
      <div className="decision-title-row">
        <h2>{r.decision}</h2>
        <span className="decision-pill">{r.passed ? 'Query approved' : 'Query blocked'}</span>
      </div>
      <p className="decision-message">{r.message}</p>
      <div className="check-list">
        {r.checks.map((check) => (
          <div className="check-item" key={check.label}>
            <span className={`check-mark ${check.passed ? 'pass' : 'fail'}`}><Icon name={check.passed ? 'check' : 'close'} size={15} /></span>
            <div>
              <strong>{check.label}</strong>
              <p>{check.message}</p>
              {check.reason && <p className="pl-mono pl-reason">{check.reason}</p>}
            </div>
            <span className={`mini-status ${check.passed ? 'pass' : 'fail'}`}>{check.passed ? 'Passed' : 'Failed'}</span>
          </div>
        ))}
      </div>
      <div className="inspection-summary">
        <div className="summary-heading"><span>Evaluated context</span><span className="source-badge">backend</span></div>
        <dl>
          <div><dt>User</dt><dd>{r.context.userId} ({r.context.role})</dd></div>
          <div><dt>Policy</dt><dd>{r.context.policyId}</dd></div>
          <div><dt>Tables</dt><dd>{r.context.tables.join(', ') || 'None'}</dd></div>
          <div><dt>Columns</dt><dd>{r.context.columns.join(', ') || 'None'}</dd></div>
        </dl>
      </div>
    </div>
  );
}

function ActivityLog({ entries, onClear }) {
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }); }, [entries.length]);
  return (
    <aside className="result-panel pl-log-panel">
      <div className="result-panel-header">
        <div><h2>Activity &amp; security log</h2></div>
        <button type="button" className="pl-ghost" onClick={onClear} disabled={!entries.length}>Clear</button>
      </div>
      <div className="pl-log-body">
        {!entries.length && <p className="pl-log-empty">Background steps, security messages, errors and pass/fail results appear here as the pipeline runs.</p>}
        {entries.map((entry) => (
          <div key={entry.id} className={`pl-log-entry pl-log-${entry.level}`}>
            <span className="pl-log-time">{entry.time}</span>
            <span className="pl-log-stage">{entry.stage}</span>
            <div className="pl-log-text">
              {entry.message}
              {entry.detail && (
                <details><summary>details</summary><pre>{typeof entry.detail === 'string' ? entry.detail : pretty(entry.detail)}</pre></details>
              )}
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------

export default function NlPipeline() {
  const [question, setQuestion] = useState(SAMPLE_QUESTION);
  const [policyText, setPolicyText] = useState(pretty(SAMPLE_POLICY));
  const [userText, setUserText] = useState(pretty(SAMPLE_USER));
  const [rulesText, setRulesText] = useState(pretty(SAMPLE_RULES));
  const [files, setFiles] = useState({ policy: '', user: '', rules: '' });

  const [genState, setGenState] = useState('idle');
  const [genError, setGenError] = useState(null);
  const [generated, setGenerated] = useState(null); // { sql, metadata, ms }
  const [sql, setSql] = useState('');

  const [verifyState, setVerifyState] = useState('idle');
  const [inspect, setInspect] = useState(null);
  const [verify, setVerify] = useState(null);
  const [verifiedPolicy, setVerifiedPolicy] = useState(null);

  const [logs, setLogs] = useState([]);
  const nextId = useRef(0);
  const step2Ref = useRef(null);
  const log = (stage, level, message, detail) =>
    setLogs((current) => [...current, { id: nextId.current++, time: timeStamp(), stage, level, message, detail }]);

  const setFile = (key) => (name) => setFiles((current) => ({ ...current, [key]: name }));

  const resetAll = () => {
    setQuestion(SAMPLE_QUESTION);
    setPolicyText(pretty(SAMPLE_POLICY));
    setUserText(pretty(SAMPLE_USER));
    setRulesText(pretty(SAMPLE_RULES));
    setFiles({ policy: '', user: '', rules: '' });
    setGenState('idle'); setGenError(null); setGenerated(null); setSql('');
    setVerifyState('idle'); setInspect(null); setVerify(null);
    setLogs([]);
  };

  // ---- Step 1: NL question + rules -> NL-to-SQL service -------------------
  const submit = async () => {
    setGenerated(null); setSql(''); setGenError(null);
    setVerifyState('idle'); setInspect(null); setVerify(null);
    log('STEP 1', 'info', 'Submit clicked. Validating the question and the three JSON inputs.');

    const q = question.trim();
    const policy = parseObject('User policy', policyText);
    const user = parseObject('Authenticated user', userText);
    const rules = parseObject('NL-to-SQL rules', rulesText);
    const problems = [
      !q && 'Natural language question is empty.',
      q.length > MAX_QUESTION_CHARS && `Question is ${q.length} characters; the limit is ${MAX_QUESTION_CHARS}.`,
      policy.error, user.error, rules.error,
      policy.value && !Array.isArray(policy.value.allowedTables) && 'User policy must include an "allowedTables" array.'
    ].filter(Boolean);
    if (problems.length) {
      problems.forEach((p) => log('STEP 1', 'error', p));
      setGenState('invalid');
      setGenError('Fix the inputs listed in the activity log, then submit again.');
      return;
    }

    const p = policy.value;
    const u = user.value;
    log('STEP 1', 'success', `Inputs valid. Policy "${p.policyId || 'unnamed'}": ${p.allowedTables.length} allowed table(s), ${(p.deniedColumns || []).length} denied column(s), ${(p.requiredFilters || p.rowRules || []).length} required filter(s).`, p);
    log('STEP 1', 'info', `Authenticated user ${u.userId || u.sub || '(no userId)'} · role ${u.role || '(none)'} · tenant ${u.tenantId ?? '(none)'}.`, u);
    log('SECURITY', 'warn', 'Identity claims come from an uploaded JSON file in this demo. In production they must come from a verified JWT, never from user input.');
    if (u.tenantId === undefined || u.tenantId === null) {
      log('SECURITY', 'warn', 'The authenticated user has no tenantId, so the tenant isolation check will fail closed.');
    }

    const injectedRules = rulesToText(rules.value);
    log('STEP 1', 'info', `Rules converted to injected_rules text (${injectedRules.length} characters).`, injectedRules);
    if (u.tenantId != null && !/tenant_id/i.test(injectedRules)) {
      log('SECURITY', 'warn', 'The NL-to-SQL rules do not mention tenant_id. The model may omit the tenant filter; verification will catch it.');
    }

    setGenState('loading');
    const body = { user_query: q, injected_rules: injectedRules };
    log('NL-TO-SQL', 'info', 'POST /api/v1/translate → NL-to-SQL service (port 8000). Waiting for the LLM…', body);
    const res = await postJson(NL_TRANSLATE_URL, body, NL_TIMEOUT_MS);

    if (!res.ok || !res.data || res.data.status !== 'SUCCESS' || !res.data.predicted_sql) {
      const message = res.ok ? `Unexpected response: status "${res.data?.status}" without predicted_sql.` : describeError(res, NL_TIMEOUT_MS);
      log('NL-TO-SQL', 'error', `Generation failed after ${res.ms} ms: ${message}`, res.data || undefined);
      if (res.status === 0 || !res.data) log('NL-TO-SQL', 'info', 'Hint: start the service with  .\\venv\\Scripts\\python.exe run_server.py  in nl-to-sql-service.');
      setGenState('fail');
      setGenError(message);
      return;
    }

    const { predicted_sql: predicted, metadata = {} } = res.data;
    log('NL-TO-SQL', 'success', `SQL generated in ${res.ms} ms.`, predicted);
    log('NL-TO-SQL', 'info', `Tokens: ${metadata.total_tokens ?? '?'} (prompt ${metadata.prompt_tokens ?? '?'}, completion ${metadata.completion_tokens ?? '?'}) · refinement attempts: ${metadata.refinement_attempts ?? 0} · self-healed: ${metadata.healed ? 'yes' : 'no'}.`, metadata);
    if (metadata.is_valid === false) log('NL-TO-SQL', 'warn', 'The engine marked its own SQL as not valid after refinement. Verification will decide.');
    if (!/^\s*(with|select)\b/i.test(predicted)) log('SECURITY', 'warn', 'Generated statement is not a SELECT. Read-only policies will block it.');
    if (/;\s*\S/.test(predicted)) log('SECURITY', 'warn', 'Generated text contains more than one statement (";" followed by more SQL).');

    setGenerated({ sql: predicted, metadata, ms: res.ms });
    setSql(predicted);
    setGenState('pass');
    log('STEP 2', 'info', 'Step 2 unlocked. Review the SQL and click Verify.');
    setTimeout(() => step2Ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  };

  // ---- Step 2: SQL + policy + user -> SQLGlot + security backend ----------
  const verifySql = async () => {
    setInspect(null); setVerify(null);
    const policy = parseObject('User policy', policyText);
    const user = parseObject('Authenticated user', userText);
    if (policy.error || user.error || !sql.trim()) {
      [policy.error, user.error, !sql.trim() && 'SQL is empty.'].filter(Boolean).forEach((e) => log('STEP 2', 'error', e));
      setVerifyState('fail');
      return;
    }
    if (sql.trim() !== generated?.sql.trim()) {
      log('SECURITY', 'warn', 'The SQL was edited by hand after generation. The edited text is what gets verified.', sql);
    }
    setVerifyState('loading');
    setVerifiedPolicy(policy.value);
    log('STEP 2', 'info', 'Verify clicked. Sending the SQL, user policy and authenticated user for checking.');

    // 2a. SQLGlot: parse into an AST and extract tables, columns, filters.
    log('SQLGLOT', 'info', 'POST /inspect → SQLGlot service (port 8001), dialect mysql.');
    const ins = await postJson(SQLGLOT_INSPECT_URL, { sql, dialect: 'mysql' }, SERVICE_TIMEOUT_MS);
    if (!ins.ok || !ins.data?.analysis) {
      const message = describeError(ins, SERVICE_TIMEOUT_MS);
      log('SQLGLOT', 'error', `Inspection failed after ${ins.ms} ms: ${message}`, ins.data || undefined);
      setInspect({ error: message });
    } else {
      const a = ins.data.analysis;
      setInspect({ analysis: a, ms: ins.ms });
      log('SQLGLOT', 'success', `Parsed in ${ins.ms} ms: ${a.statementType} · ${a.tables.length} table(s) · ${a.columns.length} column reference(s) · ${a.filters.length} filter(s) · ${a.joins.length} join(s).`, a);
      if (!KNOWN_STATEMENTS.includes(a.statementType)) {
        log('SQLGLOT', 'warn', `SQLGlot read this as "${a.statementType}", which usually means the text is not valid SQL.`);
      }
      const allowed = new Set(policy.value.allowedTables.map((t) => String(t).toLowerCase()));
      const outside = a.tables.filter((t) => !allowed.has(String(t.name).toLowerCase())).map((t) => t.name);
      if (outside.length) log('SECURITY', 'warn', `Table(s) outside the policy: ${outside.join(', ')}.`);
      const denied = new Set((policy.value.deniedColumns || []).map((c) => String(c).toLowerCase()));
      const hit = a.columns.map((c) => `${qualify(c, a)}.${c.column}`).filter((c) => denied.has(c.toLowerCase()));
      if (hit.length) log('SECURITY', 'warn', `Denied column(s) referenced: ${[...new Set(hit)].join(', ')}.`);
      const tenantFilters = a.filters.filter((f) => f.column === 'tenant_id');
      log('SECURITY', tenantFilters.length ? 'info' : 'warn', tenantFilters.length
        ? `Tenant filter found: ${tenantFilters.map((f) => `${qualify(f, a)}.tenant_id ${f.operator} ${f.value}`).join(', ')}.`
        : 'No tenant_id filter found in the query.');
    }

    // 2b. Security backend: SQLGlot analysis + policy + user -> decision.
    log('POLICY', 'info', 'POST /api/verify-sql → security checking backend (port 5000). It runs its own SQLGlot inspection, then the policy checks.');
    const ver = await postJson(VERIFY_URL, { policy: policy.value, user: user.value, sql, dialect: 'mysql' }, SERVICE_TIMEOUT_MS);
    if (!ver.ok || !ver.data?.checks) {
      const message = describeError(ver, SERVICE_TIMEOUT_MS);
      const code = ver.data?.code;
      const hint = code === 'SQLGLOT_UNAVAILABLE'
        ? 'The backend could not reach SQLGlot. Start sqlglot-service on port 8001.'
        : (!ver.data ? 'Start the backend with  npm start  in demo-application/backend (port 5000).' : null);
      log('POLICY', 'error', `Verification failed after ${ver.ms} ms: ${message}`, ver.data || undefined);
      if (hint) log('POLICY', 'info', `Hint: ${hint}`);
      setVerify({ error: message, hint });
      setVerifyState('fail');
      return;
    }

    const r = ver.data;
    setVerify({ result: r, ms: ver.ms });
    r.checks.forEach((check) => log('POLICY', check.passed ? 'success' : 'error',
      `${check.label}: ${check.passed ? 'PASS' : 'FAIL'} - ${check.message}`, check.reason ? { reason: check.reason } : undefined));
    log('DECISION', r.passed ? 'success' : 'error', `${r.decision}: ${r.message}`);
    setVerifyState(r.passed ? 'pass' : 'fail');
  };

  const inspectState = !inspect ? (verifyState === 'loading' ? 'loading' : 'idle') : inspect.error ? 'fail' : 'pass';
  const steps = [
    { label: 'Inputs', state: genState === 'idle' ? 'active' : genState === 'invalid' ? 'fail' : 'pass' },
    { label: 'NL → SQL', state: genState === 'loading' ? 'active' : genState === 'pass' ? 'pass' : genState === 'fail' ? 'fail' : 'idle' },
    { label: 'SQLGlot', state: inspectState === 'loading' ? 'active' : inspectState },
    { label: 'Decision', state: verifyState === 'loading' && inspect ? 'active' : verifyState === 'pass' ? 'pass' : verifyState === 'fail' ? 'fail' : 'idle' }
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><Icon name="shield" size={22} /></span>
          <div><strong>PolicyGate</strong><span>NL → SQL → verification pipeline</span></div>
        </div>
        <div className="topbar-actions">
          <a className="reset-button pl-link" href="#/">SQL verification console</a>
          <button className="reset-button" type="button" onClick={resetAll}><Icon name="refresh" size={16} /> Reset</button>
        </div>
      </header>

      <main>
        <div className="page-heading">
          <div>
            <p className="kicker">End-to-end pipeline</p>
            <h1>Ask in English, verify the SQL</h1>
            <p>Step 1 turns your question into SQL with the NL-to-SQL engine. Step 2 checks that SQL with SQLGlot and the security backend against the user's policy.</p>
          </div>
          <Stepper steps={steps} />
        </div>

        <div className="workspace pl-workspace">
          <div className="input-stack">
            {/* ---------------- Step 1 ---------------- */}
            <section className="input-card pl-step-card">
              <div className="pl-step-title">
                <span className="pl-step-badge">Step 1</span>
                <h2>Question &amp; context</h2>
                <StatusPill state={genState} />
              </div>

              <label className="pl-label" htmlFor="pl-question">Natural language question</label>
              <textarea id="pl-question" className="pl-question" value={question} maxLength={MAX_QUESTION_CHARS}
                onChange={(event) => setQuestion(event.target.value)} placeholder="e.g. Show employees who joined this year" />
              <div className="pl-counter">{question.length} / {MAX_QUESTION_CHARS}</div>

              <div className="pl-json-grid">
                <JsonUpload number="A" icon="file" title="User policy" description="Allowed tables, denied columns, required filters"
                  text={policyText} onText={setPolicyText} fileName={files.policy} onFileName={setFile('policy')} log={log} />
                <JsonUpload number="B" icon="user" title="Authenticated user" description="Identity claims (userId, role, tenantId)"
                  text={userText} onText={setUserText} fileName={files.user} onFileName={setFile('user')} log={log} />
                <JsonUpload number="C" icon="code" title="NL-to-SQL rules" description="Sent to the engine as injected_rules"
                  text={rulesText} onText={setRulesText} fileName={files.rules} onFileName={setFile('rules')} log={log} />
              </div>

              {genError && <div className="pl-banner fail"><Icon name="close" size={16} /> {genError}</div>}
              <div className="pl-actions">
                <span className="pl-muted">Sends the question and the rules to the NL-to-SQL service.</span>
                <button className="verify-button" type="button" onClick={submit} disabled={genState === 'loading'}>
                  <Icon name="bolt" size={17} /> {genState === 'loading' ? 'Generating SQL…' : 'Submit'}
                </button>
              </div>
            </section>

            {/* ---------------- Step 2 ---------------- */}
            <section ref={step2Ref} className={`input-card pl-step-card ${generated ? '' : 'pl-locked'}`}>
              <div className="pl-step-title">
                <span className="pl-step-badge">Step 2</span>
                <h2>Verify the generated SQL</h2>
                <StatusPill state={verifyState === 'idle' ? 'idle' : verifyState} />
              </div>

              {!generated ? (
                <p className="pl-muted">Submit step 1 first. The generated SQL will appear here.</p>
              ) : (
                <>
                  <div className="pl-meta-row">
                    <span>Generated in {generated.ms} ms</span>
                    <span>{generated.metadata.total_tokens ?? '?'} tokens</span>
                    <span>Refinements: {generated.metadata.refinement_attempts ?? 0}</span>
                    <span className={generated.metadata.is_valid === false ? 'bad' : 'ok'}>Engine valid: {generated.metadata.is_valid === false ? 'no' : 'yes'}</span>
                    {generated.metadata.healed && <span className="ok">Self-healed</span>}
                  </div>
                  <textarea className="code-input sql-input" value={sql} spellCheck="false" aria-label="Generated SQL"
                    onChange={(event) => setSql(event.target.value)} />
                  {sql.trim() !== generated.sql.trim() && (
                    <p className="field-error"><Icon name="close" size={15} /> Edited by hand. The edited SQL is what will be verified.</p>
                  )}
                  <div className="pl-actions">
                    <span className="pl-muted">SQL + policy + user → SQLGlot (8001) and security backend (5000).</span>
                    <button className="verify-button" type="button" onClick={verifySql} disabled={verifyState === 'loading'}>
                      <Icon name="shield" size={17} /> {verifyState === 'loading' ? 'Verifying…' : 'Verify'}
                    </button>
                  </div>

                  {(inspect || verify || verifyState === 'loading') && (
                    <div className="pl-results">
                      {verifyState === 'loading' && !verify && (
                        <div className="pl-result-card pl-loading"><span className="spinner" /> Checking the query…</div>
                      )}
                      <InspectionCard inspect={inspect} policy={verifiedPolicy} />
                      <DecisionCard verify={verify} />
                    </div>
                  )}
                </>
              )}
            </section>
          </div>

          <ActivityLog entries={logs} onClear={() => setLogs([])} />
        </div>
      </main>

      <footer>
        <span><Icon name="shield" size={14} /> Generated SQL is inspected and evaluated only; it is never executed here.</span>
        <span>NL-to-SQL → SQLGlot → Policy checks → Decision</span>
      </footer>
    </div>
  );
}
