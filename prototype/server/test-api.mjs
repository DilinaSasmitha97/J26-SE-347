const BASE = 'http://localhost:4000/api';

async function call(path, { method = 'GET', body, token } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  return { status: res.status, data: await res.json().catch(() => null) };
}

const login = async (email) => (await call('/auth/login', { method: 'POST', body: { email, password: 'demo1234' } })).data.token;

let pass = 0, fail = 0;
const check = (name, cond, extra = '') => {
  if (cond) { pass++; console.log(`  PASS  ${name}`); }
  else { fail++; console.log(`  FAIL  ${name} ${extra}`); }
};

const admin = await login('admin@askdb.io');
const viewer = await login('viewer@askdb.io');

console.log('\n1. Role permissions');
const denied = await call('/admin/settings/retail', { method: 'PUT', body: { max_rows: 100 }, token: viewer });
check('viewer cannot change settings', denied.status === 403, `got ${denied.status}`);
const allowed = await call('/admin/settings/retail', { method: 'PUT', body: { max_rows: 500 }, token: admin });
check('owner can change settings', allowed.status === 200);
check('unauthenticated request is rejected', (await call('/overview')).status === 401);

console.log('\n2. Access control changes the answer');
await call('/admin/settings/retail', { method: 'PUT', body: { blocked_tables: ['products'] }, token: admin });
const blocked = await call('/ask', { method: 'POST', body: { question: 'Top 5 products by revenue', connectionId: 'retail' }, token: admin });
check('question needing a blocked table is refused', blocked.data.status === 'blocked', blocked.data.status);
await call('/admin/settings/retail', { method: 'PUT', body: { blocked_tables: [] }, token: admin });
const unblocked = await call('/ask', { method: 'POST', body: { question: 'Top 5 products by revenue', connectionId: 'retail' }, token: admin });
check('same question works once unblocked', unblocked.data.status === 'ok', unblocked.data.status);

console.log('\n3. Business glossary rewrites vocabulary');
await call('/admin/settings/retail', {
  method: 'PUT',
  body: { glossary: [{ id: 'gx', term: 'takings', maps_to: 'revenue' }] },
  token: admin,
});
const glossary = await call('/ask', { method: 'POST', body: { question: 'What were our takings last month?', connectionId: 'retail' }, token: admin });
check('custom term resolves to revenue', glossary.data.plan?.metric === 'Revenue', glossary.data.plan?.metric);
check('glossary use is shown in the steps', JSON.stringify(glossary.data.steps).includes('glossary'));

console.log('\n4. PII masking');
await call('/admin/settings/retail', { method: 'PUT', body: { mask_pii: 'mask' }, token: admin });
const masked = await call('/ask', { method: 'POST', body: { question: 'Top 3 customers by revenue', connectionId: 'retail' }, token: admin });
const maskedName = masked.data.rows?.[0]?.label || '';
check('customer names are masked', /^[A-Za-z]+ [A-Z]\.$/.test(maskedName), maskedName);
await call('/admin/settings/retail', { method: 'PUT', body: { mask_pii: 'off' }, token: admin });
const full = await call('/ask', { method: 'POST', body: { question: 'Top 3 customers by revenue', connectionId: 'retail' }, token: admin });
check('names returned in full when masking is off', !/ [A-Z]\.$/.test(full.data.rows?.[0]?.label || ''), full.data.rows?.[0]?.label);
await call('/admin/settings/retail', { method: 'PUT', body: { mask_pii: 'mask' }, token: admin });

console.log('\n5. Presentation settings');
await call('/admin/settings/retail', { method: 'PUT', body: { show_sql: false, show_reasoning: false }, token: admin });
const hidden = await call('/ask', { method: 'POST', body: { question: 'Revenue last month', connectionId: 'retail' }, token: admin });
check('SQL hidden when disabled', hidden.data.sql === null);
check('reasoning hidden when disabled', hidden.data.steps.length === 0);
await call('/admin/settings/retail', { method: 'PUT', body: { show_sql: true, show_reasoning: true }, token: admin });

console.log('\n6. Row limit is enforced');
await call('/admin/settings/retail', { method: 'PUT', body: { max_rows: 3 }, token: admin });
const capped = await call('/ask', { method: 'POST', body: { question: 'Revenue by product', connectionId: 'retail' }, token: admin });
check('row cap applied', capped.data.rows.length <= 3, `${capped.data.rows.length} rows`);
await call('/admin/settings/retail', { method: 'PUT', body: { max_rows: 500 }, token: admin });

console.log('\n7. Offline connection');
const offline = await call('/ask', { method: 'POST', body: { question: 'Revenue last month', connectionId: 'billing' }, token: admin });
check('offline connection reports an error', offline.data.status === 'error', offline.data.status);

console.log('\n8. Answer payload completeness');
const full2 = await call('/ask', { method: 'POST', body: { question: 'Show revenue by month over the last 12 months', connectionId: 'retail' }, token: admin });
const a = full2.data;
check('has short answer', !!a.answer.headline);
check('has description', a.answer.description.length > 40);
check('has chart spec', a.chart.type === 'line');
check('has table columns', a.columns.length >= 2);
check('has SQL', !!a.sql);
check('has reasoning steps', a.steps.length >= 3);
check('has follow-ups', a.followUps.length > 0);
check('history recorded it', (await call('/history', { token: admin })).data.history.some((h) => h.id === a.id));

console.log(`\n${pass} passed, ${fail} failed\n`);
process.exit(fail ? 1 : 0);
