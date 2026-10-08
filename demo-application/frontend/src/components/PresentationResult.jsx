import React, { useEffect, useRef, useState } from 'react';
import './presentation.css';

const label = (value) => String(value || '').replaceAll('_', ' ').toLowerCase();
const cell = (value) => value == null ? '—' : typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value);

export function IntentPreview({ analysis, status }) {
  if (!analysis) return status === 'UNAVAILABLE' ? <p className="pl-muted">Intent analysis is unavailable; SQL generation used the original question and policy.</p> : null;
  return <div className="vp-intent" aria-label="Question understanding">
    <span className="pl-chip">{label(analysis.intent?.primary_intent)}</span>
    <span className="pl-chip">Response: {label(analysis.response_intent?.intent)}</span>
    {analysis.prediction_request?.prediction_required && <span className="pl-chip">Prediction requested</span>}
    {analysis.semantic_roles?.limit_source === 'INFERRED' && <p className="pl-muted">Suggested limit: {analysis.semantic_roles.limit} (inferred default).</p>}
  </div>;
}

export function ResultChart({ spec }) {
  const element = useRef(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let disposed = false, view;
    setError('');
    if (!spec || spec._meta?.chart_type === 'none') return undefined;
    const { _meta, ...grammar } = spec;
    import('vega-embed').then(({ default: embed }) => {
      if (disposed) return null;
      return embed(element.current, grammar, { actions: false, renderer: 'svg' });
    }).then((result) => {
      if (!result) return;
      view = result.view;
      if (disposed) view.finalize();
    }).catch(() => { if (!disposed) setError('The chart could not be displayed. The masked results remain available below.'); });
    return () => { disposed = true; view?.finalize(); };
  }, [spec]);
  if (!spec || spec._meta?.chart_type === 'none') return null;
  return <div className="vp-chart-wrap"><div ref={element} aria-label="Result chart" />{error && <p role="alert">{error}</p>}</div>;
}

function ResultTable({ table }) {
  if (!table) return null;
  return <section className="vp-block" aria-label="Answer table">
    <div className="pl-table-wrap"><table className="pl-data-table">
      <thead><tr>{table.columns.map((column) => <th key={column.name}>{column.label || column.name}</th>)}</tr></thead>
      <tbody>{table.rows.length ? table.rows.map((row, index) => <tr key={index} className={row.row_type === 'FORECAST' ? 'vp-forecast-row' : ''}>
        {table.columns.map((column) => <td key={column.name}>{cell(row[column.name])}</td>)}
      </tr>) : <tr><td colSpan={Math.max(table.columns.length, 1)}>No matching rows.</td></tr>}</tbody>
    </table></div>
    {table.limit_note && <p className="pl-muted">{table.limit_note}</p>}
    {table.truncated && <p className="pl-muted">Showing {table.rows_returned} of {table.row_count} historical rows.</p>}
  </section>;
}

