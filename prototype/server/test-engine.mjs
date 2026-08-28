import { ask } from './src/engine/pipeline.js';
import { CONNECTIONS } from './src/store.js';

const retail = CONNECTIONS.find((c) => c.id === 'retail');
const hr = CONNECTIONS.find((c) => c.id === 'peopleops');

const questions = [
  ['What was our total revenue last quarter?', retail],
  ['Show me revenue by month over the last 12 months', retail],
  ['Top 5 products by revenue this year', retail],
  ['Which region has the highest average order value?', retail],
  ['How many orders did we get last month?', retail],
  ['Revenue by category in Europe in 2025', retail],
  ['What is the gross profit by category?', retail],
  ['Lowest performing product categories by units sold', retail],
  ['How many customers bought from us this year?', retail],
  ['Show support tickets by priority', retail],
  ['What is the average csat?', retail],
  ['Revenue trend by quarter', retail],
  ['Sales in Electronics for Enterprise customers', retail],
  ['what is our gmv this year', retail],
  ['Headcount by department', hr],
  ['Average salary by location', hr],
  ['banana pancakes', retail],
];

let failures = 0;
for (const [q, conn] of questions) {
  const r = ask({ question: q, connection: conn, user: 'test' });
  const ok = r.status === 'ok' || r.status === 'clarify' || r.status === 'blocked';
  if (!ok) failures++;
  console.log('\n─────────────────────────────────────────────');
  console.log('Q:', q, `[${conn.id}]`);
  console.log('   status   :', r.status, '| conf', r.confidence, '|', r.executionMs + 'ms', '| rows', r.rowCount ?? 0);
  console.log('   headline :', r.answer.headline, '—', r.answer.subline);
  console.log('   desc     :', r.answer.description);
  console.log('   chart    :', r.chart.type, r.chart.orientation || '');
  if (r.rows && r.rows.length) console.log('   row[0]   :', JSON.stringify(r.rows[0]));
  if (r.sql) console.log('   sql      :', r.sql.replace(/\n/g, '\n              '));
}
console.log('\n\nfailures:', failures);
