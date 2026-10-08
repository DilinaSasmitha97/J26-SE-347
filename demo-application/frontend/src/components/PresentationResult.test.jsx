import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PresentationResult from './PresentationResult.jsx';

vi.mock('vega-embed', () => ({ default: vi.fn(async () => ({ view: { finalize: vi.fn() } })) }));

const chartSpec = { $schema: 'https://vega.github.io/schema/vega-lite/v5.json', mark: 'bar', data: { values: [{ department: 'HR', count: 7 }] }, encoding: { x: { field: 'department', type: 'nominal' }, y: { field: 'count', type: 'quantitative' } } };
function result(intent, blocks) {
  return {
    response: { response_intent: { intent }, blocks_emitted: blocks,
      answer: { label: 'Employee count', display_value: '7' },
      summary: { text: 'Seven employees matched.' },
      table: { columns: [{ name: 'name', label: 'Name' }], rows: [{ name: 'Masked name' }] },
      chart: { spec: chartSpec } },
    prediction: { stage_2_readiness: { verdict: 'NOT_REQUESTED' } },
    summary: { verification: { passed: true }, claims: [{ claim_id: 'H1', value: 7, text: 'Count is seven', derivation: 'Count of authorized rows' }] }
  };
}

describe('presentation contract', () => {
  for (const [intent, blocks, expected] of [
    ['SINGLE_ANSWER', ['ANSWER'], 'Direct answer'],
    ['SHORT_SUMMARY', ['SUMMARY'], 'Answer summary'],
    ['TABLE_CONTENT', ['TABLE'], 'Answer table'],
    ['CHART', ['CHART'], 'Result chart'],
    ['MIXED_SUMMARY', ['SUMMARY', 'TABLE', 'CHART'], 'Answer summary']
  ]) it(`renders the declared blocks for ${intent}`, () => {
    render(<PresentationResult envelope={result(intent, blocks)} question="Count employees" />);
    expect(screen.getByLabelText(expected)).toBeTruthy();
    expect(Boolean(screen.queryByLabelText('Direct answer'))).toBe(blocks.includes('ANSWER'));
    expect(Boolean(screen.queryByLabelText('Answer table'))).toBe(blocks.includes('TABLE'));
    expect(Boolean(screen.queryByLabelText('Answer summary'))).toBe(blocks.includes('SUMMARY'));
    expect(Boolean(screen.queryByLabelText('Result chart'))).toBe(blocks.includes('CHART'));
  });

  it('preserves the order of emitted response blocks', () => {
    const { container } = render(<PresentationResult envelope={result('MIXED_SUMMARY', ['SUMMARY', 'TABLE', 'CHART'])} />);
    expect([...container.querySelectorAll('.vp-block')].map((element) => element.getAttribute('aria-label') || 'chart')).toEqual(['Answer summary', 'Answer table', 'chart']);
  });

  it('shows forecast refusal and preserves results when presentation is unavailable', () => {
    const envelope = result('TABLE_CONTENT', ['TABLE']);
    envelope.response.forecast_notice = { status: 'REFUSED', message: 'History is truncated.' };
    const { rerender } = render(<PresentationResult envelope={envelope} />);
    expect(screen.getByText('History is truncated.')).toBeTruthy();
    rerender(<PresentationResult status="UNAVAILABLE" error={{ message: 'Service timed out.' }} />);
    expect(screen.getByText('Service timed out.')).toBeTruthy();
    expect(screen.getByText(/Masked results are shown below/)).toBeTruthy();
  });

  it('calls the server-bound what-if callback and reports refusal', async () => {
    const envelope = result('SINGLE_ANSWER', ['ANSWER']);
    envelope.prediction.stage_4_forecast = { generated: true, model: 'LINEAR_REGRESSION', points: [] };
    const simulate = vi.fn(async () => ({ scenario: { simulated: false, skipped_reason: 'Scenario not supported.' } }));
    render(<PresentationResult envelope={envelope} onSimulate={simulate} />);
    fireEvent.change(screen.getByLabelText('What-if scenario'), { target: { value: 'Increase by 10%' } });
    fireEvent.click(screen.getByRole('button', { name: 'Simulate' }));
    await waitFor(() => expect(simulate).toHaveBeenCalledWith('Increase by 10%'));
    expect(await screen.findByText('Scenario not supported.')).toBeTruthy();
  });
});
