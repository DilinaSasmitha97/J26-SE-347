// The admin console: its shell (sidebar + header) and its pages: Dashboard,
// Data sources (list and detail), Configuration (the forecasting policy in
// force) and Activity. Every figure comes from the API (/api/v4/health,
// /demo/datasets, /demo/rows, /demo/policy) or from this browser's activity log.
// Each page fills the window; long content scrolls inside its own card.

import { useEffect, useState } from "react";
import { clearActivity, timeAgo, useActivity } from "./activity.js";
import { fetchRows, policy as fetchPolicy } from "./api.js";
import Icon, { BrandMark } from "./components/icons.jsx";
import { SHAPE_LABEL } from "./components/panels.jsx";
import { humanize } from "./format.js";
import { go, href } from "./router.js";

const count = (n) => Number(n || 0).toLocaleString();

export const KIND_LABEL = {
  trend: "Time series", bar: "Breakdown", distribution: "Distribution",
  scatter: "Relationship", table: "Records", figure: "Single figure",
};

const NAV = [
  ["dashboard", "Dashboard", "grid", "/admin"],
  ["sources", "Data sources", "database", "/admin/sources"],
  ["configuration", "Configuration", "gear", "/admin/configuration"],
  ["activity", "Activity", "history", "/admin/activity"],
];

// ---------------------------------------------------------------------------
// Shell
// ---------------------------------------------------------------------------

export function ApiBadge({ status }) {
  const up = status?.status === "UP";
  return (
    <span className="badge-api" title={up ? "Prediction API online" : status ? "Prediction API offline" : "Checking the API"}>
      C4
      <span className={`presence ${status && !up ? "off" : ""}`} aria-hidden="true" />
    </span>
  );
}

function Who({ status }) {
  const up = status?.status === "UP";
  const mode = status?.llm_available ? `LLM ${status.llm_provider}` : "rules only";
  return (
    <div className="row">
      <div className="who">
        <strong>Prediction API</strong>
        <span>{!status ? "checking…" : up ? `online · v${status.pipeline_version} · ${mode}` : "offline"}</span>
      </div>
      <ApiBadge status={status} />
    </div>
  );
}

