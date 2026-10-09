import React from 'react';
import { afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import NlPipeline from './NlPipeline.jsx';

vi.mock('vega-embed', () => ({ default: vi.fn(async () => ({ view: { finalize: vi.fn() } })) }));

afterEach(() => vi.unstubAllGlobals());
const user = { userId: 'user-101-manager', role: 'MANAGER', tenantId: 101 };
const policy = { allowedTables: ['employees'], deniedColumns: [] };
const sql = 'SELECT COUNT(*) AS headcount FROM employees WHERE tenant_id = 101 AND department_id = 1';
const CLASSIFY = '/api/classify-intent';
const GENERATE = '/api/generate-sql';
const PRESENT = '/api/present-result';
const rendered = { status: 'SUCCESS', source: 'classification', intent: 'KPI_SINGLE_VALUE', row_count: 1, views: [
  { type: 'single_value', label: 'Single value', available: true, reason: '', notes: [], block: { label: 'Headcount', display_value: '7' } },
  { type: 'table', label: 'Table', available: true, reason: '', notes: [], block: { columns: [{ name: 'headcount', label: 'Headcount', align: 'right' }], rows: [{ headcount: 7 }], row_count: 1 } }
] };
const WAIT = { timeout: 3000 };

const reply = (body, status = 200) => ({ ok: status < 400, status, text: async () => JSON.stringify(body) });
const classified = (nlQuery, intent = 'KPI_SINGLE_VALUE', types = ['single_value'], prediction = false) =>
  ({ nl_query: nlQuery, intent, presentation_types: types, prediction_needed: prediction });
const bodiesFor = (fetch, url) => fetch.mock.calls.filter(([target]) => target === url).map(([, options]) => JSON.parse(options.body));

function fakeFetch(classify = (body) => reply(classified(body.nl_query))) {
  return vi.fn(async (url, options) => {
    const body = JSON.parse(options.body);
    if (url === CLASSIFY) return classify(body, options);
    if (url === PRESENT) return reply(rendered);
    return reply(url === GENERATE
      ? { sql, question: 'How many employees?', user, effectivePolicy: policy, generation: { metadata: {}, injectedRules: body.rules } }
      : { status: 'COMPLETED', question: 'How many employees?', user, effectivePolicy: policy, resultId: 'result-1',
        decision: { passed: true, decision: 'PASS', checks: [], context: { userId: user.userId, role: user.role, tables: [], columns: [] } },
        result: { columns: [{ name: 'headcount' }], rows: [[7]], rowCount: 1, masking: { maskedCells: 0 } },
        presentationStatus: 'READY', presentation: { response: { blocks_emitted: ['ANSWER'], answer: { label: 'Count', display_value: '7' } }, prediction: {} }
      });
  });
}

const generateButton = () => screen.getByRole('button', { name: /Generate SQL|Classifying/ });
const continueButton = () => screen.queryByRole('button', { name: /Continue to SQL|Generating SQL/ });
const continueAnywayButton = () => screen.queryByRole('button', { name: 'Continue without classification' });
const card = () => screen.getByLabelText('Intent classification');
const typeQuestion = (value) => fireEvent.change(screen.getByLabelText('Natural language question'), { target: { value } });

async function classify(question) {
  if (question) typeQuestion(question);
  fireEvent.click(generateButton());
  await waitFor(() => expect(continueButton()).toBeTruthy(), WAIT);
}

async function generate() {
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify(policy) } });
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify(user) } });
  await classify('How many employees?');
  fireEvent.click(continueButton());
  await waitFor(() => expect(screen.getByLabelText('Generated SQL').value).toBe(sql));
}

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

