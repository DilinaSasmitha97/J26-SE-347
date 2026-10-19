// Renders the prediction layer's forecast and anomaly charts with the real
// vega / vega-lite stack, to SVG. Requires the internal presentation service.
import assert from 'node:assert/strict';
import { compile } from 'vega-lite';
import { parse, View } from 'vega';

const url = process.env.PRESENTATION_SERVICE_URL || 'http://127.0.0.1:8004';
const table = (columns, rows) => ({ columns: columns.map((name) => ({ name })), rows, rowCount: rows.length, truncated: false, masking: { columns: [], maskedCells: 0 } });
const months = (values) => table(['month', 'hires'], values.map((v, i) => [`${2023 + Math.floor(i / 12)}-${String(i % 12 + 1).padStart(2, '0')}-01`, v]));
const cases = [
  ['trend forecast', months(Array.from({ length: 24 }, (_, i) => 100 + 4 * i)), 'TREND_ANALYSIS', true, 'Forecast monthly hires for the next 6 months', ['R1_FORECAST_MEAN', 'R2_CONFIDENCE_BAND']],
  ['forecast with a spike', months(Array.from({ length: 24 }, (_, i) => 100 + 4 * i + (i === 15 ? 60 : 0))), 'TREND_ANALYSIS', true, 'Forecast monthly hires', ['R1_FORECAST_MEAN', 'R3_ANOMALY_MARKERS']],
  ['seasonal forecast', months(Array.from({ length: 36 }, (_, i) => 200 + 30 * Math.sin((i % 12) / 12 * 2 * Math.PI) + i)), 'TREND_ANALYSIS', true, 'Predict the next 12 months', ['R1_FORECAST_MEAN']],
  ['anomaly only', months(Array.from({ length: 24 }, (_, i) => 50 + (i === 9 ? 40 : 0))), 'ANOMALY_DETECTION', false, 'Any unusual spikes in hires?', ['R3_ANOMALY_MARKERS']],
  ['per-department forecast', table(['month', 'department', 'hires'], Array.from({ length: 12 }, (_, m) => ['HR', 'IT'].map((d) => [`2024-${String(m + 1).padStart(2, '0')}-01`, d, (m + 1) * (d === 'IT' ? 2 : 1)])).flat()), 'COMPARISON', true, 'Compare hires by department and forecast', ['R5_CATEGORY_FORECASTS']]
];

async function render(spec) {
  const { _meta, ...grammar } = spec;
  const view = new View(parse(compile(grammar).spec), { renderer: 'none' });
  try {
    const svg = await view.toSVG();
    assert.match(svg, /<path/, 'the chart drew no marks');
    return svg.length;
  } finally { view.finalize(); }
}

for (const [name, result, intent, predictionNeeded, question, rules] of cases) {
  const response = await fetch(`${url}/api/v4/predict`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ member2_result: result, user_query: question, intent, prediction_needed: predictionNeeded }),
    signal: AbortSignal.timeout(60000)
  });
  const body = await response.json();
  assert.equal(body.status, 'SUCCESS', `${name}: ${body.detail || response.status}`);
  assert.ok(body.chart, `${name}: no chart (${body.chart_reason})`);
  const applied = body.chart.spec._meta.extension_rules_applied;
  for (const rule of rules) assert.ok(applied.includes(rule), `${name}: ${rule} missing from ${applied}`);
  const bytes = await render(body.chart.spec);
  console.log(`ok  ${name.padEnd(26)} ${body.readiness.verdict.padEnd(14)} model ${String(body.forecast.model).padEnd(15)} points ${String(body.forecast.points.length).padEnd(3)} ${applied.join('+')}  ${bytes} bytes SVG`);
}
