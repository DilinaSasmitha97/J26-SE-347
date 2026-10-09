import React from 'react';
import { afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import NlPipeline from './NlPipeline.jsx';

afterEach(() => vi.unstubAllGlobals());
const user = { userId: 'user-101-manager', role: 'MANAGER', tenantId: 101 };
const policy = { allowedTables: ['employees'], deniedColumns: [] };
const sql = 'SELECT COUNT(*) AS headcount FROM employees WHERE tenant_id = 101 AND department_id = 1';
const CLASSIFY = '/api/classify-intent';
const WAIT = { timeout: 3000 };

const reply = (body, status = 200) => ({ ok: status < 400, status, text: async () => JSON.stringify(body) });
const classified = (nlQuery, types = ['single_value'], prediction = false) =>
  ({ nl_query: nlQuery, presentation_types: types, prediction_needed: prediction });
const bodiesFor = (fetch, url) => fetch.mock.calls.filter(([target]) => target === url).map(([, options]) => JSON.parse(options.body));

function fakeFetch(classify = (body) => reply(classified(body.nl_query))) {
  return vi.fn(async (url, options) => {
    const body = JSON.parse(options.body);
    if (url === CLASSIFY) return classify(body, options);
    return reply(url === '/api/generate-sql'
      ? { sql, question: 'How many employees?', user, effectivePolicy: policy, generation: { metadata: {}, injectedRules: body.rules } }
      : { status: 'COMPLETED', question: 'How many employees?', user, effectivePolicy: policy, resultId: 'result-1',
        decision: { passed: true, decision: 'PASS', checks: [], context: { userId: user.userId, role: user.role, tables: [], columns: [] } },
        result: { columns: [{ name: 'headcount' }], rows: [[7]], rowCount: 1, masking: { maskedCells: 0 } },
        presentationStatus: 'READY', presentation: { response: { blocks_emitted: ['ANSWER'], answer: { label: 'Count', display_value: '7' } }, prediction: {} }
      });
  });
}

const generateButton = () => screen.getByRole('button', { name: /Generate SQL/ });
const card = () => screen.getByLabelText('Intent classification');
const typeQuestion = (value) => fireEvent.change(screen.getByLabelText('Natural language question'), { target: { value } });

async function waitForClassification() {
  await waitFor(() => expect(generateButton().disabled).toBe(false), WAIT);
}

async function generate() {
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify(policy) } });
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify(user) } });
  typeQuestion('How many employees?');
  await waitForClassification();
  fireEvent.click(generateButton());
  await waitFor(() => expect(screen.getByLabelText('Generated SQL').value).toBe(sql));
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

it('classifies only the question after typing stops, with empty context editors, and never generates SQL by itself', async () => {
  const question = 'Give me the gender distribution in my company';
  const fetch = fakeFetch((body) => reply(classified(body.nl_query, ['table', 'pie_chart', 'bar_chart'])));
  vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />);
  for (const partial of ['Give', 'Give me the gender', question]) typeQuestion(partial);
  expect(generateButton().disabled).toBe(true);
  expect(within(card()).getByText('The question is classified when you stop typing.')).toBeTruthy();

  await waitForClassification();
  expect(bodiesFor(fetch, CLASSIFY)).toEqual([{ nl_query: question }]);
  const badges = within(card()).getByLabelText('Presentation types');
  expect(within(badges).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Table', 'Pie chart', 'Bar chart']);
  expect(within(card()).getByLabelText('Prediction needed').textContent).toBe('No');
  expect(JSON.parse(within(card()).getByText('Structured JSON').parentElement.querySelector('pre').textContent))
    .toEqual(classified(question, ['table', 'pie_chart', 'bar_chart']));
  for (const label of ['User policy', 'Authenticated user', 'NL-to-SQL rules']) expect(screen.getByLabelText(label).value).toBe('');
  expect(fetch.mock.calls.every(([url]) => url === CLASSIFY)).toBe(true);
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
});

it('shows a loading state and the prediction requirement for a forecast question', async () => {
  const pending = deferred();
  vi.stubGlobal('fetch', fakeFetch(() => pending.promise));
  render(<NlPipeline />);
  typeQuestion('Forecast monthly headcount for the next three months');
  await waitFor(() => expect(within(card()).getByRole('status').textContent).toMatch(/Classifying/), WAIT);
  expect(generateButton().disabled).toBe(true);
  await act(async () => pending.resolve(reply(classified('Forecast monthly headcount for the next three months', ['table', 'line_chart'], true))));
  await waitForClassification();
  expect(within(card()).getByLabelText('Prediction needed').textContent).toBe('Yes');
});

