import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from '../App.jsx';
import PresentationResult from '../components/PresentationResult.jsx';
import DataPresentation from '../components/DataPresentation.jsx';
import PredictionCard from '../components/PredictionCard.jsx';
import IntentClassificationCard, { INTENT_LABELS, PRESENTATION_TYPE_LABELS } from '../components/IntentClassificationCard.jsx';
import TenantIsolationCard from '../components/TenantIsolationCard.jsx';
import AstTraceDialog from '../components/AstTraceDialog.jsx';

// The browser supplies the operator's pasted context to the Node demo gateway.
// The gateway validates it before generation, verification and masked execution.
const SECURE_QUERY_URL = '/api/secure-query';
const GENERATE_SQL_URL = '/api/generate-sql';
const CLASSIFY_INTENT_URL = '/api/classify-intent';
const PRESENT_RESULT_URL = '/api/present-result';
const PREDICT_RESULT_URL = '/api/predict-result';

const MAX_FILE_BYTES = 256 * 1024; // matches the backend's JSON body limit
const MAX_QUESTION_CHARS = 2000;
const PIPELINE_TIMEOUT_MS = 120000; // LLM calls with self-refinement can be slow
const CLASSIFY_TIMEOUT_MS = 40000;
const NO_CLASSIFICATION = { status: 'idle', question: '', result: null, error: null };
const PRESENT_TIMEOUT_MS = 45000; // includes the verified AI summary
const NO_DISPLAY = { status: 'idle', data: null, error: null, request: null };
const PREDICT_TIMEOUT_MS = 70000; // model fitting + verified AI summary
// The prediction layer runs for a forecast request or an anomaly question.
const wantsPrediction = (classification) => Boolean(classification
  && (classification.prediction_needed || classification.intent === 'ANOMALY_DETECTION'));
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

// Pretty-prints a JSON object with 2-space indentation; null when the text is not one.
function formatJson(text) {
  if (!text.trim()) return null;
  try {
    const value = JSON.parse(text);
    if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
    return JSON.stringify(value, null, 2);
  } catch {
    return null;
  }
}

function JsonStatus({ empty, optional, parsed }) {
  if (empty) return <p className="pl-muted">{optional ? 'Optional. The SQL service receives your question with no additional rules when left empty.' : 'Paste JSON or upload a .json file to continue.'}</p>;
  if (parsed.error) return <p className="field-error"><Icon name="close" size={15} /> {parsed.error}</p>;
  return <p className="pl-field-ok"><Icon name="check" size={15} /> Valid JSON · {Object.keys(parsed.value).length} keys</p>;
}

/** Full-screen editor for one JSON card; edits the same text as the card. */
function JsonDialog({ number, title, description, text, onEdit, onPaste, onFormat, canFormat, status, onClose, disabled }) {
  const area = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    area.current?.focus();
    const onKey = (event) => { if (event.key === 'Escape') close.current(); };
    document.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = overflow; };
  }, []);
  const titleId = `pl-json-dialog-${number}`;
  return createPortal(
    <div className="pl-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="pl-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="pl-modal-head">
          <span className="step-number">{number}</span>
          <div><h2 id={titleId}>{title}</h2><p>{description}</p></div>
          <div className="pl-modal-actions">
            <button type="button" className="pl-ghost" onClick={onFormat} disabled={disabled || !canFormat}><Icon name="format" size={15} /> Format JSON</button>
            <button type="button" className="pl-ghost" onClick={onClose} aria-label="Close full screen"><Icon name="close" size={15} /></button>
          </div>
        </div>
        <textarea ref={area} className="code-input pl-modal-input" value={text} spellCheck="false" wrap="off" aria-label={`${title} editor`} disabled={disabled}
          onChange={(event) => onEdit(event.target.value)} onPaste={onPaste} onBlur={onFormat} />
        <div className="pl-modal-foot">
          {status}
          <button type="button" className="verify-button" onClick={onClose}>Done</button>
        </div>
      </div>
    </div>,
    document.body
  );
}