it('classifies only after Generate SQL is clicked, with empty context editors, and generates no SQL until Continue', async () => {
  const question = 'Give me the gender distribution in my company';
  const fetch = fakeFetch((body) => reply(classified(body.nl_query, 'PROPORTION', ['table', 'pie_chart', 'bar_chart'])));
  vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />);
  typeQuestion(question);
  await new Promise((resolve) => setTimeout(resolve, 800));
  expect(fetch).not.toHaveBeenCalled();
  expect(continueButton()).toBeNull();

  await classify();
  expect(bodiesFor(fetch, CLASSIFY)).toEqual([{ nl_query: question }]);
  expect(within(card()).getByLabelText('Intent').textContent).toBe('Proportion');
  const badges = within(card()).getByLabelText('Presentation types');
  expect(within(badges).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Table', 'Pie chart', 'Bar chart']);
  expect(within(card()).getByLabelText('Prediction needed').textContent).toBe('No');
  expect(JSON.parse(within(card()).getByText('Structured JSON').parentElement.querySelector('pre').textContent))
    .toEqual(classified(question, 'PROPORTION', ['table', 'pie_chart', 'bar_chart']));
  for (const label of ['User policy', 'Authenticated user', 'NL-to-SQL rules']) expect(screen.getByLabelText(label).value).toBe('');
  expect(bodiesFor(fetch, GENERATE)).toEqual([]);
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
});

it('shows a loading state and the prediction requirement for a forecast question', async () => {
  const pending = deferred();
  const question = 'Forecast monthly headcount for the next three months';
  vi.stubGlobal('fetch', fakeFetch(() => pending.promise));
  render(<NlPipeline />);
  typeQuestion(question);
  fireEvent.click(generateButton());
  expect(within(card()).getByRole('status').textContent).toMatch(/Classifying/);
  expect(generateButton().disabled).toBe(true);
  await act(async () => pending.resolve(reply(classified(question, 'TREND_ANALYSIS', ['table', 'line_chart'], true))));
  await waitFor(() => expect(continueButton()).toBeTruthy(), WAIT);
  expect(within(card()).getByLabelText('Prediction needed').textContent).toBe('Yes');
  expect(within(card()).getByLabelText('Intent').textContent).toBe('Trend analysis');
});

it('Continue to SQL sends exactly the question and rules, keeps the classification, and context edits do not reclassify', async () => {
  const fetch = fakeFetch(); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />); await generate();
  expect(bodiesFor(fetch, GENERATE)).toEqual([{ question: 'How many employees?', user, policy, rules: null }]);
  expect(bodiesFor(fetch, CLASSIFY)).toEqual([{ nl_query: 'How many employees?' }]);
  expect(within(card()).getByText('Single value')).toBeTruthy();

  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify({ ...policy, version: 2 }) } });
  expect(screen.getByLabelText('Generated SQL').value).toBe(sql);
  fireEvent.change(screen.getByLabelText('NL-to-SQL rules'), { target: { value: '{"constraints":[]}' } });
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
  expect(bodiesFor(fetch, CLASSIFY).length).toBe(1);
  expect(within(card()).getByText('Single value')).toBeTruthy();
  expect(continueButton().disabled).toBe(false);
});

it('cancels a classification when the question changes and ignores its late response', async () => {
  const pending = deferred();
  let signal;
  vi.stubGlobal('fetch', fakeFetch((body, options) => { signal = options.signal; return pending.promise; }));
  render(<NlPipeline />);
  typeQuestion('Old question');
  fireEvent.click(generateButton());
  await waitFor(() => expect(signal).toBeTruthy(), WAIT);
  typeQuestion('New question');
  expect(signal.aborted).toBe(true);
  await act(async () => pending.resolve(reply(classified('Old question', 'PROPORTION', ['pie_chart']))));
  expect(within(card()).queryByLabelText('Presentation types')).toBeNull();
  expect(within(card()).getByText(/Click Generate SQL to classify/)).toBeTruthy();
  expect(continueButton()).toBeNull();
  expect(generateButton().disabled).toBe(false);
});

