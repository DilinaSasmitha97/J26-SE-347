import React from 'react';
import { afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import NlPipeline from './NlPipeline.jsx';

afterEach(() => vi.unstubAllGlobals());
const user = { userId: 'user-101-manager', role: 'MANAGER', tenantId: 101 };
const policy = { allowedTables: ['employees'], deniedColumns: [] };
const sql = 'SELECT COUNT(*) AS headcount FROM employees WHERE tenant_id = 101 AND department_id = 1';
function fakeFetch() {
  return vi.fn(async (url, options) => ({ ok: true, status: 200, text: async () => JSON.stringify(url === '/api/generate-sql'
    ? { sql, question: 'How many employees?', user, effectivePolicy: policy, generation: { metadata: {}, injectedRules: JSON.parse(options.body).rules } }
    : { status: 'COMPLETED', question: 'How many employees?', user, effectivePolicy: policy, resultId: 'result-1',
      decision: { passed: true, decision: 'PASS', checks: [], context: { userId: user.userId, role: user.role, tables: [], columns: [] } },
      result: { columns: [{ name: 'headcount' }], rows: [[7]], rowCount: 1, masking: { maskedCells: 0 } },
      presentationStatus: 'READY', presentation: { response: { blocks_emitted: ['ANSWER'], answer: { label: 'Count', display_value: '7' } }, prediction: {} }
    }) }));
}
async function generate() {
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify(policy) } });
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify(user) } });
  fireEvent.change(screen.getByLabelText('Natural language question'), { target: { value: 'How many employees?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Generate SQL' }));
  await waitFor(() => expect(screen.getByLabelText('Generated SQL').value).toBe(sql));
}

it('sends the original question with edited SQL and invalidates old presentation when SQL changes', async () => {
  const fetch = fakeFetch(); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />); await generate();
  const edited = sql.replace('COUNT(*)', 'COUNT(id)');
  fireEvent.change(screen.getByLabelText('Generated SQL'), { target: { value: edited } });
  fireEvent.click(screen.getByRole('button', { name: 'Validate & execute' }));
  await screen.findByLabelText('Direct answer');
  expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({ sql: edited, question: 'How many employees?', user, policy, rules: null, execute: true });
  fireEvent.change(screen.getByLabelText('Generated SQL'), { target: { value: sql } });
  expect(screen.queryByLabelText('Direct answer')).toBeNull();
});

it('starts and resets with empty context fields and uses pasted rules without overwriting inputs', async () => {
  const fetch = fakeFetch(); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />);
  for (const label of ['User policy', 'Authenticated user', 'NL-to-SQL rules']) expect(screen.getByLabelText(label).value).toBe('');
  const rules = { constraints: ['Order by headcount descending.'] };
  fireEvent.change(screen.getByLabelText('NL-to-SQL rules'), { target: { value: JSON.stringify(rules) } });
  await generate();
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ question: 'How many employees?', user, policy, rules });
  expect(screen.getByLabelText('User policy').value).toBe(JSON.stringify(policy));
  expect(screen.getByLabelText('Authenticated user').value).toBe(JSON.stringify(user));
  expect(screen.getByLabelText('NL-to-SQL rules').value).toBe(JSON.stringify(rules));
  expect(screen.getByText('NL-to-SQL rules sent')).toBeTruthy();
  expect(screen.getByText('NL-to-SQL rules sent').parentElement.querySelector('pre').textContent).toBe(JSON.stringify(rules, null, 2));
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: '{}' } });
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
  for (const label of ['User policy', 'Authenticated user', 'NL-to-SQL rules']) expect(screen.getByLabelText(label).value).toBe('');
});

it('question and identity changes invalidate the SQL draft', async () => {
  vi.stubGlobal('fetch', fakeFetch());
  render(<NlPipeline />); await generate();
  fireEvent.change(screen.getByLabelText('Natural language question'), { target: { value: 'Show employees' } });
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
  await generate();
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify({ userId: 'user-102-manager' }) } });
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
});