function JsonUpload({ number, icon, title, description, text, onText, onFormat, fileName, onFileName, log, disabled = false, optional = false }) {
  const input = useRef(null);
  const expandButton = useRef(null);
  const pasted = useRef(false);
  const [expanded, setExpanded] = useState(false);
  const empty = !text.trim();
  const parsed = optional && empty ? { value: {} } : parseObject(title, text);
  const formatted = formatJson(text);
  const canFormat = Boolean(formatted) && formatted !== text;

  // Reformatting keeps the same JSON, so it never clears the draft or results.
  const format = () => { if (canFormat) (onFormat || onText)(formatted); };
  const edit = (value) => {
    const pretty = pasted.current ? formatJson(value) : null;
    pasted.current = false;
    onText(pretty || value);
    onFileName(fileName ? `${fileName.replace(/ \(edited\)$/, '')} (edited)` : '');
  };
  const markPaste = () => { pasted.current = true; };
  const closeDialog = () => { setExpanded(false); requestAnimationFrame(() => expandButton.current?.focus()); };
  const status = <JsonStatus empty={empty} optional={optional} parsed={parsed} />;

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
      onText(formatJson(content) || content);
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
        <span className="pl-json-tools">
          <button type="button" className="pl-icon-button" onClick={format} disabled={disabled || !canFormat}
            aria-label={`Format ${title} JSON`} title="Format JSON"><Icon name="format" size={15} /></button>
          <button type="button" ref={expandButton} className="pl-icon-button" onClick={() => setExpanded(true)}
            aria-label={`Expand ${title} to full screen`} title="Expand to full screen"><Icon name="expand" size={15} /></button>
        </span>
        <input ref={input} type="file" accept=".json,application/json" hidden disabled={disabled}
          onChange={(event) => { readFile(event.target.files[0]); event.target.value = ''; }} />
      </div>
      <textarea className="code-input pl-json-input" value={text} spellCheck="false" wrap="off" aria-label={title} disabled={disabled} placeholder={optional ? 'Optional: paste additional rules as JSON' : `Paste ${title.toLowerCase()} JSON`}
        onChange={(event) => edit(event.target.value)} onPaste={markPaste} onBlur={format} />
      {status}
      {expanded && (
        <JsonDialog number={number} title={title} description={description} text={text} onEdit={edit} onPaste={markPaste}
          onFormat={format} canFormat={canFormat} status={status} onClose={closeDialog} disabled={disabled} />
      )}
    </section>
  );
}

