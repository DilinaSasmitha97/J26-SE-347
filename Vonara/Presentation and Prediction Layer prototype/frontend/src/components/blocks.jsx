// The four response blocks the component emits (response.blocks_emitted):
// ANSWER, SUMMARY, TABLE, CHART - plus the forecast notice that accompanies
// any explicitly requested forecast, and the key figures drawn from the
// summary's claims. Each renders only what the API sent; no number is
// computed here.

import { useEffect, useMemo, useRef, useState } from "react";
import { compact, fmt, humanize, modelName, pct } from "../format.js";
import { chartKey, chartTitle, currentMode, themeSpec } from "../theme.js";
import Icon from "./icons.jsx";

export function AnswerCard({ answer }) {
  if (!answer) return null;
  return (
    <section className="card answer" aria-label="Answer">
      <div className="answer-label">
        {answer.label}
        {answer.is_forecast && <span className="badge-forecast">Forecast</span>}
      </div>
      <div className="answer-value">{answer.display_value}</div>
      {answer.qualifier && (
        <div className="answer-qualifier">
          {answer.qualifier_label ? `${answer.qualifier_label}: ` : ""}
          {answer.qualifier}
        </div>
      )}
      {answer.interval && (
        <div className="answer-range">
          {Math.round((answer.interval.confidence_level || 0.95) * 100)}% range: {answer.interval.display}
          {answer.model ? ` · ${modelName(answer.model)}` : ""}
        </div>
      )}
    </section>
  );
}

export function verificationText(summary) {
  const v = summary && summary.verification;
  if (!v) return "";
  if (!v.passed) return "Verification failed: a number could not be traced to a claim";
  return `${v.verified} of ${v.numbers_in_summary} numbers traced to a computed claim`;
}

