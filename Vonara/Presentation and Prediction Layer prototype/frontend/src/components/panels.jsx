// The tabbed panels under the response blocks: anomalies (Stage 5), the
// interactive what-if (Stage 6), the claim trace behind every number, and
// the auditable reasoning the component records for each decision.

import { useRef, useState } from "react";
import { fmt, humanize, modelName, pct } from "../format.js";
import { ChartBlock, Tile, verificationText } from "./blocks.jsx";
import Icon from "./icons.jsx";

// ---------------------------------------------------------------------------
// Tabs (WAI-ARIA tabs pattern; panels stay mounted so a what-if result
// survives switching tabs)
// ---------------------------------------------------------------------------

export function Tabs({ tabs, active, onChange, label }) {
  const refs = useRef({});
  const enabled = tabs.filter((t) => !t.disabled);
  function onKeyDown(e) {
    const i = enabled.findIndex((t) => t.id === active);
    let next = null;
    if (e.key === "ArrowRight") next = enabled[(i + 1) % enabled.length];
    if (e.key === "ArrowLeft") next = enabled[(i - 1 + enabled.length) % enabled.length];
    if (e.key === "Home") next = enabled[0];
    if (e.key === "End") next = enabled[enabled.length - 1];
    if (next) {
      e.preventDefault();
      onChange(next.id);
      refs.current[next.id]?.focus();
    }
  }
  return (
    <div className="tabs" role="tablist" aria-label={label} onKeyDown={onKeyDown}>
      {tabs.map((t) => (
        <button
          key={t.id}
          ref={(el) => (refs.current[t.id] = el)}
          type="button"
          role="tab"
          id={`tab-${t.id}`}
          className="tab"
          aria-selected={active === t.id}
          aria-controls={`panel-${t.id}`}
          tabIndex={active === t.id ? 0 : -1}
          disabled={t.disabled}
          title={t.disabled ? t.disabledReason : undefined}
          onClick={() => onChange(t.id)}
        >
          <Icon name={t.icon} size={15} />
          {t.label}
          {t.count !== undefined && <span className="tab-count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function TabPanel({ id, active, children }) {
  return (
    <div className="tab-panel" role="tabpanel" id={`panel-${id}`} aria-labelledby={`tab-${id}`} hidden={active !== id}>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Anomalies
// ---------------------------------------------------------------------------

const PATTERN_TEXT = {
  SPIKE: "one-off spike",
  SUSTAINED: "lasting shift",
  UNCONFIRMED: "latest period, too early to tell",
};

// Where the check ran decides what "unusual" means: against the season's
// usual level, against the trend, or against the series' plain spread.
const DIRECTION_TEXT = {
  seasonal: { HIGH: "above its seasonal norm", LOW: "below its seasonal norm" },
  detrended: { HIGH: "above the trend", LOW: "below the trend" },
  plain: { HIGH: "unusually high", LOW: "unusually low" },
};

const METHOD_TEXT = {
  seasonal: "after removing the seasonal pattern",
  detrended: "after removing the trend",
  plain: "against the series' own spread",
};

export function AnomalyPanel({ anomaly }) {
  if (!anomaly) return <p className="muted">No anomaly check for this result.</p>;
  if (!anomaly.evaluated) {
    return (
      <p className="muted" aria-label="Anomalies">
        Anomaly check not run{anomaly.skipped_reason ? `: ${anomaly.skipped_reason}` : "."}
      </p>
    );
  }
  const items = [
    ...(anomaly.historical_anomalies || []).map((a) => ({ ...a, when: "past" })),
    ...(anomaly.predictive_warnings || []).map((a) => ({ ...a, when: "forecast" })),
  ];
  const space = anomaly.seasonal ? "seasonal" : anomaly.detrended ? "detrended" : "plain";
  // Forecast points may be screened in a different space (anomaly.py falls
  // back from seasonal when the forecast model is not seasonal).
  const forecastSpace = { SEASONAL: "seasonal", DETRENDED: "detrended", RAW: "plain" }[anomaly.predictive_space] || space;
  return (
    <section aria-label="Anomalies">
      {items.length === 0 ? (
        <div className="notice notice-good">
          <Icon name="check" size={18} />
          <div>
            <strong>Nothing unusual</strong>
            No value, past or forecast, is outside the normal range.
          </div>
        </div>
      ) : (
        <ul className="anomaly-list">
          {items.map((a, i) => (
            <li className="anomaly" key={i}>
              <span className="anomaly-mark" aria-hidden="true">
                <Icon name={a.direction === "HIGH" ? "arrowUp" : "arrowDown"} size={16} />
              </span>
              <div style={{ minWidth: 0 }}>
                <div className="anomaly-title">
                  {a.label} · {DIRECTION_TEXT[a.when === "forecast" ? forecastSpace : space][a.direction]}{" "}
                  {a.when === "forecast" && <span className="badge-forecast">Forecast</span>}
                </div>
                <div className="anomaly-sub">
                  {a.when === "forecast" ? "projected to leave the normal range" : PATTERN_TEXT[a.pattern] || "outlier"}
                  {" · "}found by {(a.detected_by || []).map((d) => (d === "ZSCORE" ? "Z-score" : d)).join(" + ")}
                </div>
              </div>
              <div>
                <div className="anomaly-value">{fmt(a.value)}</div>
                <div className={`severity severity-${a.severity}`} style={{ textAlign: "right" }}>
                  {a.severity === "SEVERE" ? "Severe" : "Moderate"}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <p className="muted" style={{ fontSize: 12.5, margin: "12px 0 0" }}>
        Normal range set {METHOD_TEXT[space]} ({anomaly.volatility_regime?.toLowerCase()} volatility, IQR ×
        {anomaly.iqr_multiplier} and |z| &gt; {anomaly.z_threshold}).
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// What-if
// ---------------------------------------------------------------------------

const PRESETS = ["cut spending by 10%", "increase by 15%", "gradually reduce by 20%", "double it"];

/** The slider's setting in words the backend's scenario parser accepts. */
export function sliderScenario(change, gradual) {
  if (!change) return "";
  return `${gradual ? "gradually " : ""}${change < 0 ? "reduce" : "increase"} by ${Math.abs(change)}%`;
}

export function WhatIfPanel({ onSimulate, embed }) {
  const [change, setChange] = useState(-10);
  const [gradual, setGradual] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function run(scenario) {
    const value = (scenario ?? text).trim();
    if (!value) return;
    setText(value);
    setBusy(true);
    setError("");
    try {
      setResult(await onSimulate(value));
    } catch (err) {
      setError(err.message);
      setResult(null);
    } finally {
      setBusy(false);
    }
  }

  const sc = result && result.scenario;
  return (
    <section aria-label="What-if scenario">
      <div className="whatif-grid">
        <div>
          <p className="eyebrow">Adjust the forecast</p>
          <div className="slider-row">
            <input
              type="range"
              min={-50}
              max={50}
              step={5}
              value={change}
              aria-label="Change to the forecast"
              aria-valuetext={`${change}%`}
              onChange={(e) => setChange(Number(e.target.value))}
            />
            <span className="slider-value">
              {pct(change)}
            </span>
          </div>
          <label className="check">
            <input type="checkbox" checked={gradual} onChange={(e) => setGradual(e.target.checked)} />
            Phase in gradually
          </label>
          <div style={{ marginTop: 12 }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || change === 0}
              onClick={() => run(sliderScenario(change, gradual))}
            >
              <Icon name="sliders" size={15} />
              {busy ? "Simulating…" : "Run scenario"}
            </button>
          </div>
        </div>
        <div>
          <p className="eyebrow">Or describe it</p>
          <form
            className="field"
            onSubmit={(e) => {
              e.preventDefault();
              run();
            }}
          >
            <label className="sr-only" htmlFor="whatif">Scenario</label>
            <input
              id="whatif"
              type="text"
              value={text}
              placeholder="e.g. what if we cut spending by 20%"
              onChange={(e) => setText(e.target.value)}
            />
            <button className="btn" type="submit" disabled={busy || !text.trim()}>
              Simulate
            </button>
          </form>
          <div className="suggestions">
            {PRESETS.map((p) => (
              <button key={p} type="button" className="suggestion" onClick={() => run(p)} disabled={busy}>
                {p}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <div className="notice notice-critical" role="alert" style={{ marginTop: 14 }}>
          <Icon name="x" size={18} />
          <div>{error}</div>
        </div>
      )}
      {sc && !sc.simulated && (
        <div className="notice notice-warning" role="status" style={{ marginTop: 14 }}>
          <Icon name="alert" size={18} />
          <div>
            <strong>Scenario not simulated</strong>
            {sc.skipped_reason}
          </div>
        </div>
      )}
      {sc && sc.simulated && (
        <div style={{ marginTop: 16 }}>
          <div className="scenario-tiles" aria-label="Scenario result">
            <Tile label="Forecast total, as is" value={fmt(sc.baseline_total)} />
            <Tile label="With the scenario" value={fmt(sc.scenario_total)} />
            <Tile
              label="Difference"
              value={`${sc.total_delta < 0 ? "−" : "+"}${fmt(Math.abs(sc.total_delta))}`}
              icon={sc.total_delta < 0 ? "arrowDown" : "arrowUp"}
              note={`${pct(sc.total_delta_pct)} over the forecast`}
            />
          </div>
          {result.visualization && (
            <ChartBlock
              visualization={result.visualization}
              embed={embed}
              title="Forecast with the scenario"
              subtitle={sc.spec.parse_note}
            />
          )}
          {result.summary && result.summary.claims && (
            <details style={{ marginTop: 12 }}>
              <summary className="muted" style={{ cursor: "pointer", fontSize: 13 }}>
                Scenario claims
              </summary>
              <ClaimList claims={result.summary.claims.filter((c) => c.dimension === "SCENARIO")} />
            </details>
          )}
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Show the working: every claim the summary may cite, grouped
// ---------------------------------------------------------------------------

const DIMENSIONS = [
  ["HISTORICAL", "From the data"],
  ["ANOMALY", "Anomaly check"],
  ["PREDICTIVE", "Forecast"],
  ["SCENARIO", "Scenario"],
];

function ClaimList({ claims }) {
  return (
    <ul className="claims">
      {claims.map((c) => (
        <li key={c.claim_id}>
          <span className="claim-id">{c.claim_id}</span>
          <span className="claim-text">
            {c.text}
            {(c.derivation || c.source) && (
              <span className="claim-derivation">
                {c.derivation}
                {c.derivation && c.source ? " · " : ""}
                {c.source ? `from ${c.source}` : ""}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function WorkingPanel({ summary }) {
  const claims = (summary && summary.claims) || [];
  if (!claims.length) return <p className="muted">No claims were computed for this result.</p>;
  return (
    <section aria-label="Claim trace">
      <div className="insight-meta" style={{ marginTop: 0, marginBottom: 6 }}>
        <Icon name={summary.verification?.passed === false ? "alert" : "check"} size={14} />
        {claims.length} claims, each computed from the data or the model
        {summary.verification ? ` · ${verificationText(summary)}` : ""}
      </div>
      {DIMENSIONS.map(([dim, title]) => {
        const group = claims.filter((c) => c.dimension === dim);
        if (!group.length) return null;
        return (
          <div key={dim} style={{ marginTop: 12 }}>
            <div className="claim-dim">{title.toUpperCase()}</div>
            <ClaimList claims={group} />
          </div>
        );
      })}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Details: why this view
// ---------------------------------------------------------------------------

export const SHAPE_LABEL = {
  SINGLE_ANSWER: "Single answer",
  SHORT_SUMMARY: "Summary",
  TABLE_CONTENT: "Table",
  CHART: "Chart",
  MIXED_SUMMARY: "Report",
};

function Detail({ icon, title, children }) {
  return (
    <div className="detail">
      <h4>
        <Icon name={icon} size={14} />
        {title}
      </h4>
      {children}
    </div>
  );
}

export function DetailsPanel({ envelope }) {
  const a = envelope.analysis || {};
  const ri = (envelope.response && envelope.response.response_intent) || {};
  const pred = envelope.prediction || {};
  const readiness = pred.stage_2_readiness || {};
  const model = pred.stage_3_model_selection || {};
  const masked = (envelope.input && envelope.input.masked_columns) || {};
  const trigger = a.prediction_request?.prediction_trigger;
  const decision = readiness.decision || readiness.verdict;
  return (
    <section className="detail-grid" aria-label="Why this view">
      <Detail icon="search" title="Question type">
        <p>
          {humanize((a.intent?.primary_intent || "").toLowerCase())} ·{" "}
          {Math.round((a.intent?.confidence || 0) * 100)}% ({(a.intent?.intent_source || "").toLowerCase()})
        </p>
        <p className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>{a.intent?.rationale}</p>
      </Detail>
      <Detail icon="layers" title="Answer shape">
        <p>
          {SHAPE_LABEL[ri.intent] || ri.intent} · {Math.round((ri.confidence || 0) * 100)}%
          {ri.original_intent && ri.original_intent !== ri.intent
            ? ` (changed from ${SHAPE_LABEL[ri.original_intent] || ri.original_intent})`
            : ""}
        </p>
        {ri.guardrails_applied && ri.guardrails_applied.length > 0 && (
          <p className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
            Checked against the data: {ri.guardrails_applied.join("; ")}
          </p>
        )}
      </Detail>
      <Detail icon="trend" title="Forecast">
        <p>
          {trigger === "NONE" ? "Not asked for" : humanize((trigger || "").toLowerCase())}
          {decision ? ` · readiness ${decision.replaceAll("_", " ").toLowerCase()}` : ""}
          {model.model && model.model !== "NONE" ? ` · ${modelName(model.model)}` : ""}
        </p>
        {readiness.reason_codes && readiness.reason_codes.length > 0 && (
          <p className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>{readiness.reason_codes.join(", ")}</p>
        )}
      </Detail>
      <Detail icon="lock" title="Privacy">
        <p>
          {Object.keys(masked).length
            ? `Masked by Member 2: ${Object.entries(masked).map(([c, t]) => `${c} (${t})`).join(", ")}`
            : "No masked columns in this result"}
        </p>
      </Detail>
      <Detail icon="clock" title="Served">
        <p>
          {envelope.cache?.hit ? "From the tenant's cache" : "Computed"} in{" "}
          {Math.round(envelope.profiling?.total_execution_ms ?? 0)} ms · pipeline {envelope.pipeline_version}
        </p>
      </Detail>
    </section>
  );
}