function Stepper({ steps }) {
  return (
    <div className="pipeline pl-stepper" aria-label="Pipeline progress">
      {steps.map((step, i) => (
        <React.Fragment key={step.label}>
          {i > 0 && <i />}
          <span className={`pl-step-${step.state}`} title={step.label}>
            <b>{step.state === 'pass' ? '✓' : step.state === 'fail' ? '✕' : i + 1}</b> <span className="pl-step-label">{step.label}</span>
          </span>
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
  const [trace, setTrace] = useState(null);
  const traceButton = useRef(null);
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
  const closeTrace = () => { setTrace(null); requestAnimationFrame(() => traceButton.current?.focus()); };
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
        {r.checks.map((check) => {
          const body = (
            <>
              <span className={`check-mark ${check.passed ? 'pass' : 'fail'}`}><Icon name={check.passed ? 'check' : 'close'} size={15} /></span>
              <div>
                <strong>{check.label}</strong>
                <p>{check.message}</p>
                {check.reason && <p className="pl-mono pl-reason">{check.reason}</p>}
                {check.astTrace && <span className="check-link"><Icon name="code" size={13} /> View AST breakdown</span>}
              </div>
              <span className={`mini-status ${check.passed ? 'pass' : 'fail'}`}>{check.passed ? 'Passed' : 'Failed'}</span>
            </>
          );
          return check.astTrace ? (
            <button type="button" className="check-item is-clickable" key={check.label} ref={traceButton}
              onClick={() => setTrace(check.astTrace)} aria-haspopup="dialog">{body}</button>
          ) : <div className="check-item" key={check.label}>{body}</div>;
        })}
      </div>
      {trace && <AstTraceDialog trace={trace} onClose={closeTrace} />}
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
        <div><dt>Protection</dt><dd>Single statement, read-only operation, dangerous functions, system schemas and unsafe query patterns</dd></div>
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
  const [tenantRewrite, setTenantRewrite] = useState(null);
  const [execution, setExecution] = useState(null);
  const [presentation, setPresentation] = useState(null); // prediction envelope, when enabled
  const [display, setDisplay] = useState(NO_DISPLAY);     // data presentation layer
  const displaySeq = useRef(0);
  const [prediction, setPrediction] = useState(NO_DISPLAY); // prediction layer
  const predictionSeq = useRef(0);
  const [verifiedPolicy, setVerifiedPolicy] = useState(null);
  const busy = genState === 'loading' || verifyState === 'loading';

  const clearVerification = () => {
    setTenantRewrite(null);
    setVerifyState('idle'); setInspect(null); setVerify(null); setSqlSafety(null); setExecution(null); setVerifiedPolicy(null); setPresentation(null);
    displaySeq.current += 1; setDisplay(NO_DISPLAY);
    predictionSeq.current += 1; setPrediction(NO_DISPLAY);
  };

  const invalidateDraft = () => {
    setGenerated(null); setSql(''); setGenState('idle'); setGenError(null); clearVerification();
  };

  const [logs, setLogs] = useState([]);
  const nextId = useRef(0);
  const step2Ref = useRef(null);
  const sqlBox = useRef(null);
  // The SQL editor grows with the query, so the whole statement is visible.
  useLayoutEffect(() => {
    const box = sqlBox.current;
    if (!box) return undefined;
    const fit = () => { box.style.height = 'auto'; box.style.height = `${box.scrollHeight + 2}px`; };
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, [sql, generated]);
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
    setGenerated({ sql: predicted, metadata, ms: res.ms, question: pipeline.question, userId: u.userId, context: { user: u, policy: policy.value, rules: rules.value }, injectedRules: pipeline.generation?.injectedRules,
      // Kept apart from the SQL request; used only to present the executed result.
      classification: withoutClassification ? null : { intent: currentClassification.result.intent, presentation_types: [...currentClassification.result.presentation_types], prediction_needed: currentClassification.result.prediction_needed } });
    setSql(predicted);
    setGenState('pass');
    log('STEP 2', 'info', 'Review or edit the generated SQL, then click Validate & execute. Security and policy checks will run on the SQL in the editor before execution.');
    setTimeout(() => step2Ref.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
  };

  // ---- Step 3: show the masked result in the classified formats ------------
  // ---- Step 4: forecast / anomalies for the same stored result -------------
  const predictResult = async (request) => {
    const seq = ++predictionSeq.current;
    setPrediction({ status: 'loading', data: null, error: null, request });
    const { resultId, context, classification } = request;
    log('PREDICTION', 'info', classification.prediction_needed
      ? 'Forecast requested: checking data readiness, selecting a model and forecasting.'
      : 'Anomaly question: checking the history for anomalies.');
    const res = await postJson(PREDICT_RESULT_URL, { resultId, ...context, classification }, PREDICT_TIMEOUT_MS);
    if (seq !== predictionSeq.current) return;
    if (!res.ok || !res.data?.readiness) {
      const message = describeError(res, PREDICT_TIMEOUT_MS);
      setPrediction({ status: 'error', data: null, error: message, request });
      log('PREDICTION', 'error', `Prediction failed after ${res.ms} ms: ${message}`, res.data || undefined);
      return;
    }
    setPrediction({ status: 'ready', data: res.data, error: null, request });
    const { forecast, readiness, anomalies } = res.data;
    log('PREDICTION', forecast.generated || res.data.mode === 'ANOMALY_ONLY' ? 'success' : 'warn',
      (forecast.generated
        ? `Forecast ready in ${res.ms} ms: ${forecast.points.length} periods with ${forecast.model.toLowerCase().replaceAll('_', ' ')} (readiness ${readiness.verdict}).`
        : res.data.mode === 'ANOMALY_ONLY' ? `Anomaly check done in ${res.ms} ms.` : `No forecast: ${forecast.skipped_reason || readiness.reason}`)
      + (anomalies.evaluated ? ` ${anomalies.historical_anomalies.length} historical anomal${anomalies.historical_anomalies.length === 1 ? 'y' : 'ies'}, ${anomalies.predictive_warnings.length} predicted breach(es).` : ''),
    { readiness: readiness.verdict, model: forecast.model, strategy: res.data.strategy.strategy });
  };

  const presentResult = async (request) => {
    const seq = ++displaySeq.current;
    setDisplay({ status: 'loading', data: null, error: null, request });
    const { resultId, context, classification } = request;
    log('PRESENTATION', 'info', classification
      ? `Rendering the result as: ${classification.presentation_types.map((type) => PRESENTATION_TYPE_LABELS[type]).join(', ')}.`
      : 'No classification for this question; choosing presentation formats from the data.');
    const res = await postJson(PRESENT_RESULT_URL, { resultId, ...context, classification }, PRESENT_TIMEOUT_MS);
    if (seq !== displaySeq.current) return;
    if (!res.ok || !Array.isArray(res.data?.views)) {
      const message = describeError(res, PRESENT_TIMEOUT_MS);
      setDisplay({ status: 'error', data: null, error: message, request });
      log('PRESENTATION', 'error', `Presentation failed after ${res.ms} ms: ${message}`, res.data || undefined);
      return;
    }
    setDisplay({ status: 'ready', data: res.data, error: null, request });
    const unavailable = res.data.views.filter((view) => !view.available);
    log('PRESENTATION', 'success', `Presentation ready in ${res.ms} ms: ${res.data.views.filter((view) => view.available).map((view) => view.label).join(', ') || 'no formats'}.`
      + (unavailable.length ? ` Not possible for this result: ${unavailable.map((view) => view.label).join(', ')}.` : ''),
    res.data.views.map(({ type, available, reason, notes }) => ({ type, available, reason, notes })));
  };

  // ---- Step 2: revalidate, execute read-only, classify and mask ------------
  const verifySql = async () => {
    if (busy || !generated || !sql.trim()) return;
    clearVerification();
    const policy = parseObject('User policy', policyText);
    const user = parseObject('Authenticated user', userText);
    const rules = rulesText.trim() ? parseObject('NL-to-SQL rules', rulesText) : { value: null };
    const problems = [
      policy.error, user.error, rules.error,
      policy.value && !Array.isArray(policy.value.allowedTables) && 'User policy must include an "allowedTables" array.',
      user.value && (typeof user.value.userId !== 'string' || !user.value.userId.trim()) && 'Authenticated user must contain a non-empty userId.'
    ].filter(Boolean);
    if (problems.length) {
      problems.forEach((message) => log('STEP 2', 'error', message));
      setVerifyState('fail');
      return;
    }
    // Each test uses the current editors, independently of the generation context.
    const context = { user: user.value, policy: policy.value, rules: rules.value };
    if (sql.trim() !== generated?.sql.trim()) {
      log('SECURITY', 'warn', 'The SQL was edited by hand after generation. The edited text is what gets verified.', sql);
    }
    setVerifyState('loading');
    log('STEP 2', 'info', 'Sending the edited SQL and pasted context for fresh validation, policy checks, read-only execution and PII masking.');
    const response = await postJson(SECURE_QUERY_URL, {
      sql: sql.trim(),
      question: generated.question,
      ...context,
      execute: true
    }, PIPELINE_TIMEOUT_MS);

    if (!response.ok || !response.data?.decision) {
      const message = describeError(response, PIPELINE_TIMEOUT_MS);
      setTenantRewrite(response.data?.tenantRewrite || { status: response.network || response.data?.code?.includes('UNAVAILABLE') ? 'UNAVAILABLE' : 'BLOCKED',
        message, reasonCode: response.data?.code || 'VERIFICATION_UNAVAILABLE', finalVerification: 'FAIL' });
      log('PIPELINE', 'error', `Secure execution request failed after ${response.ms} ms: ${message}`, response.data || undefined);
      setVerify({ error: message, hint: 'Check the backend, SQLGlot and database configuration.' });
      setVerifyState('fail');
      return;
    }

    const pipeline = response.data;
    setTenantRewrite(pipeline.tenantRewrite || { status: 'UNAVAILABLE', finalVerification: 'FAIL',
      message: 'The backend returned no tenant verification result. Restart the backend and SQLGlot service.' });
    if (pipeline.tenantRewrite) log('TENANT', pipeline.tenantRewrite.finalVerification === 'PASS' ? 'success' : 'error',
      `${pipeline.tenantRewrite.status}: ${pipeline.tenantRewrite.message}`, pipeline.tenantRewrite.changes);
    setVerifiedPolicy(pipeline.effectivePolicy);
    setSqlSafety(pipeline.securityValidation);
    setInspect(pipeline.inspection ? { analysis: pipeline.inspection, ms: pipeline.elapsedMs } : null);
    setVerify({ result: pipeline.decision, ms: pipeline.elapsedMs });
    pipeline.decision.checks.forEach((check) => log('POLICY', check.passed ? 'success' : 'error',
      `${check.label}: ${check.passed ? 'PASS' : 'FAIL'} - ${check.message}`, check.reason ? { reason: check.reason } : undefined));
    if (pipeline.status === 'COMPLETED') {
      setExecution({ result: pipeline.result });
      setPresentation({ envelope: pipeline.presentation, status: pipeline.presentationStatus, error: pipeline.presentationError, resultId: pipeline.resultId, context, question: pipeline.question });
      if (pipeline.presentationStatus === 'READY') log('PREDICTION', 'success', 'Prediction analysis completed using masked results.');
      // The stored result belongs to the identity and policy it was executed
      // with, so presentation and prediction must ask with that same context.
      const stored = { resultId: pipeline.resultId, context, classification: generated.classification };
      if (pipeline.resultId) {
        presentResult(stored);
        if (wantsPrediction(generated.classification)) predictResult(stored);
      } else {
        log('PRESENTATION', 'warn', 'The gateway kept no result to present; the masked rows are shown below.');
      }
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
    { label: 'Tenant isolation', state: verifyState === 'loading' ? 'active' : tenantRewrite ? (tenantRewrite.finalVerification === 'PASS' ? 'pass' : 'fail') : 'idle' },
    { label: 'Policy', state: verifyState === 'loading' && inspect ? 'active' : verifyState === 'pass' ? 'pass' : verifyState === 'fail' ? 'fail' : 'idle' },
    { label: 'Mask', state: execution?.result ? 'pass' : execution?.error ? 'fail' : 'idle' },
    { label: 'Predict', state: { loading: 'active', ready: 'pass', error: 'fail' }[prediction.status] || 'idle' },
    { label: 'Present', state: { loading: 'active', ready: 'pass', error: 'fail' }[display.status] || 'idle' }
  ];

  return (
    <div className="app-shell">
      <header className="topbar pl-topbar">
        <div className="brand">
          <span className="brand-mark"><Icon name="shield" size={22} /></span>
          <div><strong>PolicyGate</strong><span>NL → SQL → validation → masked results</span></div>
        </div>
        <Stepper steps={steps} />
        <div className="topbar-actions">
          <a className="reset-button pl-link" href="#/">SQL verification console</a>
          <button className="reset-button" type="button" onClick={resetAll} disabled={busy}><Icon name="refresh" size={16} /> Reset</button>
        </div>
      </header>

      <main>

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
                  text={policyText} onText={(value) => { setPolicyText(value); clearVerification(); }} onFormat={setPolicyText} fileName={files.policy} onFileName={setFile('policy')} log={log} disabled={busy} />
                <JsonUpload number="B" icon="user" title="Authenticated user" description="Paste the identity claims used to resolve policy filters"
                  text={userText} onText={(value) => { setUserText(value); clearVerification(); }} onFormat={setUserText} fileName={files.user} onFileName={setFile('user')} log={log} disabled={busy} />
                <JsonUpload number="C" icon="code" title="NL-to-SQL rules" description="Optional additional instructions for SQL generation"
                  text={rulesText} onText={(value) => { setRulesText(value); invalidateDraft(); }} onFormat={setRulesText} fileName={files.rules} onFileName={setFile('rules')} log={log} disabled={busy} optional />
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
                  <p className="pl-muted">For testing, change User policy or Authenticated user above, then click Validate &amp; execute again. The SQL stays in the editor; each run uses the current JSON and replaces the previous results.</p>
                  <label className="pl-label" htmlFor="pl-sql">SQL to validate and execute</label>
                  <textarea id="pl-sql" ref={sqlBox} rows={1} className="code-input sql-input pl-sql-autosize" value={sql} spellCheck="false" aria-label="Generated SQL" disabled={busy}
                    onChange={(event) => { setSql(event.target.value); clearVerification(); }} />
                  {sql.trim() !== generated.sql.trim() && (
                    <p className="pl-muted">SQL edited. Your changes will be validated before execution.</p>
                  )}
                </>
              )}
              <div className="pl-actions">
                <span className="pl-muted">Validate SQL, repair supported tenant restrictions, verify the final query and return masked results.</span>
                <button className="verify-button" type="button" onClick={verifySql} disabled={busy || !generated || !sql.trim()}>
                  <Icon name="shield" size={17} /> {verifyState === 'loading' ? 'Validating & executing…' : 'Validate & execute'}
                </button>
              </div>
              {generated && (
                <>
                  {!inspect && !verify && verifyState !== 'loading' && <TenantIsolationCard result={tenantRewrite} />}
                  {(inspect || verify || verifyState === 'loading') && (
                    <div className="pl-results">
                      {verifyState === 'loading' && !verify && (
                        <div className="pl-result-card pl-loading"><span className="spinner" /> Checking the query…</div>
                      )}
                      <SqlSafetyCard validation={sqlSafety} />
                      <InspectionCard inspect={inspect} policy={verifiedPolicy} />
                      <TenantIsolationCard result={tenantRewrite} loading={verifyState === 'loading'} />
                      <DecisionCard verify={verify} />
                      <DataPresentation status={display.status} data={display.data} error={display.error}
                        onRetry={display.request ? () => presentResult(display.request) : undefined} />
                      <PredictionCard status={prediction.status} data={prediction.data} error={prediction.error}
                        onRetry={prediction.request ? () => predictResult(prediction.request) : undefined} />
                      {presentation?.envelope && <PresentationResult key={presentation.resultId || 'unavailable'} {...presentation}
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

    </div>
  );
}
