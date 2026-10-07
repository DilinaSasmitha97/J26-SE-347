import { useEffect, useRef, useState } from "react";
import { fetchRows, health, listDatasets, present, simulate } from "./api.js";
import ResponseView from "./components/ResponseView.jsx";
import Icon, { BrandMark } from "./components/icons.jsx";

const THEMES = [
  ["system", "monitor", "System"],
  ["light", "sun", "Light"],
  ["dark", "moon", "Dark"],
];

function ThemeSwitch() {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("c4-theme") || "system";
    } catch {
      return "system";
    }
  });
  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("c4-theme", theme);
    } catch {
      // storage unavailable: the choice lasts for this page only
    }
  }, [theme]);
  return (
    <div className="segmented" role="group" aria-label="Theme">
      {THEMES.map(([id, icon, label]) => (
        <button key={id} type="button" aria-pressed={theme === id} onClick={() => setTheme(id)} title={label}>
          <Icon name={icon} size={14} />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}

function StatusPill({ status }) {
  if (!status) return null;
  const up = status.status === "UP";
  const mode = status.llm_available ? `LLM ${status.llm_provider}` : "rules only";
  return (
    <span className="status-pill" title={up ? `Pipeline ${status.pipeline_version}, ${status.active_model}` : status.error}>
      <span className={`status-dot ${up ? "" : "off"}`} aria-hidden="true" />
      <span className="status-label">{up ? "API online" : "API offline"}</span>
      {up && <span className="status-text muted">· v{status.pipeline_version} · {mode}</span>}
    </span>
  );
}

function SourceList({ datasets, active, onChoose }) {
  const groups = [];
  for (const d of datasets) {
    const group = d.group || "Data";
    let g = groups.find((x) => x.name === group);
    if (!g) groups.push((g = { name: group, items: [] }));
    g.items.push(d);
  }
  return (
    <section className="card card-pad" aria-label="Data sources">
      {groups.map((g) => (
        <div className="source-group" key={g.name}>
          <p className="eyebrow">{g.name}</p>
          <div className="source-list">
            {g.items.map((d) => (
              <button
                key={d.id}
                type="button"
                className="source"
                aria-pressed={active?.id === d.id}
                onClick={() => onChoose(d)}
              >
                <span className="source-icon">
                  <Icon name={d.kind || "database"} size={16} />
                </span>
                <span style={{ minWidth: 0 }}>
                  <span className="source-title">{d.title}</span>
                  <span className="source-note">{d.note}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </section>
  );
}

function Provenance({ source }) {
  if (!source) return null;
  const m2 = source.member2_result;
  const masked = (m2.masking && m2.masking.columns) || [];
  return (
    <section className="card card-pad provenance" aria-label="Data received">
      <p className="eyebrow">What Member 2 sent</p>
      <dl>
        <dt>Tenant</dt>
        <dd>{source.security_context.tenant_id}</dd>
        <dt>Rows</dt>
        <dd>
          {m2.rowCount}
          {m2.truncated ? " (truncated)" : ""}
        </dd>
        <dt>Columns</dt>
        <dd>{m2.columns.map((c) => c.name).join(", ")}</dd>
        <dt>Masked</dt>
        <dd>
          {masked.length
            ? masked.map((c) => (
                <span key={c.name} className="tag tag-lock" style={{ margin: "0 4px 4px 0" }}>
                  <Icon name="lock" size={11} />
                  {c.name} · {c.piiType}
                </span>
              ))
            : "none"}
        </dd>
      </dl>
      <details>
        <summary>SQL (stand-in for Member 1)</summary>
        <pre className="code">{source.sql}</pre>
      </details>
    </section>
  );
}

function Welcome({ dataset }) {
  return (
    <section className="card welcome" aria-label="Welcome">
      <h2>Ask a question about {dataset ? dataset.title.toLowerCase() : "your data"}</h2>
      <p>
        The result arrives already secured and masked by the other components. This layer decides how to show
        it, forecasts when it is asked to and the data supports it, flags unusual values and explains every
        number it states.
      </p>
      <div className="features">
        <div className="feature">
          <Icon name="layers" size={18} />
          <div>
            <strong>The right shape</strong>
            A single figure, a table, a chart or a short report.
          </div>
        </div>
        <div className="feature">
          <Icon name="trend" size={18} />
          <div>
            <strong>Forecasts with ranges</strong>
            Only when the history is long and regular enough.
          </div>
        </div>
        <div className="feature">
          <Icon name="alert" size={18} />
          <div>
            <strong>Unusual values</strong>
            Past outliers and projected breaches, marked on the chart.
          </div>
        </div>
        <div className="feature">
          <Icon name="check" size={18} />
          <div>
            <strong>Checked numbers</strong>
            Every number in a summary traces to a computed claim.
          </div>
        </div>
      </div>
    </section>
  );
}

function Loading() {
  return (
    <div className="stack" aria-busy="true" aria-label="Loading result">
      <div className="skeleton" style={{ height: 22, width: "45%" }} />
      <div className="kpis">
        {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 84 }} />)}
      </div>
      <div className="skeleton" style={{ height: 340 }} />
    </div>
  );
}

export default function App() {
  const [status, setStatus] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [active, setActive] = useState(null);
  const [source, setSource] = useState(null);
  const [question, setQuestion] = useState("");
  const [envelope, setEnvelope] = useState(null);
  const [asked, setAsked] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef(null);

  useEffect(() => {
    health()
      .then(setStatus)
      .catch((err) => setStatus({ status: "DOWN", error: err.message }));
    listDatasets()
      .then((d) => {
        setDatasets(d.datasets);
        if (d.datasets.length) choose(d.datasets[0]);
      })
      .catch((err) => setError(`Could not load data sources: ${err.message}`));
    // "/" jumps to the question box, as in most search-first tools.
    const onKey = (e) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || "");
      if (e.key === "/" && !typing) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function choose(dataset) {
    setActive(dataset);
    setEnvelope(null);
    setError("");
    setQuestion(dataset.examples[0] || "");
    try {
      setSource(await fetchRows(dataset.id));
    } catch (err) {
      setSource(null);
      setError(err.message);
    }
  }

  async function ask(text) {
    const q = (text ?? question).trim();
    if (!q || !source) return;
    setQuestion(q);
    setBusy(true);
    setError("");
    try {
      setEnvelope(await present(q, source));
      setAsked(q);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <BrandMark />
            <div style={{ minWidth: 0 }}>
              <div className="brand-name">Presentation &amp; Prediction</div>
              <div className="brand-sub">Component 4 · J26-SE-347</div>
            </div>
          </div>
          <div className="topbar-spacer" />
          <StatusPill status={status} />
          {source && (
            <span className="status-pill tenant-pill" title="Tenant of the current result">
              <Icon name="shield" size={13} />
              {source.security_context.tenant_id}
            </span>
          )}
          <ThemeSwitch />
        </div>
      </header>

      <div className="shell">
        <aside className="sidebar">
          <SourceList datasets={datasets} active={active} onChoose={choose} />
          <Provenance source={source} />
        </aside>

        <main className="stack">
          <section className="card composer" aria-label="Ask">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ask();
              }}
            >
              <div className="composer-row">
                <Icon name="search" size={18} />
                <label className="sr-only" htmlFor="question">Question</label>
                <input
                  id="question"
                  ref={input}
                  value={question}
                  autoComplete="off"
                  placeholder="Ask about this data, e.g. show monthly expenses and predict the next 3 months"
                  onChange={(e) => setQuestion(e.target.value)}
                />
                <button className="btn btn-primary" type="submit" disabled={busy || !source || !question.trim()}>
                  {busy ? "Working…" : "Ask"}
                </button>
              </div>
            </form>
            {active && active.examples.length > 0 && (
              <div className="suggestions" aria-label="Example questions">
                {active.examples.map((ex) => (
                  <button key={ex} type="button" className="suggestion" onClick={() => ask(ex)} disabled={busy}>
                    {ex}
                  </button>
                ))}
              </div>
            )}
          </section>

          {error && (
            <div className="notice notice-critical" role="alert">
              <Icon name="x" size={18} />
              <div>
                <strong>Something went wrong</strong>
                {error}
              </div>
            </div>
          )}
          {busy && <Loading />}
          {!busy && !envelope && !error && <Welcome dataset={active} />}
          {!busy && envelope && (
            <ResponseView
              key={asked}
              envelope={envelope}
              question={asked}
              onSimulate={(scenario) => simulate(asked, source, scenario)}
            />
          )}
        </main>
      </div>
    </>
  );
}
