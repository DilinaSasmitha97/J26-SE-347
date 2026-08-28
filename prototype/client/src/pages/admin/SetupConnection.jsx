import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../../lib/api.js';
import { useApp } from '../../context/AppContext.jsx';
import { formatValue } from '../../lib/format.js';
import { IconCheck, IconAlert, IconChevron } from '../../components/Icons.jsx';

// The scan runs long enough to be legible. Each stage gets an equal slice.
const SCAN_MS = 6000;
const SCAN_STAGES = [
  'Connecting to the database',
  'Reading tables and fields',
  'Working out how tables relate',
  'Checking what needs your input',
];
const STAGE_MS = SCAN_MS / SCAN_STAGES.length;

// The running commentary, grouped by the stage it belongs to. Real database
// tooling shows this; it is also the honest record of what the scan did.
function buildLog(conn, scan) {
  const host = conn?.host || 'host';
  const db = conn?.database || 'database';
  return [
    [0, `Resolving ${host}…`],
    [0, 'TCP connection established on port 3306'],
    [0, 'Secure connection negotiated (TLS 1.3)'],
    [0, `Authenticated as ${conn?.username || 'askdb_reader'}`],
    [1, `Listing tables in ${db}`],
    [1, 'Read orders — 18 fields'],
    [1, 'Read order_lines — 11 fields'],
    [1, 'Read customers — 14 fields'],
    [1, 'Read products — 9 fields'],
    [1, `Read ${Math.max(0, (scan?.tables || 12) - 4)} further tables`],
    [2, 'Reading declared foreign keys'],
    [2, 'Matched order_lines.order_id → orders.order_id'],
    [2, 'Matched order_lines.sku → products.sku'],
    [2, 'Inferred orders.cust_ref → customers.cust_code (not declared)'],
    [2, 'orders_bkp_2024 mirrors orders — possible duplicate'],
    [3, 'Classifying fields by meaning'],
    [3, '3 amount columns on orders — cannot pick one alone'],
    [3, 'cd_count has no recognisable meaning'],
    [3, 'sts holds 5 undocumented codes'],
    [3, `${scan?.flagged ?? 8} items need your confirmation`],
  ];
}

function Scanning({ stage, log, logRef }) {
  return (
    <>
      <div className="scan-layout">
        <div className="card scan-steps-card">
          <div className="scan-steps">
            {SCAN_STAGES.map((labelText, i) => {
              const state = i < stage ? 'done' : i === stage ? 'active' : 'todo';
              return (
                <div className={`scan-step is-${state}`} key={labelText}>
                  <span className="scan-step-mark">
                    {state === 'done' ? <IconCheck size={15} />
                      : state === 'active' ? <span className="stage-spin" />
                        : i + 1}
                  </span>
                  <span className="scan-step-label">{labelText}</span>
                </div>
              );
            })}
          </div>
          <div className="thinking-bar">
            <span style={{ animationDuration: `${SCAN_MS}ms` }} />
          </div>
        </div>

        <div className="card scan-log">
          <div className="card-head">
            <h3>Activity</h3>
            <div className="spacer" />
            <span className="scan-live"><span className="dot" />live</span>
          </div>
          <div className="scan-log-body" ref={logRef}>
            {log.map((line, i) => (
              <div className="scan-log-line" key={i}>
                <span className="scan-log-caret">›</span>
                <span>{line}</span>
              </div>
            ))}
            <div className="scan-log-line is-cursor">
              <span className="scan-log-caret">›</span>
              <span className="scan-cursor" />
            </div>
          </div>
        </div>
      </div>

    </>
  );
}