export default function PresentationResult({ envelope, status, error, question, onSimulate }) {
  const [scenarioText, setScenarioText] = useState('Increase the forecast by 10%');
  const [simulation, setSimulation] = useState(null);
  const [simulating, setSimulating] = useState(false);
  const [simulationError, setSimulationError] = useState('');
  // Reset local scenarios whenever execution produces a different envelope.
  useEffect(() => { setSimulation(null); setSimulationError(''); setScenarioText('Increase the forecast by 10%'); }, [envelope]);
  if (!envelope) return status === 'UNAVAILABLE' ? <section className="pl-result-card vp-result" aria-label="Presentation unavailable">
    <h3>Presentation unavailable</h3><p>{error?.message || 'The presentation service is unavailable.'}</p><p className="pl-muted">Your query completed successfully. Masked results are shown below.</p>
  </section> : null;
  const response = envelope.response || {};
  const prediction = envelope.prediction || {};
  const readiness = prediction.stage_2_readiness || {};
  const forecast = prediction.stage_4_forecast || {};
  const anomalies = prediction.stage_5_anomaly || {};
  const canSimulate = forecast.generated && Boolean(onSimulate);
  const notice = response.forecast_notice;
  const runScenario = async (event) => {
    event.preventDefault();
    if (simulating || !scenarioText.trim()) return;
    setSimulating(true); setSimulationError(''); setSimulation(null);
    try { setSimulation(await onSimulate(scenarioText.trim())); }
    catch (failure) { setSimulationError(failure.message); }
    finally { setSimulating(false); }
  };
  return <section className="pl-result-card vp-result" aria-label="Presentation and prediction">
    <div className="pl-result-head"><h3>Your answer</h3><span className="pl-chip ok">{label(response.response_intent?.intent)}</span></div>
    <p className="vp-question">{question}</p>
    <IntentPreview analysis={envelope.analysis} />
    {response.response_intent?.is_data_request === false && <p role="status">Ask a question about the data, such as a count, trend or comparison.</p>}
    {notice && <div className="vp-notice" role="status"><strong>{notice.status === 'REFUSED' ? 'Forecast unavailable' : 'Forecast'}</strong><p>{notice.message || notice.reason}</p></div>}
    {(response.blocks_emitted || []).map((block) => {
      if (block === 'ANSWER' && response.answer) return <div key={block} className="vp-block vp-answer" aria-label="Direct answer">
        <span className="pl-muted">{response.answer.label}{response.answer.is_forecast ? ' · Forecast' : ''}</span>
        <strong>{response.answer.display_value}</strong>
        {response.answer.qualifier && <p>{response.answer.qualifier_label}: {response.answer.qualifier}</p>}
        {response.answer.interval && <p>{Math.round(response.answer.interval.confidence_level * 100)}% range: {response.answer.interval.display}</p>}
      </div>;
      if (block === 'SUMMARY' && response.summary) return <div key={block} className="vp-block" aria-label="Answer summary"><p>{response.summary.text}</p><small>Summary derived from verified numerical claims</small></div>;
      if (block === 'TABLE' && response.table) return <ResultTable key={block} table={response.table} />;
      if (block === 'CHART' && response.chart) return <div key={block} className="vp-block"><ResultChart spec={response.chart.spec} /><p className="pl-muted">Solid line: history · dashed line: forecast · shaded band: prediction range.</p></div>;
      return null;
    })}
    {envelope.input?.truncated && <p className="vp-notice">The database result was capped. Totals describe the returned rows; forecasts require complete history.</p>}
    {forecast.generated && <details className="vp-details"><summary>Forecast · {label(forecast.model)} · {Math.round((forecast.confidence_level || 0.95) * 100)}% range</summary>
      <div className="pl-table-wrap"><table className="pl-data-table"><thead><tr><th>Period</th><th>Prediction</th><th>Lower bound</th><th>Upper bound</th></tr></thead>
        <tbody>{forecast.points?.map((point, index) => <tr key={index}><td>{point.label}</td><td>{cell(point.predicted)}</td><td>{cell(point.lower_bound)}</td><td>{cell(point.upper_bound)}</td></tr>)}</tbody></table></div>
    </details>}
    {readiness.verdict !== 'NOT_REQUESTED' && <details className="vp-details"><summary>Prediction readiness: {label(readiness.verdict)}</summary><p>{readiness.reason}</p>{readiness.warnings?.map((warning, index) => <p key={index}>{typeof warning === 'string' ? warning : warning.message}</p>)}</details>}
    <details className="vp-details"><summary>Anomalies</summary>
      {!anomalies.evaluated ? <p>{anomalies.skipped_reason || 'No series available.'}</p> : <>
        {!(anomalies.historical_anomalies?.length || anomalies.predictive_warnings?.length) && <p>No anomalies detected.</p>}
        {[...(anomalies.historical_anomalies || []), ...(anomalies.predictive_warnings || [])].map((item, index) => <p key={index}>{item.label}: {cell(item.value)} · {label(item.pattern || item.direction || item.type)}</p>)}
      </>}
    </details>
    <details className="vp-details"><summary>Show the working</summary><p>{envelope.summary?.verification?.passed ? 'Numerical summary claims verified.' : 'Summary verification unavailable.'}</p>
      {envelope.summary?.claims?.map((claim, index) => <div className="vp-claim" key={claim.claim_id || index}><strong>{claim.claim_id}: {cell(claim.value)}</strong><p>{claim.text}</p><small>{claim.derivation}</small></div>)}
    </details>
    {canSimulate && <form className="vp-scenario" onSubmit={runScenario}>
      <label className="pl-label" htmlFor="vp-scenario">What-if scenario</label>
      <p className="pl-muted">Apply a scenario to this authorized result. The database is not queried again.</p>
      <input id="vp-scenario" value={scenarioText} maxLength={1000} disabled={simulating} onChange={(event) => setScenarioText(event.target.value)} />
      <button className="verify-button" disabled={simulating || !scenarioText.trim()}>{simulating ? 'Simulating…' : 'Simulate'}</button>
      {simulationError && <p role="alert">{simulationError}</p>}
      {simulation && <div className="vp-simulation" role="status">
        <p>{simulation.scenario?.simulated ? simulation.summary?.text : simulation.scenario?.skipped_reason || 'This scenario could not be applied.'}</p>
        {simulation.scenario?.simulated && <ResultChart spec={simulation.visualization} />}
      </div>}
    </form>}
    {envelope.warnings?.length > 0 && <details className="vp-details"><summary>Warnings ({envelope.warnings.length})</summary>{envelope.warnings.map((warning, index) => <p key={index}>{warning}</p>)}</details>}
  </section>;
}