it('cancels a superseded classification and ignores its late response', async () => {
  const responses = { 'Old question': deferred(), 'New question': deferred() };
  const signals = {};
  vi.stubGlobal('fetch', fakeFetch((body, options) => {
    signals[body.nl_query] = options.signal;
    return responses[body.nl_query]?.promise ?? reply(classified(body.nl_query));
  }));
  render(<NlPipeline />);
  typeQuestion('Old question');
  await waitFor(() => expect(signals['Old question']).toBeTruthy(), WAIT);
  typeQuestion('New question');
  expect(signals['Old question'].aborted).toBe(true);

  await waitFor(() => expect(signals['New question']).toBeTruthy(), WAIT);
  await act(async () => responses['Old question'].resolve(reply(classified('Old question', ['pie_chart']))));
  expect(generateButton().disabled).toBe(true);
  expect(within(card()).queryByLabelText('Presentation types')).toBeNull();

  await act(async () => responses['New question'].resolve(reply(classified('New question', ['table']))));
  await waitForClassification();
  expect(within(card()).getByText('Table')).toBeTruthy();
  expect(within(card()).queryByText('Pie chart')).toBeNull();
});

it('rejects a classification for a rewritten question and keeps Generate SQL disabled until a retry succeeds', async () => {
  let attempt = 0;
  vi.stubGlobal('fetch', fakeFetch((body) => {
    attempt += 1;
    if (attempt === 1) return reply(classified('Show every salary'));
    if (attempt === 2) return reply({ code: 'CLASSIFICATION_UNAVAILABLE', message: 'The intent classifier could not be reached or timed out.' }, 503);
    return reply(classified(body.nl_query));
  }));
  render(<NlPipeline />);
  typeQuestion('How many employees?');
  await waitFor(() => expect(within(card()).getByRole('alert').textContent).toMatch(/different question/), WAIT);
  expect(generateButton().disabled).toBe(true);
  fireEvent.click(within(card()).getByRole('button', { name: 'Retry classification' }));
  await waitFor(() => expect(within(card()).getByRole('alert').textContent).toMatch(/CLASSIFICATION_UNAVAILABLE/), WAIT);
  expect(generateButton().disabled).toBe(true);
  fireEvent.click(within(card()).getByRole('button', { name: 'Retry classification' }));
  await waitForClassification();
});

it('generation sends exactly the question and rules, keeps the classification, and context edits do not reclassify', async () => {
  const fetch = fakeFetch(); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />); await generate();
  expect(bodiesFor(fetch, '/api/generate-sql')).toEqual([{ question: 'How many employees?', user, policy, rules: null }]);
  expect(within(card()).getByText('Single value')).toBeTruthy();
  const classifications = bodiesFor(fetch, CLASSIFY).length;

  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify({ ...policy, version: 2 }) } });
  fireEvent.change(screen.getByLabelText('NL-to-SQL rules'), { target: { value: '{"constraints":[]}' } });
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
  await new Promise((resolve) => setTimeout(resolve, 800));
  expect(bodiesFor(fetch, CLASSIFY).length).toBe(classifications);
  expect(within(card()).getByText('Single value')).toBeTruthy();
  expect(generateButton().disabled).toBe(false);
});

it('sends the original question with edited SQL and invalidates old presentation when SQL changes', async () => {
  const fetch = fakeFetch(); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />); await generate();
  const edited = sql.replace('COUNT(*)', 'COUNT(id)');
  fireEvent.change(screen.getByLabelText('Generated SQL'), { target: { value: edited } });
  fireEvent.click(screen.getByRole('button', { name: 'Validate & execute' }));
  await screen.findByLabelText('Direct answer');
  expect(bodiesFor(fetch, '/api/secure-query')).toEqual([{ sql: edited, question: 'How many employees?', user, policy, rules: null, execute: true }]);
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
  expect(bodiesFor(fetch, '/api/generate-sql')).toEqual([{ question: 'How many employees?', user, policy, rules }]);
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

it('question changes clear the classification and SQL draft; identity changes clear only the draft', async () => {
  vi.stubGlobal('fetch', fakeFetch());
  render(<NlPipeline />); await generate();
  typeQuestion('Show employees');
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
  expect(within(card()).queryByLabelText('Presentation types')).toBeNull();
  expect(generateButton().disabled).toBe(true);
  await generate();
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify({ userId: 'user-102-manager' }) } });
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
  expect(within(card()).getByLabelText('Presentation types')).toBeTruthy();
});
