import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import embed from 'vega-embed';
import PredictionCard from './PredictionCard.jsx';

vi.mock('vega-embed', () => ({ default: vi.fn(async () => ({ view: { finalize: vi.fn() } })) }));

const spec = { $schema: 'https://vega.github.io/schema/vega-lite/v5.json', layer: [], _meta: { forecast_layered: true } };
const ready = {
  status: 'SUCCESS', mode: 'FORECAST', intent: 'TREND_ANALYSIS',
  horizon: { value: 3, unit: 'NONE', source: 'INFERRED' },
  strategy: { strategy: 'TEMPORAL_FORECAST', rationale: 'A measure tracked over time extends naturally into future periods.' },
  readiness: { verdict: 'READY', reason: 'Series is ready for forecasting.', warnings: [], checks: ['24 points', 'regular monthly axis'] },
  model: { model: 'HOLT', reason: 'A clear trend.' },
  forecast: { generated: true, model: 'HOLT', model_reason: 'A clear trend with no seasonality.', granularity: 'MONTH', horizon: 3, confidence_level: 0.95,
    points: [{ label: 'Jan 2025', predicted: 196, lower_bound: 190, upper_bound: 202 },
      { label: 'Feb 2025', predicted: 200, lower_bound: 191, upper_bound: 209 },
      { label: 'Mar 2025', predicted: 204, lower_bound: 192, upper_bound: 216 }], skipped_reason: '' },
  anomalies: { evaluated: true, volatility_regime: 'STABLE', iqr_multiplier: 1.5, z_threshold: 3, detrended: true, seasonal: false,
    historical_anomalies: [{ label: 'Apr 2024', value: 220, direction: 'HIGH', severity: 'SEVERE', detected_by: ['IQR', 'ZSCORE'], z_score: 4.2 }],
    predictive_warnings: [{ label: 'Mar 2025', value: 204, direction: 'LOW', severity: 'MODERATE', detected_by: ['IQR'] }], skipped_reason: '' },
  strategy_result: { executed: true }, chart: { spec }, chart_reason: '',
  summary: { text: 'Hires rose steadily.\n\nThey are forecast to reach 204 by March 2025.', mode: 'LLM_VERIFIED',
    claims: [{ claim_id: 'F1', value: 204, text: 'Forecast for Mar 2025 is 204.', derivation: 'Holt' }] }
};
const notReady = {
  ...ready,
  readiness: { verdict: 'INSUFFICIENT_POINTS', reason: 'Only 3 usable observations; at least 4 are required for any forecast.', warnings: [], checks: [] },
  forecast: { ...ready.forecast, generated: false, points: [], model: 'NONE', skipped_reason: 'Only 3 usable observations; at least 4 are required for any forecast.' },
  anomalies: { evaluated: false, historical_anomalies: [], predictive_warnings: [], skipped_reason: 'Only 3 observations; at least 5 are needed.' },
  strategy_result: { executed: false }, chart: null, chart_reason: 'There is no forecast or anomaly to draw.'
};

const tab = (name) => screen.getByRole('tab', { name });
const panel = () => screen.getByRole('tabpanel');