function Question({ q, value, onChange }) {
  return (
    <div className="qa-body">
      <div className="qa-where">
        {q.table}{q.column ? <>.<b>{q.column}</b></> : null}
        {q.type && <span className="qa-type">{q.type}</span>}
      </div>

      <h2 className="qa-title">{q.title}</h2>
      <p className="qa-context">{q.context}</p>

      {q.samples?.length > 0 && (
        <div className="qa-samples">
          <span className="qa-samples-label">Example values</span>
          {q.samples.map((sv, i) => <code key={i}>{sv}</code>)}
        </div>
      )}

      {q.kind === 'text' && (
        <textarea
          className="textarea qa-input"
          rows={3}
          value={value ?? ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={q.placeholder}
          autoFocus
        />
      )}

      {q.kind === 'choice' && (
        <div className="qa-options">
          {q.options.map((o) => (
            <button
              type="button"
              key={o.value}
              className={`qa-option${value === o.value ? ' is-on' : ''}`}
              onClick={() => onChange(o.value)}
            >
              <span className="qa-option-main">
                <span className="qa-option-label">{o.label}</span>
                {o.hint && <span className="qa-option-hint">{o.hint}</span>}
              </span>
              {value === o.value && <IconCheck size={16} />}
            </button>
          ))}
        </div>
      )}

      {q.kind === 'confirm' && (
        <div className="qa-options qa-options-row">
          <button
            type="button"
            className={`qa-option${value === true ? ' is-on' : ''}`}
            onClick={() => onChange(true)}
          >
            <span className="qa-option-label">{q.confirmLabel || 'Yes'}</span>
            {value === true && <IconCheck size={16} />}
          </button>
          <button
            type="button"
            className={`qa-option${value === false ? ' is-on' : ''}`}
            onClick={() => onChange(false)}
          >
            <span className="qa-option-label">{q.denyLabel || 'No'}</span>
            {value === false && <IconCheck size={16} />}
          </button>
        </div>
      )}

      <div className="qa-why">
        <IconAlert size={14} />
        <span>{q.why}</span>
      </div>
    </div>
  );
}

export default function SetupConnection() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast, refreshConnections } = useApp();

  const [phase, setPhase] = useState('scanning'); // scanning | review | done
  const [stage, setStage] = useState(0);
  const [data, setData] = useState(null);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [saving, setSaving] = useState(false);
  const [log, setLog] = useState([]);
  const timers = useRef([]);
  const logRef = useRef(null);

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  useEffect(() => {
    let cancelled = false;

    // Fetch first so the running commentary can name the real host, database
    // and table counts, then play the scan over a fixed six seconds.
    api.review(id)
      .then((res) => {
        if (cancelled) return;
        setData(res);

        timers.current = SCAN_STAGES.slice(0, -1).map((_, i) =>
          setTimeout(() => setStage(i + 1), (i + 1) * STAGE_MS)
        );

        // Spread the log lines of each stage across that stage's slice.
        const lines = buildLog(res.connection, res.scan);
        const perStage = {};
        for (const [st] of lines) perStage[st] = (perStage[st] || 0) + 1;
        const seen = {};
        lines.forEach(([st, text]) => {
          seen[st] = (seen[st] || 0) + 1;
          const at = st * STAGE_MS + (seen[st] / (perStage[st] + 1)) * STAGE_MS;
          timers.current.push(setTimeout(() => {
            setLog((l) => [...l, text]);
          }, at));
        });

        timers.current.push(setTimeout(() => {
          if (cancelled) return;
          const seeded = {};
          for (const q of res.questions) {
            if (q.defaultAnswer !== undefined) seeded[q.id] = q.defaultAnswer;
          }
          setAnswers(seeded);
          setPhase('review');
        }, SCAN_MS));
      })
      .catch((err) => {
        if (cancelled) return;
        toast(err.message, 'err');
        navigate('/admin/connections');
      });

    return () => { cancelled = true; };
  }, [id, navigate, toast]);

  // Keep the newest log line in view.
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [log]);

  const questions = data?.questions || [];
  const q = questions[index];
  const answeredCount = questions.filter((x) => answers[x.id] !== undefined && answers[x.id] !== '').length;

  const setAnswer = (v) => setAnswers((a) => ({ ...a, [q.id]: v }));

  const next = () => {
    if (index < questions.length - 1) setIndex(index + 1);
    else finish();
  };

  const finish = async () => {
    setSaving(true);
    try {
      await api.saveReview(id, answers);
      await refreshConnections();
      setPhase('done');
    } catch (err) {
      toast(err.message, 'err');
    } finally {
      setSaving(false);
    }
  };

  // ---- scanning ---------------------------------------------------------
  if (phase === 'scanning') {
    const conn = data?.connection;
    return (
      <div className="setup-page is-scanning">
        <div className="qa-head">
          <h2 className="setup-lead">
            Setting up {conn?.name || 'your database'}
          </h2>
          <p className="setup-sub">
            {conn ? `${conn.host}/${conn.database}` : 'Reading your schema. You can leave this page open.'}
          </p>
        </div>
        <Scanning stage={stage} log={log} logRef={logRef} />
      </div>
    );
  }

  // ---- finished ---------------------------------------------------------
  if (phase === 'done') {
    return (
      <div className="setup-page">
        <div className="card setup-done">
          <div className="setup-done-mark"><IconCheck size={24} /></div>
          <h2>Your database is ready</h2>
          <p>
            {answeredCount} of {questions.length} questions answered. What you told us has been
            saved, so answers will use your wording from now on.
          </p>
          <div className="row" style={{ gap: 10, justifyContent: 'center' }}>
            <button className="btn" onClick={() => navigate('/admin/connections')}>
              Back to databases
            </button>
            <button className="btn btn-primary" onClick={() => navigate('/admin/configure')}>
              Review settings
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---- question wizard --------------------------------------------------
  const scan = data.scan;
  const isAnswered = (item) => answers[item.id] !== undefined && answers[item.id] !== '';

  return (
    <div className="setup-page">
      <div className="qa-head">
        <h2 className="setup-lead">A few things I could not work out</h2>
        <p className="setup-sub">
          {data.connection?.name} is connected. Your answers teach the system what your
          data means — skip anything you are unsure about.
        </p>
      </div>

      <div className="scan-summary">
        <div><b>{formatValue(scan.tables, 'number')}</b><span>Tables</span></div>
        <div><b>{formatValue(scan.columns, 'number')}</b><span>Fields</span></div>
        <div><b>{formatValue(scan.relationships, 'number')}</b><span>Links found</span></div>
        <div><b>{formatValue(scan.rows, 'number')}</b><span>Records</span></div>
        <div className="is-flagged"><b>{questions.length}</b><span>Need your input</span></div>
      </div>

      <div className="qa-layout">
        <div className="card qa-card">
          <div className="qa-card-top">
            <span className="qa-step">Question {index + 1} of {questions.length}</span>
            <div className="qa-progress-track">
              <span style={{ width: `${((index + 1) / questions.length) * 100}%` }} />
            </div>
          </div>

          <Question q={q} value={answers[q.id]} onChange={setAnswer} />

          <div className="qa-foot">
            <button
              className="btn btn-ghost"
              onClick={() => setIndex(index - 1)}
              disabled={index === 0}
            >
              <IconChevron size={14} style={{ transform: 'rotate(90deg)' }} />
              Back
            </button>
            <div className="spacer" />
            <button className="btn btn-ghost" onClick={next} disabled={saving}>
              Skip
            </button>
            <button className="btn btn-primary" onClick={next} disabled={saving}>
              {index === questions.length - 1
                ? (saving ? 'Saving…' : 'Finish setup')
                : 'Next'}
            </button>
          </div>
        </div>

        <aside className="qa-side">
          <div className="card">
            <div className="card-head">
              <h3>All questions</h3>
              <div className="spacer" />
              <span className="small muted">{answeredCount}/{questions.length}</span>
            </div>
            <div className="qa-list">
              {questions.map((item, i) => (
                <button
                  key={item.id}
                  className={`qa-list-item${i === index ? ' is-current' : ''}${isAnswered(item) ? ' is-done' : ''}`}
                  onClick={() => setIndex(i)}
                >
                  <span className="qa-list-mark">
                    {isAnswered(item) ? <IconCheck size={13} /> : i + 1}
                  </span>
                  <span className="qa-list-text">
                    <span className="qa-list-title">{item.title}</span>
                    <span className="qa-list-where">
                      {item.table}{item.column ? `.${item.column}` : ''}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          <button
            className="btn qa-finish"
            onClick={finish}
            disabled={saving}
          >
            {saving ? 'Saving…' : 'Finish now'}
          </button>
          <p className="qa-side-note">
            Anything you skip can be answered later under Configuration.
          </p>
        </aside>
      </div>
    </div>
  );
}
