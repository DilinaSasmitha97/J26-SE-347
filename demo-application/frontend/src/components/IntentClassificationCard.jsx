import React from 'react';

export const PRESENTATION_TYPE_LABELS = Object.freeze({
  table: 'Table',
  single_value: 'Single value',
  bar_chart: 'Bar chart',
  pie_chart: 'Pie chart',
  line_chart: 'Line chart',
  summary: 'Summary'
});

const STATUS = {
  idle: { pill: '', text: 'Waiting' },
  pending: { pill: 'loading', text: 'Waiting' },
  loading: { pill: 'loading', text: 'Classifying' },
  ready: { pill: 'pass', text: 'Classified' },
  error: { pill: 'error', text: 'Error' }
};

/**
 * Shows the question-only classification: recommended presentation formats and
 * whether a forecast was requested. The result is a recommendation; whether the
 * returned rows support a format or forecast is decided after execution.
 */
export default function IntentClassificationCard({ status, result, error, onRetry, disabled = false }) {
  const { pill, text } = STATUS[status] || STATUS.idle;
  return (
    <section className={`pl-intent-card ${status === 'error' ? 'is-fail' : status === 'ready' ? 'is-pass' : ''}`}
      aria-label="Intent classification" aria-busy={status === 'loading'}>
      <div className="pl-result-head">
        <h3>Intent classification</h3>
        <span className={`pl-pill ${pill ? `pl-pill-${pill}` : ''}`}>{status === 'loading' && <i className="pl-dot-spin" />}{text}</span>
      </div>

      {status === 'idle' && <p className="pl-muted">Type a question to see the recommended presentation formats.</p>}
      {status === 'pending' && <p className="pl-muted">The question is classified when you stop typing.</p>}
      {status === 'loading' && <p className="pl-muted" role="status">Classifying the question…</p>}

      {status === 'error' && (
        <>
          <p className="pl-error-text" role="alert">{error}</p>
          <button type="button" className="pl-ghost" onClick={onRetry} disabled={disabled}>Retry classification</button>
        </>
      )}

      {status === 'ready' && result && (
        <>
          <div className="pl-intent-row">
            <span className="pl-intent-label">Recommended formats</span>
            <ul className="pl-intent-types" aria-label="Presentation types">
              {result.presentation_types.map((type) => (
                <li key={type} className="pl-chip ok">{PRESENTATION_TYPE_LABELS[type] || type}</li>
              ))}
            </ul>
          </div>
          <div className="pl-intent-row">
            <span className="pl-intent-label">Prediction needed</span>
            <strong aria-label="Prediction needed">{result.prediction_needed ? 'Yes' : 'No'}</strong>
          </div>
          <p className="pl-muted">Recommended from the question alone. Whether the results support each format or a forecast is checked after execution.</p>
          <details className="pl-intent-json">
            <summary>Structured JSON</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </details>
        </>
      )}
    </section>
  );
}
