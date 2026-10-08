import { useEffect, useRef, useState } from "react";
import { record } from "./activity.js";
import { fetchRows, health, listDatasets, present, simulate } from "./api.js";
import ResponseView from "./components/ResponseView.jsx";
import Icon, { BrandMark } from "./components/icons.jsx";
import {
  ActivityPage, AppShell, ConfigurationPage, DashboardPage, SourceDetailPage, SourcesPage,
} from "./console.jsx";
import { go, href, useRoute } from "./router.js";

// ---------------------------------------------------------------------------
// Theme: system by default; the sidebar toggle stores an explicit choice.
// ---------------------------------------------------------------------------

function systemDark() {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

function useTheme() {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("c4-theme") || (systemDark() ? "dark" : "light");
    } catch {
      return systemDark() ? "dark" : "light";
    }
  });
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("c4-theme", theme);
    } catch {
      // storage unavailable: the choice lasts for this page only
    }
  }, [theme]);
  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))];
}

// ---------------------------------------------------------------------------
// Ask
// ---------------------------------------------------------------------------

function Loading() {
  return (
    <div className="workspace" aria-busy="true" aria-label="Loading result">
      <div className="ws-main">
        <div className="skeleton" style={{ height: 22, width: "45%", flex: "none" }} />
        <div className="kpis">
          {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 74 }} />)}
        </div>
        <div className="skeleton" style={{ flex: 1, minHeight: 240 }} />
      </div>
      <div className="ws-side"><div className="skeleton" style={{ flex: 1 }} /></div>
    </div>
  );
}

const CAPABILITIES = [
  ["layers", "The right shape", "A figure, a table, a chart or a short report."],
  ["trend", "Forecasts with ranges", "Only when the history supports one."],
  ["alert", "Unusual values", "Past outliers and projected breaches."],
  ["check", "Checked numbers", "Every number traces to a computed claim."],
];

