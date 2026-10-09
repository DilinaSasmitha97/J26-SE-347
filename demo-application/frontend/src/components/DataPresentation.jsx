import React, { useEffect, useRef, useState } from 'react';
import { ResultChart } from './PresentationResult.jsx';
import { INTENT_LABELS } from './IntentClassificationCard.jsx';

const SUMMARY_MODES = {
  LLM_VERIFIED: { tone: 'ok', text: 'AI-written · every number verified against the data' },
  LLM_REJECTED: { tone: 'warn', text: 'The AI draft failed number verification · showing computed facts' },
  DETERMINISTIC: { tone: '', text: 'Computed facts' }
};

const cellText = (value) => value == null || value === '' ? '—'
  : typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(value);

function Notes({ notes }) {
  if (!notes?.length) return null;
  return <ul className="dp-notes">{notes.map((note, index) => <li key={index}>{note}</li>)}</ul>;
}

function TableView({ block }) {
  return (
    <>
      <div className="pl-table-wrap">
        <table className="pl-data-table" aria-label="Result table">
          <thead><tr>{block.columns.map((column) => (
            <th key={column.name} className={column.align === 'right' ? 'dp-num' : ''}>
              {column.label || column.name}{column.masked && <span className="dp-masked" title="PII masked before leaving the backend">masked</span>}
            </th>))}</tr></thead>
          <tbody>{block.rows.length ? block.rows.map((row, index) => (
            <tr key={index}>{block.columns.map((column) => (
              <td key={column.name} className={column.align === 'right' ? 'dp-num' : ''}>{cellText(row[column.name])}</td>))}</tr>
          )) : <tr><td colSpan={Math.max(block.columns.length, 1)}>No rows returned.</td></tr>}</tbody>
        </table>
      </div>
      <p className="pl-muted">{block.row_count} row{block.row_count === 1 ? '' : 's'}</p>
    </>
  );
}

function SingleValueView({ block }) {
  return (
    <div className="dp-single" aria-label="Single value">
      <span className="pl-muted">{block.label}</span>
      <strong>{block.display_value}</strong>
      {block.qualifier && <p>{block.qualifier_label}: {block.qualifier}</p>}
    </div>
  );
}

function SummaryView({ block }) {
  const mode = SUMMARY_MODES[block.mode] || SUMMARY_MODES.DETERMINISTIC;
  return (
    <div className="dp-summary" aria-label="Summary">
      {String(block.text || '').split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
      <span className={`dp-badge ${mode.tone}`}>{mode.text}</span>
      {block.claims?.length > 0 && (
        <details className="vp-details">
          <summary>Show the computed facts ({block.claims.length})</summary>
          {block.claims.map((claim) => (
            <div className="vp-claim" key={claim.claim_id}>
              <strong>{claim.claim_id}: {cellText(claim.value)}</strong>
              <p>{claim.text}</p>
              <small>{claim.derivation}</small>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

function ViewBody({ view }) {
  if (!view.available) {
    return <div className="dp-unavailable" role="note"><strong>{view.label} isn't possible for this result.</strong><p>{view.reason}</p></div>;
  }
  const { block } = view;
  if (view.type === 'table') return <TableView block={block} />;
  if (view.type === 'single_value') return <SingleValueView block={block} />;
  if (view.type === 'summary') return <SummaryView block={block} />;
  return <ResultChart spec={block.spec} />;
}

/**
 * The data presentation layer: the executed, masked result shown in every
 * format the intent classification recommended, one tab per format.
 */
export default function DataPresentation({ status, data, error, onRetry }) {
  const views = data?.views || [];
  const [active, setActive] = useState(0);
  const tabs = useRef([]);
  useEffect(() => { setActive(0); }, [data]);

  if (status === 'idle') return null;
  if (status === 'loading') {
    return <section className="pl-result-card dp-card" aria-label="Results"><div className="pl-loading"><span className="spinner" /> Preparing the presentation…</div></section>;
  }
  if (status === 'error') {
    return (
      <section className="pl-result-card dp-card is-fail" aria-label="Results">
        <div className="pl-result-head"><h3>Results</h3></div>
        <p className="pl-error-text" role="alert">{error}</p>
        <p className="pl-muted">The masked database rows are still shown below.</p>
        {onRetry && <button type="button" className="pl-ghost" onClick={onRetry}>Retry presentation</button>}
      </section>
    );
  }

  const select = (index) => {
    const next = (index + views.length) % views.length;
    setActive(next);
    tabs.current[next]?.focus();
  };
  const onKeyDown = (event) => {
    const moves = { ArrowRight: active + 1, ArrowLeft: active - 1, Home: 0, End: views.length - 1 };
    if (event.key in moves) { event.preventDefault(); select(moves[event.key]); }
  };
  const current = views[active];

  return (
    <section className="pl-result-card dp-card is-pass" aria-label="Results">
      <div className="pl-result-head">
        <h3>Results{data.intent && <> · {INTENT_LABELS[data.intent] || data.intent}</>}</h3>
        <span className="pl-chip">{data.source === 'classification' ? 'Formats from the intent classification' : 'Formats chosen from the data'}</span>
      </div>
      <div className="dp-tabs" role="tablist" aria-label="Presentation formats" onKeyDown={onKeyDown}>
        {views.map((view, index) => (
          <button key={view.type} ref={(element) => { tabs.current[index] = element; }} type="button" role="tab"
            id={`dp-tab-${view.type}`} aria-controls={`dp-panel-${view.type}`} aria-selected={index === active}
            tabIndex={index === active ? 0 : -1} className={`dp-tab ${view.available ? '' : 'is-unavailable'}`}
            onClick={() => setActive(index)} title={view.available ? '' : view.reason}>
            {view.label}{!view.available && <span aria-hidden="true"> ·  n/a</span>}
          </button>
        ))}
      </div>
      {current && (
        <div className="dp-panel" role="tabpanel" id={`dp-panel-${current.type}`} aria-labelledby={`dp-tab-${current.type}`}>
          <ViewBody view={current} />
          {current.available && <Notes notes={current.notes} />}
        </div>
      )}
    </section>
  );
}
