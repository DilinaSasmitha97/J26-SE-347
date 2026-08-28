// ---------------------------------------------------------------------------
// Picks the chart form from the shape of the answer, following the rule that
// the data's job chooses the form:
//   change over time -> line
//   magnitude across categories -> bar (horizontal once labels get long)
//   one headline number -> no chart, a stat tile
//   composition of a few parts -> bar, with a donut offered as an alternate
// ---------------------------------------------------------------------------

const ADDITIVE = new Set(['revenue', 'order_count', 'units', 'profit', 'ticket_count', 'headcount', 'total_salary']);

export function visualise(plan, result) {
  const rows = result.rows || [];
  const fmt = plan.metric.format;

  if (!rows.length) {
    return { type: 'empty', valueFormat: fmt, alternates: ['table'] };
  }

  // One number -> a hero stat, not a chart.
  if (!plan.dimension && !plan.timeGrain) {
    return {
      type: 'stat',
      valueFormat: fmt,
      title: plan.metric.label,
      alternates: ['table'],
    };
  }

  if (plan.timeGrain) {
    return {
      type: 'line',
      xKey: 'period',
      yKey: 'value',
      valueFormat: fmt,
      title: `${plan.metric.label} by ${plan.timeGrain.label.toLowerCase()}`,
      xLabel: plan.timeGrain.label,
      yLabel: plan.metric.label,
      // Long series get too many ticks to label; let the client thin them.
      dense: rows.length > 14,
      alternates: ['bar', 'table'],
    };
  }

  const longestLabel = rows.reduce((m, r) => Math.max(m, String(r.label ?? '').length), 0);
  const horizontal = longestLabel > 14 || rows.length > 8;
  const additive = ADDITIVE.has(plan.metric.id);

  return {
    type: 'bar',
    orientation: horizontal ? 'horizontal' : 'vertical',
    xKey: 'label',
    yKey: 'value',
    valueFormat: fmt,
    title: `${plan.metric.label} by ${plan.dimension.label.toLowerCase()}`,
    xLabel: plan.dimension.label,
    yLabel: plan.metric.label,
    // A donut only makes sense for parts of a whole, and only a few parts.
    // Five is the cap: that is how many steps the ordinal brand ramp resolves
    // into with visible lightness gaps, and slices past it stop being legible.
    alternates: additive && rows.length <= 5 ? ['donut', 'table'] : ['table'],
  };
}