function AskPage({ datasets, sourceId, loadError }) {
  const active = datasets.find((d) => d.id === sourceId) || datasets[0] || null;
  const [source, setSource] = useState(null);
  const [question, setQuestion] = useState("");
  const [envelope, setEnvelope] = useState(null);
  const [asked, setAsked] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const input = useRef(null);

  useEffect(() => {
    if (!active) return;
    setEnvelope(null);
    setError("");
    setQuestion("");
    setSource(null);
    fetchRows(active.id).then(setSource).catch((err) => setError(err.message));
  }, [active?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
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
  }, []);

  async function ask(text) {
    const q = (text ?? question).trim();
    if (!q || !source) return;
    setQuestion(q);
    setBusy(true);
    setError("");
    try {
      const result = await present(q, source);
      setEnvelope(result);
      setAsked(q);
      record(q, active, result);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const title = active ? active.title : "your data";
  const started = Boolean(envelope || busy);

  const picker = datasets.length > 0 && (
    <label className="source-select" htmlFor="source">
      <Icon name="database" size={16} />
      <span className="sr-only">Data source</span>
      <select id="source" value={active?.id || ""} onChange={(e) => go(`/ask/${e.target.value}`)}>
        {[...new Set(datasets.map((d) => d.group))].map((group) => (
          <optgroup key={group} label={group}>
            {datasets.filter((d) => d.group === group).map((d) => (
              <option key={d.id} value={d.id}>{d.title}</option>
            ))}
          </optgroup>
        ))}
      </select>
    </label>
  );
  const box = (
    <form
      className="ask-box"
      onSubmit={(e) => {
        e.preventDefault();
        ask();
      }}
    >
      <Icon name="search" size={18} />
      <label className="sr-only" htmlFor="question">Question</label>
      <input
        id="question"
        ref={input}
        value={question}
        autoComplete="off"
        placeholder={`Ask about ${title}...`}
        onChange={(e) => setQuestion(e.target.value)}
      />
      <button className="send" type="submit" aria-label="Ask" disabled={busy || !source || !question.trim()}>
        <Icon name="arrowRight" size={18} />
      </button>
    </form>
  );
  const problem = (error || loadError) && (
    <div className="notice notice-critical" role="alert">
      <Icon name="x" size={18} />
      <div>
        <strong>Something went wrong</strong>
        {error || loadError}
      </div>
    </div>
  );

  if (!started) {
    // Before the first question: everything centred, as a search page.
    return (
      <section className="ask-empty" aria-label="Start">
        <span className="brand-tile lg"><BrandMark size={34} /></span>
        <h2>Ask {title} a question</h2>
        <p>
          Answers come from the secured, masked result. You get the right kind of answer, a forecast when the
          history supports one, and every number is checked.
        </p>
        <div className="ask-bar ask-bar-hero">
          {picker}
          {box}
        </div>
        {problem}
        {active && active.examples.length > 0 && (
          <div className="chips" aria-label="Example questions">
            {active.examples.map((ex) => (
              <button key={ex} type="button" className="chip" onClick={() => ask(ex)} disabled={busy || !source}>
                {ex}
              </button>
            ))}
          </div>
        )}
        <div className="capabilities">
          {CAPABILITIES.map(([icon, head, text]) => (
            <div className="capability" key={head}>
              <strong><Icon name={icon} size={15} />{head}</strong>
              {text}
            </div>
          ))}
        </div>
      </section>
    );
  }

  // After a question: the box moves to the top; the result fills the window.
  return (
    <>
      <div className="ask-bar">
        {picker}
        {box}
      </div>
      {problem}
      {busy && <Loading />}
      {!busy && envelope && (
        <ResponseView
          key={asked}
          envelope={envelope}
          question={asked}
          layout="workspace"
          onSimulate={(scenario) => simulate(asked, source, scenario)}
        />
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// The user-facing app: brand and status only, no administration
// ---------------------------------------------------------------------------

function UserApp({ status, theme, onToggleTheme, children }) {
  const up = status?.status === "UP";
  return (
    <div className="user-app">
      <header className="user-top">
        <a className="user-brand" href={href("/ask")}>
          <span className="brand-tile"><BrandMark size={20} /></span>
          <span>Presentation &amp; Prediction</span>
        </a>
        <div className="spacer" />
        <button type="button" className="icon-btn" onClick={onToggleTheme}
          title={theme === "dark" ? "Light mode" : "Dark mode"}>
          <Icon name={theme === "dark" ? "sun" : "moon"} size={17} />
          <span className="sr-only">{theme === "dark" ? "Light mode" : "Dark mode"}</span>
        </button>
        <span className="status" title={up ? "The service is available" : status ? "The service is unavailable" : ""}>
          <span className={`dot ${status && !up ? "off" : ""}`} aria-hidden="true" />
          {!status ? "Connecting…" : up ? "Online" : "Offline"}
        </span>
      </header>
      <main className="user-body">{children}</main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// App: #/ask is the user app; #/admin/... is the console
// ---------------------------------------------------------------------------

const PAGES = {
  dashboard: ["Dashboard", "Health and usage across your workspace"],
  sources: ["Data sources", "Result sets users can ask questions about"],
  configuration: ["Configuration", "The forecasting policy in force"],
  activity: ["Activity", "Questions asked from this browser"],
};

export default function App() {
  const route = useRoute();
  const [theme, toggleTheme] = useTheme();
  const [status, setStatus] = useState(null);
  const [datasets, setDatasets] = useState([]);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    health().then(setStatus).catch((err) => setStatus({ status: "DOWN", error: err.message }));
    listDatasets()
      .then((d) => setDatasets(d.datasets))
      .catch((err) => setLoadError(`Could not load data sources: ${err.message}`));
  }, []);

  if (route.area === "ask") {
    return (
      <UserApp status={status} theme={theme} onToggleTheme={toggleTheme}>
        <AskPage datasets={datasets} sourceId={route.id} loadError={loadError} />
      </UserApp>
    );
  }

  const page = PAGES[route.page] ? route.page : "dashboard";
  const detail = page === "sources" && route.id ? datasets.find((d) => d.id === route.id) : null;
  const [title, subtitle] = detail ? ["Data source", "What it holds and how it arrives"] : PAGES[page];
  return (
    <AppShell page={page} title={title} subtitle={subtitle} status={status} theme={theme} onToggleTheme={toggleTheme}>
      {page === "dashboard" && <DashboardPage datasets={datasets} status={status} loadError={loadError} />}
      {page === "sources" && !route.id && <SourcesPage datasets={datasets} />}
      {page === "sources" && route.id && (detail ? <SourceDetailPage dataset={detail} />
        : datasets.length ? (
          <section className="card empty">
            No data source called <span className="mono">{route.id}</span>.{" "}
            <a href={href("/admin/sources")}>See all data sources</a>
          </section>
        ) : <div className="skeleton fill" />)}
      {page === "configuration" && <ConfigurationPage />}
      {page === "activity" && <ActivityPage />}
    </AppShell>
  );
}
