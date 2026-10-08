// Synthetic renderer validation; requires the internal presentation service.
import assert from 'node:assert/strict';
import { compile } from 'vega-lite';
import { parse, View } from 'vega';

const url = process.env.PRESENTATION_SERVICE_URL || 'http://127.0.0.1:8004';
const input = {
  user_query: 'Chart monthly headcount and forecast the next 3 months',
  member2_result: {
    columns: [{ name: 'month' }, { name: 'headcount' }],
    rows: Array.from({ length: 24 }, (_, i) => [`${2023 + Math.floor(i / 12)}-${String(i % 12 + 1).padStart(2, '0')}-01`, 100 + 5 * i]),
    rowCount: 24, truncated: false, masking: { columns: [], maskedCells: 0 }
  },
  security_context: { tenant_id: 'chart-validation' }
};
async function request(endpoint, body) {
  const response = await fetch(`${url}/api/v4/${endpoint}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), signal: AbortSignal.timeout(30000)
  });
  assert.equal(response.ok, true);
  const envelope = await response.json();
  assert.equal(envelope.status, 'SUCCESS');
  return envelope;
}
async function verifyChart(grammar) {
  const { _meta, ...spec } = grammar;
  const view = new View(parse(compile(spec).spec), { renderer: 'none' });
  try {
    const svg = await view.toSVG();
    assert.match(svg, /<svg/);
    assert.match(svg, /<path/);
    return svg.length;
  } finally { view.finalize(); }
}
const envelope = await request('present', input);
assert.equal(envelope.prediction.stage_4_forecast.generated, true);
const forecastBytes = await verifyChart(envelope.response.chart.spec);
const scenario = await request('simulate', { ...input, scenario_text: 'Increase the forecast by 10%' });
assert.equal(scenario.scenario.simulated, true);
const scenarioBytes = await verifyChart(scenario.visualization);
console.log(`Real forecast and scenario charts compiled and rendered to SVG (${forecastBytes} / ${scenarioBytes} characters).`);
