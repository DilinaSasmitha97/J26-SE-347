import React, { useEffect, useRef, useState } from 'react';
import { Icon } from '../App.jsx';
import PresentationResult from '../components/PresentationResult.jsx';
import IntentClassificationCard, { INTENT_LABELS, PRESENTATION_TYPE_LABELS } from '../components/IntentClassificationCard.jsx';

// The browser supplies the operator's pasted context to the Node demo gateway.
// The gateway validates it before generation, verification and masked execution.
const SECURE_QUERY_URL = '/api/secure-query';
const GENERATE_SQL_URL = '/api/generate-sql';
const CLASSIFY_INTENT_URL = '/api/classify-intent';

const MAX_FILE_BYTES = 256 * 1024; // matches the backend's JSON body limit
const MAX_QUESTION_CHARS = 2000;
const PIPELINE_TIMEOUT_MS = 120000; // LLM calls with self-refinement can be slow
const CLASSIFY_TIMEOUT_MS = 40000;
const NO_CLASSIFICATION = { status: 'idle', question: '', result: null, error: null };
const KNOWN_STATEMENTS = ['SELECT', 'INSERT', 'UPDATE', 'DELETE'];

const SAMPLE_QUESTION = 'Show the first name, last name and work email of employees in my department';

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

// The classification must match the question it was requested for; the model
// cannot rewrite the question, invent an intent, or choose formats outside the
// six allowed types.
function classificationProblem(data, question) {
  if (!data || typeof data !== 'object' || Array.isArray(data)) return 'the response is not a JSON object';
  if (data.nl_query !== question) return 'the response is for a different question';
  if (!Object.hasOwn(INTENT_LABELS, data.intent)) return 'an unsupported intent was returned';
  const types = data.presentation_types;
  if (!Array.isArray(types) || !types.length) return 'no presentation types were returned';
  if (types.some((type) => !Object.hasOwn(PRESENTATION_TYPE_LABELS, type))) return 'an unsupported presentation type was returned';
  if (new Set(types).size !== types.length) return 'duplicate presentation types were returned';
  if (typeof data.prediction_needed !== 'boolean') return 'prediction_needed is not a Boolean';
  return null;
}

async function postJson(url, body, timeoutMs, signal) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  signal?.addEventListener('abort', () => controller.abort(), { once: true });
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
      ok: false, status: 0, data: null, network: true, cancelled: Boolean(signal?.aborted),
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