it('rejects an invalid classification, offers Retry, and can continue without classification', async () => {
  let attempt = 0;
  const fetch = fakeFetch((body) => {
    attempt += 1;
    if (attempt === 1) return reply(classified('Show every salary'));
    if (attempt === 2) return reply({ ...classified(body.nl_query), intent: 'GENDER_SPLIT' });
    return reply({ code: 'CLASSIFICATION_UNAVAILABLE', message: 'The intent classifier could not be reached or timed out.' }, 503);
  });
  vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />);
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify(policy) } });
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify(user) } });
  typeQuestion('How many employees?');
  fireEvent.click(generateButton());
  await waitFor(() => expect(within(card()).getByRole('alert').textContent).toMatch(/different question/), WAIT);
  expect(continueButton()).toBeNull();
  fireEvent.click(within(card()).getByRole('button', { name: 'Retry classification' }));
  await waitFor(() => expect(within(card()).getByRole('alert').textContent).toMatch(/unsupported intent/), WAIT);
  fireEvent.click(within(card()).getByRole('button', { name: 'Retry classification' }));
  await waitFor(() => expect(within(card()).getByRole('alert').textContent).toMatch(/CLASSIFICATION_UNAVAILABLE/), WAIT);

  fireEvent.click(continueAnywayButton());
  await waitFor(() => expect(screen.getByLabelText('Generated SQL').value).toBe(sql));
  expect(bodiesFor(fetch, GENERATE)).toEqual([{ question: 'How many employees?', user, policy, rules: null }]);
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
  expect(bodiesFor(fetch, GENERATE)).toEqual([{ question: 'How many employees?', user, policy, rules }]);
  expect(screen.getByLabelText('User policy').value).toBe(JSON.stringify(policy));
  expect(screen.getByLabelText('Authenticated user').value).toBe(JSON.stringify(user));
  expect(screen.getByLabelText('NL-to-SQL rules').value).toBe(JSON.stringify(rules));
  expect(screen.getByText('NL-to-SQL rules sent').parentElement.querySelector('pre').textContent).toBe(JSON.stringify(rules, null, 2));
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: '{}' } });
  expect(screen.getByLabelText('Generated SQL').value).toBe(sql);
  fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
  for (const label of ['User policy', 'Authenticated user', 'NL-to-SQL rules']) expect(screen.getByLabelText(label).value).toBe('');
  expect(within(card()).queryByLabelText('Presentation types')).toBeNull();
});

it('question changes clear the classification and SQL draft; identity changes preserve both', async () => {
  vi.stubGlobal('fetch', fakeFetch());
  render(<NlPipeline />); await generate();
  typeQuestion('Show employees');
  expect(screen.queryByLabelText('Generated SQL')).toBeNull();
  expect(within(card()).queryByLabelText('Presentation types')).toBeNull();
  expect(continueButton()).toBeNull();
  await generate();
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify({ userId: 'user-102-manager' }) } });
  expect(screen.getByLabelText('Generated SQL').value).toBe(sql);
  expect(within(card()).getByLabelText('Presentation types')).toBeTruthy();
});

it('retests the same edited SQL with each current policy and identity, clearing previous results without regeneration', async () => {
  const fetch = fakeFetch(); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />); await generate();
  const edited = sql.replace('COUNT(*)', 'COUNT(id)');
  fireEvent.change(screen.getByLabelText('Generated SQL'), { target: { value: edited } });
  const validate = () => fireEvent.click(screen.getByRole('button', { name: 'Validate & execute' }));
  const secureCalls = () => bodiesFor(fetch, '/api/secure-query');
  validate();
  await screen.findByLabelText('Results', {}, WAIT);

  const testUser = { userId: 'user-102-manager', role: 'MANAGER', tenantId: 102 };
  const testPolicy = { ...policy, policyId: 'test-policy', deniedColumns: ['employees.id'] };
  // Exercise intermediate invalid text as well as a changed userId and tenant.
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: '{' } });
  expect(screen.queryByLabelText('Results')).toBeNull();
  expect(screen.queryByLabelText('Direct answer')).toBeNull();
  expect(screen.queryByText('Query approved')).toBeNull();
  expect(screen.getByLabelText('Generated SQL').value).toBe(edited);
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify(testPolicy) } });
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify(testUser) } });
  validate();
  await screen.findByLabelText('Results', {}, WAIT);
  expect(secureCalls()[1]).toEqual({ sql: edited, question: 'How many employees?', user: testUser, policy: testPolicy, rules: null, execute: true });
  expect(bodiesFor(fetch, PRESENT)[1]).toEqual({ resultId: 'result-1', user: testUser, policy: testPolicy, rules: null,
    classification: { intent: 'KPI_SINGLE_VALUE', presentation_types: ['single_value'] } });

  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify(policy) } });
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify({ ...testUser, tenantId: 101 }) } });
  validate();
  await screen.findByLabelText('Results', {}, WAIT);
  expect(secureCalls()[2]).toEqual({ sql: edited, question: 'How many employees?', user: { ...testUser, tenantId: 101 }, policy, rules: null, execute: true });
  expect(screen.getByLabelText('Generated SQL').value).toBe(edited);
  expect(bodiesFor(fetch, GENERATE)).toHaveLength(1);
  expect(bodiesFor(fetch, CLASSIFY)).toHaveLength(1);
});

