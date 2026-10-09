import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import embed from 'vega-embed';
import DataPresentation from './DataPresentation.jsx';

vi.mock('vega-embed', () => ({ default: vi.fn(async () => ({ view: { finalize: vi.fn() } })) }));

const pieSpec = { $schema: 'https://vega.github.io/schema/vega-lite/v5.json', mark: { type: 'arc' }, data: { values: [{ gender: 'Female', headcount: 42 }] }, encoding: {} };
const barSpec = { ...pieSpec, mark: { type: 'bar' } };
const data = {
  status: 'SUCCESS', source: 'classification', intent: 'PROPORTION', row_count: 2,
  views: [
    { type: 'table', label: 'Table', available: true, reason: '', notes: [], block: {
      columns: [{ name: 'gender', label: 'Gender', align: 'left', masked: false }, { name: 'headcount', label: 'Headcount', align: 'right', masked: false },
        { name: 'work_email', label: 'Work Email', align: 'left', masked: true }],
      rows: [{ gender: 'Female', headcount: 42, work_email: 'f***@example.com' }, { gender: 'Male', headcount: 51, work_email: 'm***@example.com' }], row_count: 2 } },
    { type: 'pie_chart', label: 'Pie chart', available: true, reason: '', notes: ['Headcount is summed per gender.'], block: { spec: pieSpec } },
    { type: 'bar_chart', label: 'Bar chart', available: true, reason: '', notes: [], block: { spec: barSpec } },
    { type: 'line_chart', label: 'Line chart', available: false, reason: 'The result has no date or period column to draw over time.', notes: [], block: null },
    { type: 'single_value', label: 'Single value', available: true, reason: '', notes: [], block: { label: 'Headcount', display_value: '93', qualifier: '', qualifier_label: '' } },
    { type: 'summary', label: 'Summary', available: true, reason: '', notes: [], block: {
      text: 'Headcount totals 93.\n\nMale leads with 51.', mode: 'LLM_VERIFIED',
      claims: [{ claim_id: 'H1', value: 93, text: 'Total headcount is 93.', derivation: 'sum of 2 values' }] } }
  ]
};

const tab = (name) => screen.getByRole('tab', { name });
const panel = () => screen.getByRole('tabpanel');

describe('data presentation', () => {
  it('shows one tab per recommended format and opens the first', () => {
    render(<DataPresentation status="ready" data={data} />);
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Table', 'Pie chart', 'Bar chart', 'Line chart ·  n/a', 'Single value', 'Summary']);
    expect(tab('Table').getAttribute('aria-selected')).toBe('true');
    expect(screen.getByText(/Results · Proportion/)).toBeTruthy();
    expect(screen.getByText('Formats from the intent classification')).toBeTruthy();
    const table = within(panel()).getByRole('table', { name: 'Result table' });
    expect(within(table).getAllByRole('row')).toHaveLength(3);
    expect(within(table).getByText('masked')).toBeTruthy();
  });

  it('renders every chart tab with Vega-Lite and shows its notes', async () => {
    render(<DataPresentation status="ready" data={data} />);
    fireEvent.click(tab('Pie chart'));
    await waitFor(() => expect(embed).toHaveBeenLastCalledWith(expect.anything(), pieSpec, expect.objectContaining({ renderer: 'svg' })));
    expect(within(panel()).getByText('Headcount is summed per gender.')).toBeTruthy();
    fireEvent.click(tab('Bar chart'));
    await waitFor(() => expect(embed).toHaveBeenLastCalledWith(expect.anything(), barSpec, expect.anything()));
  });

  it('explains a format the result cannot support', () => {
    render(<DataPresentation status="ready" data={data} />);
    fireEvent.click(tab('Line chart'));
    expect(within(panel()).getByRole('note').textContent).toMatch(/Line chart isn't possible for this result.*no date or period column/);
  });

  it('shows the single value and the verified summary', () => {
    render(<DataPresentation status="ready" data={data} />);
    fireEvent.click(tab('Single value'));
    expect(within(panel()).getByLabelText('Single value').textContent).toContain('93');
    fireEvent.click(tab('Summary'));
    expect(within(panel()).getByText('Male leads with 51.')).toBeTruthy();
    expect(within(panel()).getByText(/every number verified/)).toBeTruthy();
    expect(within(panel()).getByText('Show the computed facts (1)')).toBeTruthy();
  });

  it('flags a summary whose AI draft failed verification', () => {
    const rejected = { ...data, views: [{ ...data.views[5], block: { ...data.views[5].block, mode: 'LLM_REJECTED' } }] };
    render(<DataPresentation status="ready" data={rejected} />);
    expect(screen.getByText(/failed number verification · showing computed facts/)).toBeTruthy();
  });

  it('moves between tabs with the arrow keys', () => {
    render(<DataPresentation status="ready" data={data} />);
    fireEvent.keyDown(tab('Table'), { key: 'ArrowRight' });
    expect(tab('Pie chart').getAttribute('aria-selected')).toBe('true');
    fireEvent.keyDown(tab('Pie chart'), { key: 'End' });
    expect(tab('Summary').getAttribute('aria-selected')).toBe('true');
    fireEvent.keyDown(tab('Summary'), { key: 'ArrowRight' });
    expect(tab('Table').getAttribute('aria-selected')).toBe('true');
  });

  it('marks formats chosen from the data, and shows loading and error states', () => {
    const { rerender } = render(<DataPresentation status="ready" data={{ ...data, source: 'data', intent: null }} />);
    expect(screen.getByText('Formats chosen from the data')).toBeTruthy();
    rerender(<DataPresentation status="loading" />);
    expect(screen.getByText('Preparing the presentation…')).toBeTruthy();
    const retry = vi.fn();
    rerender(<DataPresentation status="error" error="PRESENTATION_UNAVAILABLE: offline" onRetry={retry} />);
    expect(screen.getByRole('alert').textContent).toContain('PRESENTATION_UNAVAILABLE');
    fireEvent.click(screen.getByRole('button', { name: 'Retry presentation' }));
    expect(retry).toHaveBeenCalled();
  });
});