describe('prediction card', () => {
  it('shows the forecast with its readiness, horizon and model', async () => {
    render(<PredictionCard status="ready" data={ready} />);
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Forecast', 'Forecast table', 'Anomalies', 'Readiness & method', 'Summary']);
    expect(screen.getByText(/Prediction · 3 months ahead/)).toBeTruthy();
    expect(screen.getByLabelText('Readiness').textContent).toBe('Ready');
    await waitFor(() => expect(embed).toHaveBeenLastCalledWith(expect.anything(), { $schema: spec.$schema, layer: [] }, expect.anything()));
    expect(within(panel()).getByText(/dashed line: forecast · shaded band: 95% prediction range · triangles: anomalies/)).toBeTruthy();
  });

  it('lists forecast points with lower and upper bounds', () => {
    render(<PredictionCard status="ready" data={ready} />);
    fireEvent.click(tab('Forecast table'));
    const rows = within(within(panel()).getByRole('table', { name: 'Forecast table' })).getAllByRole('row');
    expect(rows.map((row) => row.textContent)).toEqual(['PeriodPredictionLower boundUpper bound', 'Jan 2025196190202', 'Feb 2025200191209', 'Mar 2025204192216']);
  });

  it('separates historical anomalies from predicted breaches', () => {
    render(<PredictionCard status="ready" data={ready} />);
    fireEvent.click(tab('Anomalies'));
    const body = within(panel()).getByLabelText('Anomalies').textContent;
    expect(body).toMatch(/IQR fence and Z-score/);
    expect(body).toMatch(/Historical anomaliesApr 2024: 220 · high · severe · detected by IQR \+ ZSCORE/);
    expect(body).toMatch(/Predicted threshold breachesMar 2025: 204 · low/);
  });

  it('explains readiness, strategy, model and horizon, and shows the verified summary', () => {
    render(<PredictionCard status="ready" data={ready} />);
    fireEvent.click(tab('Readiness & method'));
    const method = within(panel()).getByLabelText('Readiness and method').textContent;
    expect(method).toMatch(/ready.*Series is ready/);
    expect(method).toMatch(/temporal forecast: A measure tracked over time/);
    expect(method).toMatch(/holt: A clear trend with no seasonality/);
    expect(method).toMatch(/3 months \(default\)/);
    fireEvent.click(tab('Summary'));
    expect(within(panel()).getByText('They are forecast to reach 204 by March 2025.')).toBeTruthy();
    expect(within(panel()).getByText(/every number verified/)).toBeTruthy();
  });

  it('shows why no forecast was produced when the data is not ready', () => {
    render(<PredictionCard status="ready" data={notReady} />);
    expect(screen.getByLabelText('Readiness').textContent).toBe('Insufficient points');
    expect(within(panel()).getByRole('note').textContent).toMatch(/No forecast was produced.*at least 4 are required/);
    fireEvent.click(tab('Anomalies'));
    expect(within(panel()).getByRole('note').textContent).toMatch(/Anomalies were not checked/);
  });

  it('shows one forecast per category for a multi-series result', () => {
    const perType = { ...ready, readiness: { ...ready.readiness, verdict: 'MULTI_SERIES', reason: 'One series per employment_type.' },
      forecast: { ...ready.forecast, generated: false, points: [] },
      strategy_result: { executed: true, details: { categories: [
        { category: 'PERMANENT', points: [{ label: '2026', predicted: 4.2, lower: 0.4, upper: 8 }] },
        { category: 'INTERN', points: [{ label: '2026', predicted: 1, lower: 0, upper: 3.7 }] }] } } };
    render(<PredictionCard status="ready" data={perType} />);
    expect(screen.getByLabelText('Readiness').textContent).toBe('Forecast per category');
    fireEvent.click(tab('Forecast table'));
    const rows = within(within(panel()).getByRole('table', { name: 'Forecast table' })).getAllByRole('row');
    expect(rows.map((row) => row.textContent)).toEqual(['CategoryPeriodPredictionLower boundUpper bound', 'PERMANENT20264.20.48', 'INTERN2026103.7']);
  });

  it('anomaly-only questions get no forecast tabs', () => {
    const anomalyOnly = { ...ready, mode: 'ANOMALY_ONLY', readiness: { ...ready.readiness, verdict: 'NOT_REQUESTED' },
      forecast: { ...ready.forecast, generated: false, points: [] }, anomalies: { ...ready.anomalies, predictive_warnings: [] } };
    render(<PredictionCard status="ready" data={anomalyOnly} />);
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Anomaly chart', 'Anomalies', 'Readiness & method', 'Summary']);
    expect(screen.getByText('Anomaly check')).toBeTruthy();
    expect(screen.getByLabelText('Readiness').textContent).toBe('History only');
  });

  it('shows loading and error states', () => {
    const { rerender } = render(<PredictionCard status="loading" />);
    expect(screen.getByText('Checking readiness and forecasting…')).toBeTruthy();
    const retry = vi.fn();
    rerender(<PredictionCard status="error" error="PREDICTION_FAILED: boom" onRetry={retry} />);
    fireEvent.click(screen.getByRole('button', { name: 'Retry prediction' }));
    expect(retry).toHaveBeenCalled();
  });
});