export function AppShell({ page, title, subtitle, status, theme, onToggleTheme, children }) {
  return (
    <div className="app">
      <aside className="sidebar" aria-label="Navigation">
        <div className="sidebar-brand">
          <span className="brand-tile"><BrandMark size={20} /></span>
          <div>
            <strong>Presentation &amp; Prediction</strong>
            <small>Admin console</small>
          </div>
        </div>
        <div className="nav-label">Administration</div>
        <nav className="nav">
          {NAV.map(([id, label, icon, path]) => (
            <a key={id} className="nav-item" href={href(path)} aria-current={page === id ? "page" : undefined}>
              <Icon name={icon} size={18} />
              {label}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <a className="nav-item" href={href("/ask")} target="_blank" rel="noreferrer">
            <Icon name="sparkle" size={18} />
            Open the user app
          </a>
          <button type="button" className="nav-item" onClick={onToggleTheme}>
            <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
            {theme === "dark" ? "Light mode" : "Dark mode"}
          </button>
        </div>
        <div className="sidebar-foot">
          <ApiBadge status={status} />
          <div>
            <strong>Prediction API</strong>
            <small>{status?.status === "UP" ? `online · v${status.pipeline_version}` : status ? "offline" : "checking…"}</small>
          </div>
        </div>
      </aside>
      <div className="content">
        <header className="page-head">
          <div>
            <h1>{title}</h1>
            <p>{subtitle}</p>
          </div>
          <div className="spacer" />
          <Who status={status} />
        </header>
        <main className="page-body">{children}</main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

function Stat({ label, value, note, small }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value${small ? " sm" : ""}`}>{value}</div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  );
}

function headline(entry) {
  if (entry.headline) return entry.headline;
  if (entry.forecast === "REFUSED") return "Forecast refused";
  if (entry.forecast === "SHOWN") return "Forecast shown";
  return SHAPE_LABEL[entry.shape] || entry.shape;
}

function SourceCell({ d, sub }) {
  return (
    <div className="row">
      <span className="type-badge"><Icon name={d.kind || "database"} size={16} /></span>
      <div style={{ minWidth: 0 }}>
        <span className="cell-title">{d.title}</span>
        <span className="cell-sub">{sub}</span>
      </div>
    </div>
  );
}

export function DashboardPage({ datasets, status, loadError }) {
  const activity = useActivity();
  const records = datasets.reduce((n, d) => n + (d.row_count || 0), 0);
  const tenants = new Set(datasets.map((d) => d.tenant)).size;
  const groups = new Set(datasets.map((d) => d.group)).size;
  const avgMs = activity.length ? Math.round(activity.reduce((n, a) => n + a.ms, 0) / activity.length) : 0;
  const shown = activity.filter((a) => a.forecast === "SHOWN").length;
  const refused = activity.filter((a) => a.forecast === "REFUSED").length;
  const down = status && status.status !== "UP";

  return (
    <>
      <section className="card stats" aria-label="Workspace summary">
        <Stat label="Data sources" value={datasets.length} note={`${tenants} tenants · ${groups} groups`} />
        <Stat label="Records available" value={count(records)} note="ready to be asked about" />
        <Stat label="Questions asked" value={activity.length}
          note={activity.length ? `answered in ${avgMs} ms on average` : "none yet in this browser"} />
        <Stat label="Forecasts" value={shown + refused}
          note={shown + refused ? `${shown} shown · ${refused} refused` : "none requested yet"} />
      </section>

      {(down || loadError) && (
        <section className="card banner" role="status">
          <Icon name="alert" size={18} />
          <div>
            <strong>{down ? "The prediction API is offline" : "Data sources could not be loaded"}</strong>
            {" — "}
            {down ? "no question can be answered until it is back." : loadError}
          </div>
          <div className="spacer" />
          <button type="button" className="btn" onClick={() => window.location.reload()}>Retry</button>
        </section>
      )}

      <div className="split split-2 fill">
        <section className="card pane" aria-label="Data sources overview">
          <div className="card-head ruled">
            <h2 className="card-title">Data sources</h2>
            <a className="btn" href={href("/admin/sources")}>View all</a>
          </div>
          <div className="scroll">
            <table>
              <thead>
                <tr><th scope="col">Name</th><th scope="col">Status</th><th scope="col" className="num">Records</th></tr>
              </thead>
              <tbody>
                {datasets.map((d) => (
                  <tr key={d.id} className="clickable" onClick={() => go(`/admin/sources/${d.id}`)}>
                    <td><SourceCell d={d} sub={`${d.tenant} · ${KIND_LABEL[d.kind] || d.group}`} /></td>
                    <td><span className="status"><span className="dot" />Online</span></td>
                    <td className="num">{count(d.row_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="card pane" aria-label="Recent questions">
          <div className="card-head ruled">
            <h2 className="card-title">Recent questions</h2>
            <a href={href("/admin/activity")}>View all</a>
          </div>
          <div className="scroll">
            {activity.length === 0 ? (
              <div className="empty">No questions yet. <a href={href("/ask")}>Ask one</a>.</div>
            ) : (
              <ul className="claims" style={{ padding: "2px 20px" }}>
                {activity.slice(0, 20).map((a) => (
                  <li key={a.at} style={{ gridTemplateColumns: "1fr auto", padding: "12px 0" }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontSize: 14 }}>{a.question}</div>
                      <div className="muted" style={{ fontSize: 12.5 }}>{a.source} · {timeAgo(a.at)}</div>
                    </div>
                    <div style={{ fontWeight: 650, whiteSpace: "nowrap" }}>{headline(a)}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Data sources
// ---------------------------------------------------------------------------

export function SourcesPage({ datasets }) {
  const groups = [...new Set(datasets.map((d) => d.group))];
  return (
    <section className="card pane fill" aria-label="All data sources">
      <div className="card-head ruled">
        <div>
          <h2 className="card-title">All data sources</h2>
          <p className="card-sub">Each is a result set the security layer returns, masked, for one tenant</p>
        </div>
        <span className="count">{datasets.length} sources</span>
      </div>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Name</th><th scope="col">Tenant</th><th scope="col">Status</th>
              <th scope="col">Privacy</th><th scope="col" className="num">Columns</th><th scope="col" className="num">Records</th>
            </tr>
          </thead>
          {groups.map((group) => (
            <tbody key={group} aria-label={group}>
              <tr className="group-row"><td colSpan={6}>{group}</td></tr>
              {datasets.filter((d) => d.group === group).map((d) => (
                <tr key={d.id} className="clickable" onClick={() => go(`/admin/sources/${d.id}`)}>
                  <td><SourceCell d={d} sub={d.note} /></td>
                  <td className="mono">{d.tenant}</td>
                  <td><span className="status"><span className="dot" />Online</span></td>
                  <td>
                    {(d.masked || []).length
                      ? <span className="tag tag-lock"><Icon name="lock" size={11} />{d.masked.length} masked</span>
                      : <span className="muted">no personal data</span>}
                  </td>
                  <td className="num">{(d.columns || []).length}</td>
                  <td className="num">{count(d.row_count)}</td>
                </tr>
              ))}
            </tbody>
          ))}
        </table>
      </div>
    </section>
  );
}

function columnKind(values) {
  const present = values.filter((v) => v !== null && v !== undefined && v !== "");
  if (!present.length) return "empty";
  if (present.every((v) => !Number.isNaN(Number(v)))) return "number";
  if (present.every((v) => /^\d{4}-\d{2}(-\d{2})?/.test(String(v)))) return "date";
  return "text";
}

export function SourceDetailPage({ dataset }) {
  const [payload, setPayload] = useState(null);
  const [check, setCheck] = useState(null);
  const [error, setError] = useState("");

  async function load(isTest) {
    const started = performance.now();
    setError("");
    try {
      const data = await fetchRows(dataset.id);
      setPayload(data);
      if (isTest) setCheck(`Responded in ${Math.round(performance.now() - started)} ms with ${data.member2_result.rowCount} rows`);
    } catch (err) {
      setError(err.message);
      setCheck(null);
    }
  }
  useEffect(() => {
    setPayload(null);
    setCheck(null);
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataset.id]);

  const m2 = payload?.member2_result;
  const names = m2 ? m2.columns.map((c) => c.name) : dataset.columns || [];
  const masked = Object.fromEntries((dataset.masked || []).map((m) => [m.name, m.pii_type]));
  const rows = m2 ? m2.rows : [];

  return (
    <>
      <div className="row" style={{ flex: "none" }}>
        <a className="btn-link" href={href("/admin/sources")}>
          <Icon name="chevronLeft" size={16} /> Back to data sources
        </a>
      </div>
      <section className="card" aria-label="Data source" style={{ flex: "none" }}>
        <div className="card-pad row" style={{ gap: 14, flexWrap: "wrap" }}>
          <span className="type-badge lg"><Icon name={dataset.kind || "database"} size={22} /></span>
          <div style={{ minWidth: 0 }}>
            <div className="row" style={{ flexWrap: "wrap" }}>
              <h2 className="card-title" style={{ fontSize: 19 }}>{dataset.title}</h2>
              <span className="pill-online"><span className="dot" />online</span>
            </div>
            <div className="mono muted" style={{ fontSize: 12.5, marginTop: 2 }}>{dataset.tenant} · {dataset.note}</div>
          </div>
          <div className="spacer" />
          {check && <span className="tag tag-green"><Icon name="check" size={12} />{check}</span>}
          {error && <span className="tag tag-lock"><Icon name="alert" size={12} />{error}</span>}
          <button type="button" className="btn" onClick={() => load(true)}>
            <Icon name="refresh" size={15} /> Test connection
          </button>
          <a className="btn btn-primary" href={href(`/ask/${dataset.id}`)}>
            <Icon name="sparkle" size={15} /> Ask about this
          </a>
        </div>
        <div className="stats bordered">
          <Stat label="Type" value={KIND_LABEL[dataset.kind] || dataset.group} small />
          <Stat label="Arrives from" value="Member 2 (stand-in)" small />
          <Stat label="Privacy" value={Object.keys(masked).length ? `${Object.keys(masked).length} masked` : "None"} small />
          <Stat label="Columns" value={names.length} small />
          <Stat label="Records" value={count(dataset.row_count)} small />
          <Stat label="Tenant" value={<span className="mono">{dataset.tenant}</span>} small />
        </div>
      </section>

      <div className="split split-2 fill">
        <section className="card pane" aria-label="Fields">
          <div className="card-head ruled">
            <h2 className="card-title">Fields</h2>
            <span className="muted" style={{ fontSize: 13 }}>Select a field for sample values</span>
          </div>
          <div className="scroll">
            <div className="xlist">
              {names.map((name, i) => {
                const values = rows.map((r) => r[i]);
                const kind = columnKind(values);
                const sample = [...new Set(values.filter((v) => v !== null))].slice(0, 5);
                return (
                  <details className="xitem" key={name}>
                    <summary>
                      <Icon name="chevronRight" size={16} className="chev" />
                      <span className="xitem-name">{name}</span>
                      <span className="xitem-desc">
                        {masked[name] ? `Masked by Member 2 (${masked[name].toLowerCase()})` : `${kind} values`}
                      </span>
                      <span className="spacer" />
                      {masked[name] && <span className="tag tag-lock"><Icon name="lock" size={11} />masked</span>}
                      <span className="count">{kind}</span>
                    </summary>
                    <div className="xitem-body">
                      {payload ? <>Sample: <span className="mono">{sample.map(String).join(" · ") || "—"}</span></> : "Loading…"}
                    </div>
                  </details>
                );
              })}
            </div>
          </div>
        </section>

        <div className="pane" style={{ gap: 16 }}>
          <section className="card pane fill" aria-label="Sample records">
            <div className="card-head ruled">
              <h2 className="card-title">Sample records</h2>
              <span className="muted" style={{ fontSize: 13 }}>
                {m2 ? `First ${Math.min(50, rows.length)} of ${m2.rowCount}, as Member 2 sends them` : "Loading…"}
              </span>
            </div>
            <div className="scroll">
              {m2 && (
                <table>
                  <thead><tr>{names.map((n) => <th key={n} scope="col">{n}</th>)}</tr></thead>
                  <tbody>
                    {rows.slice(0, 50).map((r, i) => (
                      <tr key={i}>
                        {r.map((v, j) => (
                          <td key={j} className={masked[names[j]] ? "masked" : ""}>{v === null ? "—" : String(v)}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </section>
          <section className="card" aria-label="Query" style={{ flex: "none" }}>
            <div className="card-head ruled">
              <h2 className="card-title">Query</h2>
              <span className="muted" style={{ fontSize: 13 }}>Fixed SQL standing in for Member 1</span>
            </div>
            <div className="card-pad"><pre className="code">{dataset.sql}</pre></div>
          </section>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Configuration: the forecasting policy in force
// ---------------------------------------------------------------------------

const pct = (v) => `${Math.round(v * 100)}%`;
const READINESS = [
  ["refuse_truncated_input", "Refuse a truncated result", (v) => (v ? "Yes" : "No — warn only"),
    "A result cut at the security layer's row limit may be missing its latest periods."],
  ["min_points_any", "Minimum history", (v) => `${v} periods`, "Below this, no forecast at all."],
  ["min_points_trend", "History for a trend model", (v) => `${v} periods`, "Below this, a weighted moving average is used."],
  ["min_points_seasonal", "History for SARIMA", (v) => `${v} periods`, "Two full seasonal cycles at monthly granularity."],
  ["max_missing_value_ratio", "Unreadable values allowed", pct, "Above this share of unreadable values, no forecast."],
  ["max_missing_period_ratio", "Empty periods allowed", pct, "Fewer are filled in and disclosed; more refuse the forecast."],
  ["min_points_signal_test", "History for the noise test", (v) => `${v} periods`, "Shorter series are forecast with a caution."],
  ["signal_test_origins", "Noise test: past points re-forecast", (v) => `${v}`, "Each is forecast from the data before it."],
  ["conflict_noise_limit", "Unstable-series limit", (v) => (v == null ? "Off" : pct(v)),
    "Refuse when ADF and KPSS disagree and the in-history error is above this."],
  ["near_constant_cv", "Near-constant below", pct, "Variation under this share of the level gets a caution."],
  ["min_points_stationarity", "History for ADF / KPSS", (v) => `${v} periods`, "The stationarity tests have no power below this."],
  ["holidays", "Holidays", (v) => (v && v.length ? `${v.length} dates` : "None configured"), "Not counted as missing trading days."],
];
const FORECAST = [
  ["guard_sarima", "SARIMA must beat the benchmarks", (v) => (v ? "Yes" : "No"),
    "Every model must beat naive / seasonal naive on the series' own history."],
  ["fitted_smoothing_min_points", "Fitted smoothing from", (v) => (v ? `${v} periods` : "Off"),
    "Damped Holt estimates its constants on longer histories."],
  ["band_method", "Range method", (v) => humanize(v), "How the 95% range is built from the residuals."],
  ["clip_non_negative", "Ranges cut at zero", (v) => (v ? "Yes" : "No"), "For measures that have never been negative."],
  ["sarima_timeout_seconds", "SARIMA time limit", (v) => `${v} s`, "Over it, damped Holt is used instead."],
  ["max_horizon", "Longest forecast", (v) => `${v} periods`, "Also never more than half the history."],
];

function PolicyCard({ title, sub, rows, values, grow }) {
  return (
    <section className={`card pane${grow ? " fill" : ""}`} aria-label={title} style={grow ? undefined : { flex: "none" }}>
      <div className="card-head ruled">
        <div>
          <h2 className="card-title">{title}</h2>
          <p className="card-sub">{sub}</p>
        </div>
      </div>
      <div className="scroll">
        <div className="kv">
          {rows.filter(([key]) => key in values).map(([key, label, show, why]) => (
            <div key={key} style={{ display: "contents" }}>
              <div className="k">{label}<span className="why mono">{key}</span></div>
              <div className="v"><span className="mono">{show(values[key])}</span><span className="why">{why}</span></div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function ConfigurationPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetchPolicy().then(setData).catch((err) => setError(err.message));
  }, []);
  if (error) return <section className="card banner"><Icon name="alert" size={18} />{error}</section>;
  if (!data) return <div className="skeleton fill" />;
  const limits = data.readiness.max_expected_error || {};
  return (
    <>
      <section className="card banner" aria-label="Policy version">
        <Icon name="info" size={18} />
        <div>
          Policy <span className="mono">{data.version}</span> from <span className="mono">{data.file}</span> is in force.
          {" "}Edit the file and restart the server to change it, then re-run the benchmarks.
        </div>
      </section>
      <div className="split split-2 fill">
        <PolicyCard title="Readiness" sub="When a forecast may be made at all" rows={READINESS} values={data.readiness} grow />
        <div className="pane" style={{ gap: 16 }}>
          <PolicyCard title="Forecasting" sub="How the forecast and its range are made" rows={FORECAST}
            values={data.forecast} grow />
          <section className="card" aria-label="Noise limits" style={{ flex: "none" }}>
            <div className="card-head ruled">
              <div>
                <h2 className="card-title">Noise limit by granularity</h2>
                <p className="card-sub">Refuse when a simple forecast missed by more than this on the series' own history</p>
              </div>
            </div>
            <div className="row" style={{ flexWrap: "wrap", gap: 8, padding: "12px 20px" }}>
              {Object.entries(limits).filter(([k]) => !k.startsWith("_")).map(([k, v]) => (
                <span key={k} className="count">
                  {k === "default" ? "Default" : humanize(k.toLowerCase())} <span className="mono">{pct(v)}</span>
                </span>
              ))}
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Activity
// ---------------------------------------------------------------------------

export function ActivityPage() {
  const activity = useActivity();
  return (
    <section className="card pane fill" aria-label="Activity log">
      <div className="card-head ruled">
        <div>
          <h2 className="card-title">Questions asked</h2>
          <p className="card-sub">In this browser only: the API keeps no history.</p>
        </div>
        <button type="button" className="btn btn-danger" onClick={clearActivity} disabled={!activity.length}>
          Clear
        </button>
      </div>
      <div className="scroll">
        {activity.length === 0 ? (
          <div className="empty">Nothing yet. <a href={href("/ask")}>Ask a question</a> and it appears here.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Question</th><th scope="col">Answer shape</th><th scope="col">Forecast</th>
                <th scope="col">Result</th><th scope="col" className="num">Time</th><th scope="col">When</th>
              </tr>
            </thead>
            <tbody>
              {activity.map((a) => (
                <tr key={a.at} className="clickable" onClick={() => go(`/ask/${a.sourceId}`)}>
                  <td style={{ whiteSpace: "normal", minWidth: 260 }}>
                    <span className="cell-title">{a.question}</span>
                    <span className="cell-sub">{a.source}</span>
                  </td>
                  <td>{SHAPE_LABEL[a.shape] || a.shape}</td>
                  <td>
                    {a.forecast === "SHOWN" && <span className="tag tag-green">shown</span>}
                    {a.forecast === "REFUSED" && <span className="tag tag-lock">refused</span>}
                    {!a.forecast && <span className="muted">—</span>}
                  </td>
                  <td>{a.headline || "—"}</td>
                  <td className="num">{a.ms} ms{a.cached ? " · cached" : ""}</td>
                  <td className="muted">{timeAgo(a.at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}
