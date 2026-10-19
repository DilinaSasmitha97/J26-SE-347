import React, { useEffect, useRef, useState } from 'react';
import { ResultChart } from './PresentationResult.jsx';
import { SummaryView, cellText } from './DataPresentation.jsx';

const VERDICT_TONE = { READY: 'ok', READY_WITH_WARNING: 'warn', NOT_REQUESTED: '' };
const PERIODS = { DAY: 'days', WEEK: 'weeks', MONTH: 'months', QUARTER: 'quarters', YEAR: 'years', HOUR: 'hours' };
const words = (value) => String(value || '').replaceAll('_', ' ').toLowerCase();
const capitalised = (value) => { const text = words(value); return text.charAt(0).toUpperCase() + text.slice(1); };

function ForecastChartView({ data }) {
  const { forecast, chart, chart_reason: chartReason, mode } = data;
  return (
    <>
      {mode === 'FORECAST' && !forecast.generated && !data.strategy_result?.executed && (
        <div className="dp-unavailable" role="note"><strong>No forecast was produced.</strong><p>{forecast.skipped_reason || data.readiness.reason}</p></div>
      )}
      {chart ? <ResultChart spec={chart.spec} /> : <p className="pl-muted">{chartReason}</p>}
      {chart && forecast.generated && <p className="pl-muted">Solid line: history · dashed line: forecast · shaded band: {Math.round(forecast.confidence_level * 100)}% prediction range{data.anomalies.evaluated ? ' · triangles: anomalies' : ''}.</p>}
      {chart && !forecast.generated && data.anomalies.evaluated && <p className="pl-muted">Line: history · triangles: anomalies.</p>}
    </>
  );
}

