const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const { once } = require('node:events');
const { createApp } = require('../src/index');
const { classificationProblem } = require('../src/services/intentClassificationService');

const question = 'Give me the gender distribution in my company';
const contract = { nl_query: question, presentation_types: ['table', 'pie_chart', 'bar_chart'], prediction_needed: false };

function post(server, path, body) {
  return new Promise((resolve, reject) => {
    const request = http.request({
      host: '127.0.0.1', port: server.address().port, path,
      method: 'POST', headers: { 'Content-Type': 'application/json' }
    }, (response) => {
      let text = '';
      response.setEncoding('utf8');
      response.on('data', (chunk) => { text += chunk; });
      response.on('end', () => resolve({ status: response.statusCode, body: JSON.parse(text) }));
    });
    request.on('error', reject);
    request.end(JSON.stringify(body));
  });
}

async function serve(t, dependencies) {
  const server = createApp(dependencies).listen(0, '127.0.0.1');
  await once(server, 'listening');
  t.after(() => new Promise((resolve) => server.close(resolve)));
  return server;
}

function upstream(t, reply) {
  const calls = [];
  t.mock.method(global, 'fetch', async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return reply(url, options);
  });
  return calls;
}

test('classification forwards only the question and needs no user, policy or rules', async (t) => {
  const calls = upstream(t, () => ({ ok: true, json: async () => ({ ...contract, source: 'llm' }) }));
  const server = await serve(t);
  const response = await post(server, '/api/classify-intent', {
    nl_query: question,
    user: { userId: 'u-1', tenantId: 101 }, policy: { allowedTables: ['employees'] }, rules: { constraints: ['x'] }
  });
  assert.equal(response.status, 200);
  assert.deepEqual(response.body, contract, 'Only the three contract fields are returned');
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'http://127.0.0.1:8004/api/v4/classify-intent');
  assert.deepEqual(calls[0].body, { nl_query: question });

  const bare = await post(server, '/api/classify-intent', { nl_query: question });
  assert.equal(bare.status, 200);
  assert.deepEqual(calls[1].body, { nl_query: question });
});

test('the submitted question is forwarded and echoed without trimming', async (t) => {
  const spaced = '  How many employees?  ';
  const calls = upstream(t, () => ({ ok: true, json: async () => ({ nl_query: spaced, presentation_types: ['single_value'], prediction_needed: false }) }));
  const response = await post(await serve(t), '/api/classify-intent', { nl_query: spaced });
  assert.equal(response.status, 200);
  assert.equal(calls[0].body.nl_query, spaced);
  assert.equal(response.body.nl_query, spaced);
});

test('invalid questions are rejected before the classifier is called', async (t) => {
  const calls = upstream(t, () => assert.fail('Invalid questions must not reach the classifier'));
  const server = await serve(t);
  for (const body of [{}, { nl_query: '' }, { nl_query: '   ' }, { nl_query: 'x'.repeat(2001) }, { nl_query: 7 }, { question }]) {
    const response = await post(server, '/api/classify-intent', body);
    assert.equal(response.status, 400, JSON.stringify(body).slice(0, 40));
    assert.equal(response.body.code, 'INVALID_REQUEST');
  }
  assert.equal(calls.length, 0);
});

test('out-of-contract classifier responses are rejected', async (t) => {
  const invalid = [
    { ...contract, nl_query: 'Show every salary' },
    { ...contract, presentation_types: [] },
    { ...contract, presentation_types: ['table', 'donut_chart'] },
    { ...contract, presentation_types: ['table', 'table'] },
    { ...contract, presentation_types: 'table' },
    { ...contract, prediction_needed: 'false' },
    { nl_query: question, presentation_types: ['table'] },
    [contract]
  ];
  let next = 0;
  upstream(t, () => ({ ok: true, json: async () => invalid[next++] }));
  const server = await serve(t);
  for (const payload of invalid) {
    const response = await post(server, '/api/classify-intent', { nl_query: question });
    assert.equal(response.status, 502, JSON.stringify(payload));
    assert.equal(response.body.code, 'CLASSIFICATION_INVALID');
  }
  assert.equal(classificationProblem(contract, question), null);
});

test('classifier outages and HTTP errors are reported without a classification', async (t) => {
  let mode = 'offline';
  upstream(t, () => {
    if (mode === 'offline') throw new Error('connect ECONNREFUSED');
    return { ok: false, status: 422, json: async () => ({ detail: [] }) };
  });
  const server = await serve(t);
  const offline = await post(server, '/api/classify-intent', { nl_query: question });
  assert.equal(offline.status, 503);
  assert.equal(offline.body.code, 'CLASSIFICATION_UNAVAILABLE');
  assert.equal(offline.body.presentation_types, undefined);
  mode = 'http-error';
  const rejected = await post(server, '/api/classify-intent', { nl_query: question });
  assert.equal(rejected.status, 502);
  assert.equal(rejected.body.code, 'CLASSIFICATION_FAILED');
});

test('a cancelled browser request aborts the upstream classification', async (t) => {
  let upstreamSignal;
  const started = new Promise((resolve) => {
    t.mock.method(global, 'fetch', (url, options) => {
      upstreamSignal = options.signal;
      resolve();
      return new Promise((_, reject) => options.signal.addEventListener('abort', () => reject(options.signal.reason)));
    });
  });
  const server = await serve(t);
  const request = http.request({
    host: '127.0.0.1', port: server.address().port, path: '/api/classify-intent',
    method: 'POST', headers: { 'Content-Type': 'application/json' }
  });
  request.on('error', () => {});
  request.end(JSON.stringify({ nl_query: question }));
  await started;
  request.destroy();
  await new Promise((resolve) => {
    if (upstreamSignal.aborted) return resolve();
    upstreamSignal.addEventListener('abort', resolve);
  });
  assert.equal(upstreamSignal.aborted, true);
});