it('rejects invalid testing context without losing SQL or submitting a verification request', async () => {
  const fetch = fakeFetch(); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />); await generate();
  const validate = () => fireEvent.click(screen.getByRole('button', { name: 'Validate & execute' }));
  for (const text of ['{', '{}', '[]', '']) {
    fireEvent.change(screen.getByLabelText('User policy'), { target: { value: text } });
    validate();
    expect(bodiesFor(fetch, '/api/secure-query')).toHaveLength(0);
    expect(screen.getByLabelText('Generated SQL').value).toBe(sql);
  }
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify(policy) } });
  for (const text of ['{', '{}', '{"userId":" "}', '{"userId":123}']) {
    fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: text } });
    validate();
    expect(bodiesFor(fetch, '/api/secure-query')).toHaveLength(0);
    expect(screen.getByLabelText('Generated SQL').value).toBe(sql);
  }
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify(user) } });
  validate();
  await screen.findByLabelText('Results', {}, WAIT);
  expect(bodiesFor(fetch, '/api/secure-query')).toHaveLength(1);
  expect(bodiesFor(fetch, GENERATE)).toHaveLength(1);
});

it('after execution shows the result in the classified formats, using the stored result', async () => {
  const fetch = fakeFetch(); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />); await generate();
  fireEvent.click(screen.getByRole('button', { name: 'Validate & execute' }));
  const results = await screen.findByLabelText('Results', {}, WAIT);
  await waitFor(() => expect(within(results).getAllByRole('tab').map((t) => t.textContent)).toEqual(['Single value', 'Table']), WAIT);
  expect(within(results).getByRole('tabpanel').textContent).toContain('Headcount7');
  expect(bodiesFor(fetch, PRESENT)).toEqual([{ resultId: 'result-1', user, policy, rules: null,
    classification: { intent: 'KPI_SINGLE_VALUE', presentation_types: ['single_value'] } }]);
  expect(JSON.stringify(bodiesFor(fetch, PRESENT))).not.toContain('rows');

  fireEvent.change(screen.getByLabelText('Generated SQL'), { target: { value: sql.replace('COUNT(*)', 'COUNT(id)') } });
  expect(screen.queryByLabelText('Results')).toBeNull();
});

it('without a classification asks for formats chosen from the data', async () => {
  const fetch = fakeFetch(() => reply({ code: 'CLASSIFICATION_UNAVAILABLE', message: 'offline' }, 503)); vi.stubGlobal('fetch', fetch);
  render(<NlPipeline />);
  fireEvent.change(screen.getByLabelText('User policy'), { target: { value: JSON.stringify(policy) } });
  fireEvent.change(screen.getByLabelText('Authenticated user'), { target: { value: JSON.stringify(user) } });
  typeQuestion('How many employees?');
  fireEvent.click(generateButton());
  await waitFor(() => expect(continueAnywayButton()).toBeTruthy(), WAIT);
  fireEvent.click(continueAnywayButton());
  await waitFor(() => expect(screen.getByLabelText('Generated SQL').value).toBe(sql));
  fireEvent.click(screen.getByRole('button', { name: 'Validate & execute' }));
  await waitFor(() => expect(bodiesFor(fetch, PRESENT)).toHaveLength(1), WAIT);
  expect(bodiesFor(fetch, PRESENT)[0].classification).toBeNull();
});