function ForecastTableView({ forecast }) {
  if (!forecast.generated) return <div className="dp-unavailable" role="note"><strong>No forecast was produced.</strong><p>{forecast.skipped_reason}</p></div>;
  return (
    <>
      <div className="pl-table-wrap">
        <table className="pl-data-table" aria-label="Forecast table">
          <thead><tr><th>Period</th><th className="dp-num">Prediction</th><th className="dp-num">Lower bound</th><th className="dp-num">Upper bound</th></tr></thead>
          <tbody>{forecast.points.map((point) => (
            <tr key={point.label}><td>{point.label}</td><td className="dp-num">{cellText(point.predicted)}</td>
              <td className="dp-num">{cellText(point.lower_bound)}</td><td className="dp-num">{cellText(point.upper_bound)}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <p className="pl-muted">{Math.round(forecast.confidence_level * 100)}% prediction range. The range widens with each period ahead.</p>
    </>
  );
}

function AnomalyList({ title, items }) {
  if (!items.length) return null;
  return (
    <div className="pr-anomalies">
      <h4>{title}</h4>
      <ul>{items.map((item, index) => (
        <li key={`${item.label}-${index}`}>
          <strong>{item.label}</strong>: {cellText(item.value)} · {words(item.direction)} · {words(item.severity)}
          <small> · detected by {(item.detected_by || []).join(' + ') || 'threshold'}{item.z_score ? ` · z = ${cellText(item.z_score)}` : ''}</small>
        </li>
      ))}</ul>
    </div>
  );
}

function AnomaliesView({ anomalies }) {
  if (!anomalies.evaluated) return <div className="dp-unavailable" role="note"><strong>Anomalies were not checked.</strong><p>{anomalies.skipped_reason}</p></div>;
  const historical = anomalies.historical_anomalies || [];
  const predicted = anomalies.predictive_warnings || [];
  return (
    <div aria-label="Anomalies">
      <p>Method: IQR fence and Z-score ({anomalies.volatility_regime?.toLowerCase()} series, IQR × {cellText(anomalies.iqr_multiplier)}, |z| ≥ {cellText(anomalies.z_threshold)}
        {anomalies.detrended ? ', measured around the trend' : ''}{anomalies.seasonal ? ', after removing seasonality' : ''}).</p>
      {!historical.length && !predicted.length && <p>No anomalies found.</p>}
      <AnomalyList title="Historical anomalies" items={historical} />
      <AnomalyList title="Predicted threshold breaches" items={predicted} />
    </div>
  );
}

function MethodView({ data }) {
  const { readiness, strategy, model, forecast, horizon } = data;
  const periods = PERIODS[forecast.granularity] || 'periods';
  return (
    <dl className="pl-facts pr-method" aria-label="Readiness and method">
      <div><dt>Readiness</dt><dd><span className={`pl-chip ${VERDICT_TONE[readiness.verdict] ?? 'bad'}`}>{words(readiness.verdict)}</span> {readiness.reason}</dd></div>
      {readiness.warnings?.length > 0 && <div><dt>Warnings</dt><dd>{readiness.warnings.map((w, i) => <span key={i}>{typeof w === 'string' ? w : w.message}</span>)}</dd></div>}
      <div><dt>Strategy</dt><dd>{words(strategy.strategy)}: {strategy.rationale}</dd></div>
      {forecast.generated && <div><dt>Model</dt><dd>{words(forecast.model)}: {forecast.model_reason || model.reason}</dd></div>}
      <div><dt>Horizon</dt><dd>{forecast.generated ? `${forecast.horizon} ${periods}` : `${horizon.value} periods`} ({horizon.source === 'EXPLICIT' ? 'from your question' : 'default'})</dd></div>
      {readiness.checks?.length > 0 && <div><dt>Checks</dt><dd><details><summary>{readiness.checks.length} readiness checks</summary><ul>{readiness.checks.map((c, i) => <li key={i}>{c}</li>)}</ul></details></dd></div>}
    </dl>
  );
}

/**
 * The prediction layer: confidence-bounded forecast, readiness, anomalies and
 * a verified unified summary, shown below the Results card.
 */
export default function PredictionCard({ status, data, error, onRetry }) {
  const [active, setActive] = useState(0);
  const tabs = useRef([]);
  useEffect(() => { setActive(0); }, [data]);
  if (status === 'idle') return null;
  if (status === 'loading') {
    return <section className="pl-result-card dp-card pr-card" aria-label="Prediction"><div className="pl-loading"><span className="spinner" /> Checking readiness and forecasting…</div></section>;
  }
  if (status === 'error') {
    return (
      <section className="pl-result-card dp-card pr-card is-fail" aria-label="Prediction">
        <div className="pl-result-head"><h3>Prediction</h3></div>
        <p className="pl-error-text" role="alert">{error}</p>
        {onRetry && <button type="button" className="pl-ghost" onClick={onRetry}>Retry prediction</button>}
      </section>
    );
  }

  const forecastMode = data.mode === 'FORECAST';
  const views = [
    { id: 'chart', label: forecastMode ? 'Forecast' : 'Anomaly chart', body: <ForecastChartView data={data} /> },
    ...(forecastMode ? [{ id: 'table', label: 'Forecast table', body: <ForecastTableView forecast={data.forecast} /> }] : []),
    { id: 'anomalies', label: 'Anomalies', body: <AnomaliesView anomalies={data.anomalies} /> },
    { id: 'method', label: 'Readiness & method', body: <MethodView data={data} /> },
    { id: 'summary', label: 'Summary', body: <SummaryView block={data.summary} /> }
  ];
  const select = (index) => { const next = (index + views.length) % views.length; setActive(next); tabs.current[next]?.focus(); };
  const onKeyDown = (event) => {
    const moves = { ArrowRight: active + 1, ArrowLeft: active - 1, Home: 0, End: views.length - 1 };
    if (event.key in moves) { event.preventDefault(); select(moves[event.key]); }
  };
  const verdict = data.readiness.verdict;
  const tone = VERDICT_TONE[verdict] ?? 'bad';
  const periods = PERIODS[data.forecast.granularity] || 'periods';

  return (
    <section className={`pl-result-card dp-card pr-card ${tone === 'bad' ? 'is-fail' : 'is-pass'}`} aria-label="Prediction">
      <div className="pl-result-head">
        <h3>{forecastMode ? 'Prediction' : 'Anomaly check'}
          {forecastMode && data.forecast.generated && <> · {data.forecast.horizon} {periods} ahead</>}</h3>
        <span className={`pl-chip ${tone}`} aria-label="Readiness">{forecastMode ? capitalised(verdict) : 'History only'}</span>
      </div>
      {forecastMode && data.forecast.generated && <p className="pl-muted">Model: {words(data.forecast.model)} · strategy: {words(data.strategy.strategy)}</p>}
      <div className="dp-tabs" role="tablist" aria-label="Prediction views" onKeyDown={onKeyDown}>
        {views.map((view, index) => (
          <button key={view.id} ref={(element) => { tabs.current[index] = element; }} type="button" role="tab"
            id={`pr-tab-${view.id}`} aria-controls={`pr-panel-${view.id}`} aria-selected={index === active}
            tabIndex={index === active ? 0 : -1} className="dp-tab" onClick={() => setActive(index)}>{view.label}</button>
        ))}
      </div>
      <div className="dp-panel" role="tabpanel" id={`pr-panel-${views[active].id}`} aria-labelledby={`pr-tab-${views[active].id}`}>
        {views[active].body}
      </div>
    </section>
  );
}
