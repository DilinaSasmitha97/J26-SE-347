// Renders every chart the data presentation layer returns, with the real
// vega / vega-lite stack, to SVG. Requires the internal presentation service.
import assert from 'node:assert/strict';
import { compile } from 'vega-lite';
import { parse, View } from 'vega';

const url = process.env.PRESENTATION_SERVICE_URL || 'http://127.0.0.1:8004';
const table = (columns, rows) => ({ columns: columns.map((name) => ({ name })), rows, rowCount: rows.length, truncated: false, masking: { columns: [], maskedCells: 0 } });
const cases = [
  ['gender share', table(['gender', 'headcount'], [['Female', 42], ['Male', 51]]), ['pie_chart', 'bar_chart']],
  ['salary by department (string decimals)', table(['department', 'avg_salary'], [['HR', '52000.50'], ['IT', '71000.25'], ['Sales', '48000.00']]), ['bar_chart', 'pie_chart']],
  ['monthly hires', table(['month', 'hires'], Array.from({ length: 12 }, (_, i) => [`2024-${String(i + 1).padStart(2, '0')}-01`, i + 3])), ['line_chart', 'bar_chart']],
  ['hires per year (year numbers)', table(['hire_year', 'hires'], Array.from({ length: 10 }, (_, i) => [2015 + i, i + 5])), ['line_chart']],
  ['grouped monthly hires', table(['month', 'department', 'hires'], [1, 2, 3, 4].flatMap((m) => ['HR', 'IT'].map((d) => [`2024-0${m}-01`, d, m]))), ['line_chart', 'bar_chart']],
  ['two categories', table(['department', 'gender', 'n'], [['HR', 'F', 3], ['HR', 'M', 2], ['IT', 'F', 4], ['IT', 'M', 6]]), ['bar_chart']],
  ['40 job titles', table(['job_title', 'n'], Array.from({ length: 40 }, (_, i) => [`Title ${i}`, i])), ['bar_chart']]
];

async function render(spec) {
  const view = new View(parse(compile(spec).spec), { renderer: 'none' });
  try {
    const svg = await view.toSVG();
    assert.match(svg, /<svg/);
    assert.match(svg, /<path/, 'the chart drew no marks');
    return svg.length;
  } finally { view.finalize(); }
}

let charts = 0;
for (const [name, result, types] of cases) {
  const response = await fetch(`${url}/api/v4/render`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ member2_result: result, user_query: name, intent: null, presentation_types: types }),
    signal: AbortSignal.timeout(30000)
  });
  assert.equal(response.ok, true, `${name}: HTTP ${response.status}`);
  const body = await response.json();
  assert.equal(body.status, 'SUCCESS', name);
  for (const view of body.views) {
    assert.equal(view.available, true, `${name} / ${view.type}: ${view.reason}`);
    const bytes = await render(view.block.spec);
    charts += 1;
    console.log(`ok  ${name.padEnd(40)} ${view.type.padEnd(10)} ${bytes} bytes of SVG`);
  }
}
console.log(`Rendered ${charts} charts with vega-lite ${(await import('vega-lite')).version}.`);