export function SummaryBlock({ summary, envelopeSummary }) {
  if (!summary) return null;
  return (
    <section className="card insight" aria-label="Summary">
      <p className="eyebrow">Summary</p>
      <p className="insight-text">{summary.text}</p>
      <div className="insight-meta">
        <Icon name={envelopeSummary?.verification?.passed === false ? "alert" : "check"} size={14} />
        {summary.mode === "LLM_VERIFIED" ? "Written by the LLM, every number checked" : "Written from computed claims"}
        {envelopeSummary?.verification ? ` · ${verificationText(envelopeSummary)}` : ""}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Key figures: stat tiles taken from the summary's claims (H = history,
// F = forecast). The tile shows the claim's value; the note quotes the
// claim's own wording or supporting values.
// ---------------------------------------------------------------------------

function claimOf(claims, kind) {
  return claims.find((c) => c.kind === kind);
}

function quote(text, pattern) {
  const m = text && text.match(pattern);
  return m ? m[1] : "";
}

export function Tile({ label, value, full, note, tone, icon, forecast }) {
  return (
    <div className={`card kpi ${forecast ? "kpi-forecast" : ""}`}>
      <div className="kpi-label">
        {label}
        {forecast && <span className="badge-forecast">Forecast</span>}
      </div>
      <div className={`kpi-value ${tone || ""}`} title={full}>
        {icon && <Icon name={icon} size={18} className="kpi-icon" />}
        {value}
      </div>
      {note && <div className="kpi-note" title={note}>{note}</div>}
    </div>
  );
}

export function KeyFigures({ envelope }) {
  const claims = envelope?.summary?.claims || [];
  const forecast = envelope?.prediction?.stage_4_forecast || {};
  const total = claimOf(claims, "TOTAL");
  if (!total) return null;
  const tiles = [];
  tiles.push(
    <Tile key="total" label="Total" value={compact(total.value)} full={fmt(total.value)} note={total.derivation} />,
  );

  const change = claimOf(claims, "CHANGE");
  const changeTile = change && (
    <Tile
      key="change"
      label="Change, first to last"
      value={pct(change.value)}
      icon={change.value > 0 ? "arrowUp" : change.value < 0 ? "arrowDown" : null}
      note={quote(change.text, /from ([\d.,]*\d[KMB]? to [\d.,]*\d[KMB]?)/).replace(" to ", " → ")}
    />
  );

  const next = claims.find((c) => c.kind === "FORECAST");
  if (forecast.generated && next) {
    if (changeTile) tiles.push(changeTile);
    const [lo, hi] = next.supporting_values || [];
    const level = Math.round((forecast.confidence_level || 0.95) * 100);
    tiles.push(
      <Tile
        key="next"
        forecast
        label={quote(next.text, /for (.+?) is projected/) || "Next period"}
        value={compact(next.value)}
        full={fmt(next.value)}
        note={lo !== undefined && hi !== undefined ? `${level}% range ${fmt(lo)} – ${fmt(hi)}` : ""}
      />,
    );
    const horizon = claimOf(claims, "FORECAST_TOTAL");
    const fit = claimOf(claims, "MODEL_FIT");
    if (horizon) {
      tiles.push(
        <Tile
          key="horizon"
          forecast
          label={`Next ${forecast.horizon} ${forecast.horizon === 1 ? "period" : "periods"}, total`}
          value={compact(horizon.value)}
          full={fmt(horizon.value)}
          note={`${modelName(forecast.model)}${fit ? ` · typical error ${fit.value.toFixed(1)}%` : ""}`}
        />,
      );
    }
  } else {
    const mean = claimOf(claims, "MEAN");
    const peak = claimOf(claims, "PEAK");
    const spread = claimOf(claims, "DISPERSION");
    if (mean) {
      tiles.push(
        <Tile key="mean" label="Average" value={compact(mean.value)} full={fmt(mean.value)}
          note={spread ? `standard deviation ${fmt(spread.value)}` : ""} />,
      );
    }
    if (peak) {
      const when = quote(peak.text, /\bat ([^,]+),/);
      tiles.push(
        <Tile key="peak" label="Highest" value={compact(peak.value)} full={fmt(peak.value)}
          note={when ? `at ${when}` : ""} />,
      );
    }
    if (changeTile) tiles.push(changeTile);
  }
  return (
    <section className="kpis" aria-label="Key figures">
      {tiles}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Table
// ---------------------------------------------------------------------------

function isNumberColumn(col) {
  return col.type === "number" || col.role === "MEASURE";
}

export function TableBlock({ table, maskedColumns = {} }) {
  if (!table) return null;
  const columns = table.columns || [];
  const rows = table.rows || [];
  const maskedHere = columns.filter((c) => maskedColumns[c.name]);
  return (
    <section className="card" aria-label="Table">
      <div className="card-head" style={{ paddingBottom: 12 }}>
        <div>
          <h3 className="card-title">Rows</h3>
          <p className="card-sub">
            {table.rows_returned ?? rows.length} of {table.row_count ?? rows.length}
            {table.truncated ? " (truncated)" : ""}
            {table.forecast_rows ? ` · ${table.forecast_rows} forecast rows in italics` : ""}
          </p>
        </div>
        {maskedHere.length > 0 && (
          <span className="tag tag-lock">
            <Icon name="lock" size={12} />
            {maskedHere.length} masked {maskedHere.length === 1 ? "column" : "columns"}
          </span>
        )}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.name} scope="col" className={isNumberColumn(c) ? "num" : ""}>
                  {c.label || c.name}
                  {maskedColumns[c.name] && (
                    <span title={`Masked by Member 2 (${maskedColumns[c.name]})`} style={{ marginLeft: 4 }}>
                      <Icon name="lock" size={11} className="inline-icon" />
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={row.row_type === "FORECAST" ? "forecast-row" : ""}>
                {columns.map((c) => {
                  const v = row[c.name];
                  const num = typeof v === "number";
                  return (
                    <td key={c.name} className={`${num || isNumberColumn(c) ? "num" : ""} ${maskedColumns[c.name] ? "masked" : ""}`}>
                      {v === null || v === undefined ? "—" : num ? fmt(v) : String(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.limit_note && <div className="table-foot">{table.limit_note}</div>}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Chart
// ---------------------------------------------------------------------------

function KeySwatch({ item }) {
  const common = { width: 22, height: 10, "aria-hidden": true };
  if (item.style === "triangle") {
    return (
      <svg {...common} viewBox="0 0 22 10">
        <polygon points="11,0 18,10 4,10" fill={item.color} />
      </svg>
    );
  }
  if (item.style === "diamond") {
    return (
      <svg {...common} viewBox="0 0 22 10">
        <polygon points="11,0 16,5 11,10 6,5" fill={item.color} />
      </svg>
    );
  }
  if (item.style === "band") {
    return (
      <svg {...common} viewBox="0 0 22 10">
        <rect x="0" y="1" width="22" height="8" rx="2" fill={item.color} opacity="0.25" />
      </svg>
    );
  }
  const dash = { dashed: "6 4", dotted: "2 3", rule: "3 3" }[item.style];
  return (
    <svg {...common} viewBox="0 0 22 10">
      <line x1="0" y1="5" x2="22" y2="5" stroke={item.color} strokeWidth="2" strokeDasharray={dash} />
    </svg>
  );
}

/** Data rows of a Vega-Lite spec (top level or first layer), for the table view. */
function specRows(spec) {
  if (!spec) return [];
  if (spec.data && Array.isArray(spec.data.values)) return spec.data.values;
  for (const layer of spec.layer || []) {
    if (layer.data && Array.isArray(layer.data.values)) return layer.data.values;
  }
  return [];
}

function useColorMode() {
  const [mode, setMode] = useState(currentMode());
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => setMode(currentMode());
    mq.addEventListener?.("change", update);
    const observer = new MutationObserver(update);
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      mq.removeEventListener?.("change", update);
      observer.disconnect();
    };
  }, []);
  return mode;
}

export function ChartBlock({ chart, visualization, embed, title, subtitle, fill = false }) {
  const host = useRef(null);
  const [tableChosen, setAsTable] = useState(false);
  const mode = useColorMode();
  const spec = chart?.spec || visualization;
  const meta = useMemo(
    () => (visualization && visualization._meta) || (spec && spec._meta) || {},
    [visualization, spec],
  );
  // A spec with no mark (the backend's data-grid contract) has nothing for
  // Vega to draw: show its rows as a table.
  const gridOnly = meta.render_as === "data_grid" || (spec && !spec.mark && !spec.layer);
  const asTable = tableChosen || gridOnly;
  const themed = useMemo(() => (spec ? themeSpec(spec, mode, meta, { fillHeight: fill }) : null),
    [spec, mode, meta, fill]);
  const key = meta.extension_rules_applied && meta.extension_rules_applied.length ? chartKey(meta, mode, spec) : [];

  useEffect(() => {
    if (!themed || asTable || !host.current) return undefined;
    let view = null;
    let cancelled = false;
    const run = embed || ((el, s, o) => import("vega-embed").then((m) => m.default(el, s, o)));
    Promise.resolve(run(host.current, themed, { actions: false, renderer: "svg", tooltip: true }))
      .then((result) => {
        view = result && result.view;
        if (cancelled && view) view.finalize();
      })
      .catch((err) => {
        if (host.current) host.current.textContent = `Chart could not be drawn: ${err.message}`;
      });
    return () => {
      cancelled = true;
      if (view) view.finalize();
    };
  }, [themed, asTable, embed]);

  if (!spec) return null;
  const rows = specRows(spec);
  const cols = rows.length ? Object.keys(rows[0]) : [];
  const name = title || chartTitle(meta);
  return (
    <section className={`card${fill ? " chart-fill" : ""}`} aria-label={`Chart: ${chart?.chart_type || meta.chart_type || ""}`}>
      <div className="card-head">
        <div>
          <h3 className="card-title">{name}</h3>
          <p className="card-sub">{subtitle ?? (chart?.rationale || meta.selection_reason || "")}</p>
        </div>
        {!gridOnly && <div className="segmented" role="group" aria-label="View">
          <button type="button" aria-pressed={!asTable} onClick={() => setAsTable(false)}>
            <Icon name={meta.chart_type === "bar" ? "bar" : "trend"} size={14} />
            Chart
          </button>
          <button type="button" aria-pressed={asTable} onClick={() => setAsTable(true)}>
            <Icon name="table" size={14} />
            Table
          </button>
        </div>}
      </div>
      {key.length > 0 && !asTable && (
        <ul className="chart-key" aria-label="Chart key">
          {key.map((item) => (
            <li key={item.label}>
              <KeySwatch item={item} />
              {item.label}
            </li>
          ))}
        </ul>
      )}
      {asTable ? (
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead>
              <tr>
                {cols.map((c) => (
                  <th key={c} scope="col" className={typeof rows[0][c] === "number" ? "num" : ""}>
                    {humanize(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  {cols.map((c) => (
                    <td key={c} className={typeof r[c] === "number" ? "num" : ""}>
                      {typeof r[c] === "number" ? fmt(r[c]) : String(r[c] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="chart-body">
          <div className="vega-host" ref={host} data-testid="vega-host" />
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Forecast notice
// ---------------------------------------------------------------------------

export function ForecastNotice({ notice }) {
  if (!notice || !notice.requested) return null;
  const shown = notice.status === "SHOWN";
  const warned = shown && notice.warnings && notice.warnings.length > 0;
  const tone = !shown ? "critical" : warned ? "warning" : "good";
  const icon = !shown ? "x" : warned ? "alert" : "check";
  const periods = `${notice.horizon} ${notice.horizon === 1 ? "period" : "periods"} ahead`;
  const byDefault = notice.horizon_source === "DEFAULT" ? " (default)" : "";
  const title = !shown
    ? "Forecast not shown"
    : warned
      ? "Forecast shown, with cautions"
      : `Forecast shown${notice.model ? ` · ${modelName(notice.model)}, ${periods}${byDefault}` : ""}`;
  // Notes are facts about how the forecast was made (shortened horizon, model
  // fallback, range cut at zero); cautions are readiness warnings.
  const items = [...(warned ? notice.warnings : []), ...(shown ? notice.notes || [] : [])];
  return (
    <div className={`notice notice-${tone}`} role="status">
      <Icon name={icon} size={18} />
      <div>
        <strong>{title}</strong>
        {notice.message && <div>{notice.message}</div>}
        {items.length > 0 && (
          <ul>
            {items.map((w) => <li key={w.code}>{w.message}</li>)}
          </ul>
        )}
      </div>
    </div>
  );
}