function JsonUpload({ number, icon, title, description, text, onText, fileName, onFileName, log, disabled = false, optional = false }) {
  const input = useRef(null);
  const empty = !text.trim();
  const parsed = optional && empty ? { value: {} } : parseObject(title, text);

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
    <section className={`input-card pl-json-card ${!empty && parsed.error ? 'has-error' : ''}`}>
      <div className="card-heading">
        <span className="step-number">{number}</span>
        <span className="card-icon"><Icon name={icon} /></span>
        <div><h2>{title}</h2><p>{description}</p></div>
      </div>
      <div className="pl-upload-row">
        <button type="button" className="pl-ghost" onClick={() => input.current?.click()} disabled={disabled}>
          <Icon name="file" size={15} /> Upload .json
        </button>
        <span className="pl-file-name">{fileName || 'Paste JSON or upload a file'}</span>
        <input ref={input} type="file" accept=".json,application/json" hidden disabled={disabled}
          onChange={(event) => { readFile(event.target.files[0]); event.target.value = ''; }} />
      </div>
      <textarea className="code-input pl-json-input" value={text} spellCheck="false" aria-label={title} disabled={disabled} placeholder={optional ? 'Optional: paste additional rules as JSON' : `Paste ${title.toLowerCase()} JSON`}
        onChange={(event) => { onText(event.target.value); onFileName(fileName ? `${fileName} (edited)` : ''); }} />
      {empty ? <p className="pl-muted">{optional ? 'Optional. The SQL service receives your question with no additional rules when left empty.' : 'Paste JSON or upload a .json file to continue.'}</p> : parsed.error
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

function SqlSafetyCard({ validation }) {
  if (!validation) return null;
  return (
    <div className={`pl-result-card ${validation.safe ? 'is-pass' : 'is-fail'}`}>
      <div className="pl-result-head">
        <h3>SQL safety validation</h3>
        <StatusPill state={validation.safe ? 'pass' : 'fail'} />
      </div>
      <dl className="pl-facts">
        <div><dt>Parser verdict</dt><dd>{validation.safe ? 'Safe to continue' : 'Blocked before execution'}</dd></div>
        <div><dt>Statement</dt><dd><span className={`pl-chip ${validation.safe ? 'ok' : 'bad'}`}>{validation.statementType}</span></dd></div>
        <div><dt>Protection</dt><dd>Single statement, read-only operation, dangerous functions, system schemas and policy-derived allowlist</dd></div>
      </dl>
      {validation.violations?.length > 0 && (
        <div className="pl-violation-list">
          {validation.violations.map((item, index) => (
            <div key={`${item.type}-${index}`}><strong>{item.type}</strong><span>{item.detail}</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

function ExecutionCard({ execution }) {
  if (!execution) return null;
  if (execution.error) {
    return (
      <div className="pl-result-card is-fail">
        <div className="pl-result-head"><h3>Secure execution &amp; masking</h3><StatusPill state="error" /></div>
        <p className="pl-error-text">{execution.error.message}</p>
        <p className="pl-mono pl-reason">{execution.error.code}</p>
        <div className="service-hint">Validation passed, but MySQL execution could not complete. Configure the shared database credentials in demo-application/.env.</div>
      </div>
    );
  }

  const result = execution.result;
  const columns = result.columns || [];
  const classifications = result.classification || [];
  return (
    <div className="pl-result-card is-pass pl-execution-card">
      <div className="pl-result-head">
        <h3>Secure execution &amp; masking</h3>
        <StatusPill state="done" />
      </div>
      <div className="pl-meta-row">
        <span>Engine: {result.engine || 'mysql'}</span>
        <span>{result.rowCount} database row(s)</span>
        <span>{result.rows.length} returned</span>
        <span>{result.elapsedMs} ms query time</span>
        <span className="ok">{result.masking?.maskedCells || 0} cell(s) masked</span>
        <span>NER: {result.ner?.status || 'unknown'}</span>
      </div>
      <div className="pl-table-wrap">
        <table className="pl-data-table">
          <thead><tr>{columns.map((column, index) => <th key={`${column.name}-${index}`}>{column.name}</th>)}</tr></thead>
          <tbody>
            {result.rows.length ? result.rows.map((row, rowIndex) => (
              <tr key={rowIndex}>{row.map((value, columnIndex) => <td key={columnIndex}>{value == null ? 'NULL' : String(value)}</td>)}</tr>
            )) : <tr><td colSpan={Math.max(columns.length, 1)}>No rows returned.</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="inspection-summary">
        <div className="summary-heading"><span>PII classification &amp; masking plan</span><span className="source-badge">Security layer</span></div>
        <div className="pl-classification-grid">
          {columns.map((column, index) => {
            const classification = classifications[index] || {};
            const plan = result.masking?.columns?.find((item) => item.name === column.name);
            return (
              <div key={`${column.name}-${index}`}>
                <strong>{column.name}</strong>
                <span>{classification.piiType || 'Non-PII'}</span>
                <small>{plan?.action || 'clear'} · {classification.method || 'schema/values'}</small>
              </div>
            );
          })}
        </div>
      </div>
      {result.ner?.warnings?.map((warning, index) => <div key={index} className="pl-banner fail">{warning}</div>)}
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
  const [policyText, setPolicyText] = useState('');
  const [userText, setUserText] = useState('');
  const [rulesText, setRulesText] = useState('');
  const [files, setFiles] = useState({ policy: '', user: '', rules: '' });

  const [genState, setGenState] = useState('idle');
  const [genError, setGenError] = useState(null);
  const [generated, setGenerated] = useState(null); // { sql, metadata, ms }
  const [sql, setSql] = useState('');

  const [verifyState, setVerifyState] = useState('idle');
  const [inspect, setInspect] = useState(null);
  const [verify, setVerify] = useState(null);
  const [sqlSafety, setSqlSafety] = useState(null);
  const [execution, setExecution] = useState(null);
  const [presentation, setPresentation] = useState(null);
  const [verifiedPolicy, setVerifiedPolicy] = useState(null);
  const busy = genState === 'loading' || verifyState === 'loading';

  const clearVerification = () => {
    setVerifyState('idle'); setInspect(null); setVerify(null); setSqlSafety(null); setExecution(null); setVerifiedPolicy(null); setPresentation(null);
  };

  const invalidateDraft = () => {
    setGenerated(null); setSql(''); setGenState('idle'); setGenError(null); clearVerification();
  };

  const [logs, setLogs] = useState([]);
  const nextId = useRef(0);
  const step2Ref = useRef(null);
  const log = (stage, level, message, detail) =>
    setLogs((current) => [...current, { id: nextId.current++, time: timeStamp(), stage, level, message, detail }]);

  const setFile = (key) => (name) => setFiles((current) => ({ ...current, [key]: name }));

  // ---- Step 1a: classify the question when Generate SQL is clicked -----------
  // Question only, stored apart from the SQL draft.
  const [classification, setClassification] = useState(NO_CLASSIFICATION);
  const classifyController = useRef(null);
  const classifySeq = useRef(0);
  const trimmedQuestion = question.trim();

  // Cancels any in-flight request; a late response for an older question no
  // longer matches classifySeq and is ignored.
  const cancelClassification = () => {
    classifyController.current?.abort();
    classifyController.current = null;
    classifySeq.current += 1;
  };
  useEffect(() => cancelClassification, []);

  // A classification for a previous question is never shown or used.
  const currentClassification = classification.question === trimmedQuestion ? classification : NO_CLASSIFICATION;
  const classifying = currentClassification.status === 'loading';
  const classified = currentClassification.status === 'ready' && currentClassification.result?.nl_query === trimmedQuestion;
  const classificationFailed = currentClassification.status === 'error';

  const classifyQuestion = async () => {
    const q = trimmedQuestion;
    if (busy || classifying) return;
    if (!q || q.length > MAX_QUESTION_CHARS) {
      log('STEP 1', 'error', !q ? 'Natural language question is empty.' : `Question is ${q.length} characters; the limit is ${MAX_QUESTION_CHARS}.`);
      return;
    }
    cancelClassification();
    invalidateDraft();
    const seq = classifySeq.current;
    const controller = new AbortController();
    classifyController.current = controller;
    log('STEP 1', 'info', 'Generate SQL clicked. Classifying the question (question only) before SQL generation.');
    setClassification({ status: 'loading', question: q, result: null, error: null });
    const res = await postJson(CLASSIFY_INTENT_URL, { nl_query: q }, CLASSIFY_TIMEOUT_MS, controller.signal);
    if (seq !== classifySeq.current || res.cancelled) return;
    classifyController.current = null;

    const problem = res.ok ? classificationProblem(res.data, q) : null;
    if (!res.ok || problem) {
      const message = problem ? `The classifier response was rejected: ${problem}.` : describeError(res, CLASSIFY_TIMEOUT_MS);
      setClassification({ status: 'error', question: q, result: null, error: message });
      log('INTENT', 'error', `Intent classification failed after ${res.ms} ms: ${message}`, res.data || undefined);
      log('STEP 1', 'info', 'Retry the classification, or continue to SQL generation without it.');
      return;
    }
    setClassification({ status: 'ready', question: q, result: res.data, error: null });
    log('INTENT', 'success', `Question classified in ${res.ms} ms: intent ${INTENT_LABELS[res.data.intent]}; formats ${res.data.presentation_types.map((type) => PRESENTATION_TYPE_LABELS[type]).join(', ')}; prediction needed: ${res.data.prediction_needed ? 'yes' : 'no'}.`, res.data);
    log('STEP 1', 'info', 'Review the classification, then click Continue to SQL.');
  };

  // Changing the question cancels its classification and clears the draft and results.
  const changeQuestion = (value) => {
    setQuestion(value);
    if (value.trim() === trimmedQuestion) return;
    cancelClassification();
    setClassification(NO_CLASSIFICATION);
    invalidateDraft();
  };

  const resetAll = () => {
    cancelClassification();
    setClassification(NO_CLASSIFICATION);
    setQuestion(SAMPLE_QUESTION);
    setPolicyText('');
    setUserText('');
    setRulesText('');
    setFiles({ policy: '', user: '', rules: '' });
    setGenState('idle'); setGenError(null); setGenerated(null); setSql('');
    clearVerification();
    setLogs([]);
  };

  // ---- Step 1b: generate an editable draft without executing it -----------
  // Runs on Continue to SQL, or on Continue without classification after a
  // failed classification. The classification is never added to the request.
  const generateSql = async ({ withoutClassification = false } = {}) => {
    if (busy || !(classified || (withoutClassification && classificationFailed))) return;
    setGenerated(null); setSql(''); setGenError(null);
    clearVerification();
    if (withoutClassification) log('INTENT', 'warn', 'Continuing to SQL generation without a classification for this question.');
    log('STEP 1', 'info', 'Continue to SQL clicked. Validating the question and the three JSON inputs.');

    const q = question.trim();
    const policy = parseObject('User policy', policyText);
    const user = parseObject('Authenticated user', userText);
    const rules = rulesText.trim() ? parseObject('NL-to-SQL rules', rulesText) : { value: null };
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

    const u = user.value;
    if (!u.userId) {
      log('STEP 1', 'error', 'Authenticated user JSON must contain userId.');
      setGenState('invalid');
      setGenError('Add userId to your user JSON, then submit again.');
      return;
    }
    log('STEP 1', 'success', `Inputs valid. Requesting SQL generation for ${u.userId} using the pasted context.`);
    log('NL-TO-SQL', 'info', 'Only the natural-language question and pasted NL-to-SQL rules are forwarded to the SQL service. The gateway keeps user and policy context for validation and execution.');

    setGenState('loading');
    const body = { question: q, user: u, policy: policy.value, rules: rules.value };
    log('NL-TO-SQL', 'info', 'POST /api/generate-sql → backend gateway. Generate a SQL draft for review before validation and execution.', body);
    const res = await postJson(GENERATE_SQL_URL, body, PIPELINE_TIMEOUT_MS);

    if (!res.ok || !res.data?.sql) {
      const message = describeError(res, PIPELINE_TIMEOUT_MS);
      log('PIPELINE', 'error', `Secure generation failed after ${res.ms} ms: ${message}`, res.data || undefined);
      if (res.status === 0 || !res.data) log('PIPELINE', 'info', 'Start the Node backend and NL-to-SQL service, then retry.');
      setGenState('fail');
      setGenError(message);
      return;
    }

    const pipeline = res.data;
    const predicted = pipeline.sql;
    const metadata = pipeline.generation?.metadata || {};
    log('NL-TO-SQL', 'success', `SQL generated through the backend gateway in ${res.ms} ms.`, predicted);
    log('NL-TO-SQL', 'info', `Tokens: ${metadata.total_tokens ?? '?'} (prompt ${metadata.prompt_tokens ?? '?'}, completion ${metadata.completion_tokens ?? '?'}) · refinement attempts: ${metadata.refinement_attempts ?? 0} · self-healed: ${metadata.healed ? 'yes' : 'no'}.`, metadata);
    setGenerated({ sql: predicted, metadata, ms: res.ms, question: pipeline.question, userId: u.userId, context: { user: u, policy: policy.value, rules: rules.value }, injectedRules: pipeline.generation?.injectedRules });
    setSql(predicted);
    setGenState('pass');
    log('STEP 2', 'info', 'Review or edit the generated SQL, then click Validate & execute. Security and policy checks will run on the SQL in the editor before execution.');
    setTimeout(() => step2Ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  };

  // ---- Step 2: revalidate, execute read-only, classify and mask ------------
  const verifySql = async () => {
    if (busy || !generated || !sql.trim()) return;
    clearVerification();
    const user = parseObject('Authenticated user', userText);
    if (user.value?.userId && user.value.userId !== generated.userId) {
      log('STEP 2', 'error', 'The selected identity changed. Generate a fresh SQL draft.');
      invalidateDraft();
      return;
    }
    if (user.error || !user.value?.userId || !sql.trim() || user.value.userId !== generated.userId) {
      [user.error, !user.value?.userId && 'Authenticated user must contain userId.', !sql.trim() && 'SQL is empty.'].filter(Boolean).forEach((e) => log('STEP 2', 'error', e));
      setVerifyState('fail');
      return;
    }
    if (sql.trim() !== generated?.sql.trim()) {
      log('SECURITY', 'warn', 'The SQL was edited by hand after generation. The edited text is what gets verified.', sql);
    }
    setVerifyState('loading');
    log('STEP 2', 'info', 'Sending the edited SQL and pasted context for fresh validation, policy checks, read-only execution and PII masking.');
    const response = await postJson(SECURE_QUERY_URL, {
      sql: sql.trim(),
      question: generated.question,
      ...generated.context,
      execute: true
    }, PIPELINE_TIMEOUT_MS);

    if (!response.ok || !response.data?.decision) {
      const message = describeError(response, PIPELINE_TIMEOUT_MS);
      log('PIPELINE', 'error', `Secure execution request failed after ${response.ms} ms: ${message}`, response.data || undefined);
      setVerify({ error: message, hint: 'Check the backend, SQLGlot and database configuration.' });
      setVerifyState('fail');
      return;
    }

    const pipeline = response.data;
    setVerifiedPolicy(pipeline.effectivePolicy);
    setSqlSafety(pipeline.securityValidation);
    setInspect(pipeline.inspection ? { analysis: pipeline.inspection, ms: pipeline.elapsedMs } : null);
    setVerify({ result: pipeline.decision, ms: pipeline.elapsedMs });
    pipeline.decision.checks.forEach((check) => log('POLICY', check.passed ? 'success' : 'error',
      `${check.label}: ${check.passed ? 'PASS' : 'FAIL'} - ${check.message}`, check.reason ? { reason: check.reason } : undefined));
    if (pipeline.status === 'COMPLETED') {
      setExecution({ result: pipeline.result });
      setPresentation({ envelope: pipeline.presentation, status: pipeline.presentationStatus, error: pipeline.presentationError, resultId: pipeline.resultId, context: generated.context, question: pipeline.question });
      log('PRESENTATION', pipeline.presentationStatus === 'READY' ? 'success' : 'warn', pipeline.presentationStatus === 'READY'
        ? 'Answer, prediction and presentation completed using masked results.'
        : 'Presentation unavailable; the masked database results remain available.');
      log('EXECUTION', 'success', `Read-only query returned ${pipeline.result.rowCount} row(s); ${pipeline.result.masking.maskedCells} cell(s) were masked before the response left the backend.`, pipeline.result.masking);
      if (pipeline.result.ner?.warnings?.length) pipeline.result.ner.warnings.forEach((warning) => log('NER', 'warn', warning));
    } else if (pipeline.executionError) {
      setExecution({ error: pipeline.executionError });
      log('EXECUTION', 'error', `${pipeline.executionError.code}: ${pipeline.executionError.message}`, pipeline.executionError.details);
    }
    log('DECISION', pipeline.decision.passed ? 'success' : 'error', `${pipeline.decision.decision}: ${pipeline.decision.message}`);
    setVerifyState(pipeline.status === 'COMPLETED' || pipeline.status === 'APPROVED' ? 'pass' : 'fail');
  };

  const inspectState = !inspect ? (verifyState === 'loading' ? 'loading' : 'idle') : inspect.error ? 'fail' : 'pass';
  const intentStepState = { loading: 'active', ready: 'pass', error: 'fail' }[currentClassification.status] || 'idle';
  const steps = [
    { label: 'Inputs', state: genState === 'idle' ? 'active' : genState === 'invalid' ? 'fail' : 'pass' },
    { label: 'Intent', state: intentStepState },
    { label: 'NL → SQL', state: genState === 'loading' ? 'active' : genState === 'pass' ? 'pass' : genState === 'fail' ? 'fail' : 'idle' },
    { label: 'SQL safety', state: sqlSafety ? (sqlSafety.safe ? 'pass' : 'fail') : verifyState === 'loading' ? 'active' : 'idle' },
    { label: 'SQLGlot', state: inspectState === 'loading' ? 'active' : inspectState },
    { label: 'Policy', state: verifyState === 'loading' && inspect ? 'active' : verifyState === 'pass' ? 'pass' : verifyState === 'fail' ? 'fail' : 'idle' },
    { label: 'Mask', state: execution?.result ? 'pass' : execution?.error ? 'fail' : 'idle' },
    { label: 'Present', state: presentation?.status === 'READY' ? 'pass' : presentation?.status === 'UNAVAILABLE' ? 'fail' : 'idle' }
  ];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark"><Icon name="shield" size={22} /></span>
          <div><strong>PolicyGate</strong><span>NL → SQL → validation → masked results</span></div>
        </div>
        <div className="topbar-actions">
          <a className="reset-button pl-link" href="#/">SQL verification console</a>
          <button className="reset-button" type="button" onClick={resetAll} disabled={busy}><Icon name="refresh" size={16} /> Reset</button>
        </div>
      </header>

      <main>
        <div className="page-heading">
          <div>
            <p className="kicker">End-to-end pipeline</p>
            <h1>Classify, generate SQL, review it, then execute</h1>
            <p>Click Generate SQL to classify your question, review the classification, then continue to a SQL draft you can edit, validate and execute to see masked results.</p>
          </div>
          <Stepper steps={steps} />
        </div>

        <div className="workspace pl-workspace">
          <div className="input-stack">
            {/* ---------------- Step 1 ---------------- */}
            <section className="input-card pl-step-card">
              <div className="pl-step-title">
                <span className="pl-step-badge">Step 1</span>
                <h2>Question &amp; supplied context</h2>
                <StatusPill state={genState} />
              </div>

              <label className="pl-label" htmlFor="pl-question">Natural language question</label>
              <textarea id="pl-question" className="pl-question" value={question} maxLength={MAX_QUESTION_CHARS} disabled={busy}
                onChange={(event) => changeQuestion(event.target.value)} placeholder="e.g. Show employees who joined this year" />
              <div className="pl-counter">{question.length} / {MAX_QUESTION_CHARS}</div>
              <div className="vp-examples" aria-label="Example questions">
                {['How many employees are in my department?', 'Give me the gender distribution in my company', 'List employee names and work emails in my department', 'Chart monthly new hires in my department and forecast the next 3 months'].map((example) =>
                  <button key={example} type="button" className="pl-ghost" disabled={busy} onClick={() => changeQuestion(example)}>{example}</button>)}
              </div>

              <div className="pl-json-grid">
                <JsonUpload number="A" icon="file" title="User policy" description="Paste the policy to apply to this query"
                  text={policyText} onText={(value) => { setPolicyText(value); invalidateDraft(); }} fileName={files.policy} onFileName={setFile('policy')} log={log} disabled={busy} />
                <JsonUpload number="B" icon="user" title="Authenticated user" description="Paste the identity claims used to resolve policy filters"
                  text={userText} onText={(value) => { setUserText(value); invalidateDraft(); }} fileName={files.user} onFileName={setFile('user')} log={log} disabled={busy} />
                <JsonUpload number="C" icon="code" title="NL-to-SQL rules" description="Optional additional instructions for SQL generation"
                  text={rulesText} onText={(value) => { setRulesText(value); invalidateDraft(); }} fileName={files.rules} onFileName={setFile('rules')} log={log} disabled={busy} optional />
              </div>

              <IntentClassificationCard status={currentClassification.status} result={currentClassification.result}
                error={currentClassification.error} onRetry={classifyQuestion} disabled={busy} />

              {genError && <div className="pl-banner fail"><Icon name="close" size={16} /> {genError}</div>}
              <div className="pl-actions">
                <span className="pl-muted">{classified
                  ? 'Review the classification, then continue to generate a SQL draft for step 2.'
                  : classificationFailed
                    ? 'Classification failed. Retry it, or continue without it.'
                    : 'Generate SQL classifies the question first. No SQL is generated until you continue.'}</span>
                <div className="pl-action-buttons">
                  <button className={classified || classificationFailed ? 'pl-ghost' : 'verify-button'} type="button" onClick={classifyQuestion}
                    disabled={busy || classifying || !trimmedQuestion}>
                    <Icon name="bolt" size={17} /> {classifying ? 'Classifying…' : 'Generate SQL'}
                  </button>
                  {classified && (
                    <button className="verify-button" type="button" onClick={() => generateSql()} disabled={busy}>
                      <Icon name="code" size={17} /> {genState === 'loading' ? 'Generating SQL…' : 'Continue to SQL'}
                    </button>
                  )}
                  {classificationFailed && (
                    <button className="verify-button" type="button" onClick={() => generateSql({ withoutClassification: true })} disabled={busy}>
                      {genState === 'loading' ? 'Generating SQL…' : 'Continue without classification'}
                    </button>
                  )}
                </div>
              </div>
            </section>

            {/* ---------------- Step 2 ---------------- */}
            <section ref={step2Ref} className={`input-card pl-step-card ${generated ? '' : 'pl-locked'}`}>
              <div className="pl-step-title">
                <span className="pl-step-badge">Step 2</span>
                <h2>Review &amp; edit SQL</h2>
                <StatusPill state={verifyState === 'idle' ? 'idle' : verifyState} />
              </div>

              {!generated ? (
                <p className="pl-muted">Click Generate SQL, review the classification, then Continue to SQL. Your editable SQL draft will appear here.</p>
              ) : (
                <>
                  <div className="pl-meta-row">
                    <span>Generated in {generated.ms} ms</span>
                    <span>{generated.metadata.total_tokens ?? '?'} tokens</span>
                    <span>Refinements: {generated.metadata.refinement_attempts ?? 0}</span>
                    <span className={generated.metadata.is_valid === false ? 'bad' : 'ok'}>Engine valid: {generated.metadata.is_valid === false ? 'no' : 'yes'}</span>
                    {generated.metadata.healed && <span className="ok">Self-healed</span>}
                  </div>
                  {generated.injectedRules && <details><summary>NL-to-SQL rules sent</summary><pre>{typeof generated.injectedRules === 'string' ? generated.injectedRules : pretty(generated.injectedRules)}</pre></details>}
                  <label className="pl-label" htmlFor="pl-sql">SQL to validate and execute</label>
                  <textarea id="pl-sql" className="code-input sql-input" value={sql} spellCheck="false" aria-label="Generated SQL" disabled={busy}
                    onChange={(event) => { setSql(event.target.value); clearVerification(); }} />
                  {sql.trim() !== generated.sql.trim() && (
                    <p className="pl-muted">SQL edited. Your changes will be validated before execution.</p>
                  )}
                </>
              )}
              <div className="pl-actions">
                <span className="pl-muted">Validate the SQL in the editor, execute it read-only and return masked results.</span>
                <button className="verify-button" type="button" onClick={verifySql} disabled={busy || !generated || !sql.trim()}>
                  <Icon name="shield" size={17} /> {verifyState === 'loading' ? 'Validating & executing…' : 'Validate & execute'}
                </button>
              </div>
              {generated && (
                <>
                  {(inspect || verify || verifyState === 'loading') && (
                    <div className="pl-results">
                      {verifyState === 'loading' && !verify && (
                        <div className="pl-result-card pl-loading"><span className="spinner" /> Checking the query…</div>
                      )}
                      <SqlSafetyCard validation={sqlSafety} />
                      <InspectionCard inspect={inspect} policy={verifiedPolicy} />
                      <DecisionCard verify={verify} />
                      {presentation && <PresentationResult key={presentation.resultId || 'unavailable'} {...presentation}
                        onSimulate={presentation.resultId ? async (scenarioText) => {
                          const response = await postJson('/api/simulate', { resultId: presentation.resultId, ...presentation.context, scenarioText }, 65000);
                          if (!response.ok || response.data?.status !== 'SUCCESS') throw new Error(describeError(response, 65000));
                          log('WHAT-IF', 'success', 'Scenario evaluated against the authorized masked result.');
                          return response.data;
                        } : undefined} />}
                      <ExecutionCard execution={execution} />
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
        <span><Icon name="shield" size={14} /> Raw database rows stay in the backend; the browser receives masked values only.</span>
        <span>Inputs → Intent → NL-to-SQL → SQL safety → SQLGlot → Policy → Read-only DB → PII mask</span>
      </footer>
    </div>
  );
}
