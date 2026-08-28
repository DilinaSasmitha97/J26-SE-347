// ---------------------------------------------------------------------------
// Result -> language. Produces the short answer, the supporting paragraph and
// the insight chips shown above the table.
// ---------------------------------------------------------------------------

const nf = new Intl.NumberFormat('en-US');
const nf2 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function formatValue(value, format, { compact = false } = {}) {
  if (value === null || value === undefined || Number.isNaN(value)) return '-';
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);

  if (format === 'currency') {
    if (compact && Math.abs(n) >= 1000000) return '$' + (n / 1000000).toFixed(2) + 'M';
    if (compact && Math.abs(n) >= 10000) return '$' + (n / 1000).toFixed(1) + 'K';
    return '$' + nf2.format(n);
  }
  if (format === 'percent') return nf2.format(n) + '%';
  if (format === 'decimal') return nf2.format(n);
  if (compact && Math.abs(n) >= 1000000) return (n / 1000000).toFixed(2) + 'M';
  return nf.format(Math.round(n * 100) / 100);
}

const pctChange = (curr, prev) => (!prev ? null : ((curr - prev) / Math.abs(prev)) * 100);

// "category" -> "categories", "priority" -> "priorities", "region" -> "regions"
function plural(word) {
  const w = String(word);
  if (/[^aeiou]y$/i.test(w)) return w.slice(0, -1) + 'ies';
  if (/(s|x|z|ch|sh)$/i.test(w)) return w + 'es';
  return w + 's';
}

function periodPhrase(plan) {
  return plan.timeRange ? `in ${plan.timeRange.label}` : 'across the full history';
}

function filterPhrase(plan) {
  if (!plan.filters.length) return '';
  return ' for ' + plan.filters.map((f) => `${f.label} = ${f.value}`).join(' and ');
}

export function narrate(plan, result, comparison) {
  const { rows } = result;
  const metric = plan.metric;
  const fmt = metric.format;

  if (!rows.length || (rows.length === 1 && (rows[0].value === null || rows[0].value === undefined))) {
    return {
      headline: 'No matching data',
      subline: `${metric.label} ${periodPhrase(plan)}`,
      description: `The query ran successfully but returned no rows${filterPhrase(plan)}. Either the filters are too narrow or that period has no records in this database.`,
      insights: [],
    };
  }

  // ---- single number ----------------------------------------------------
  if (!plan.dimension && !plan.timeGrain) {
    const value = rows[0].value;
    const insights = [{ label: metric.label, value: formatValue(value, fmt) }];

    let deltaSentence = '';
    if (comparison && comparison.value !== null && comparison.value !== undefined) {
      const change = pctChange(Number(value), Number(comparison.value));
      if (change !== null && Number.isFinite(change)) {
        const dir = change >= 0 ? 'up' : 'down';
        insights.push({
          label: 'vs previous period',
          value: (change >= 0 ? '+' : '') + change.toFixed(1) + '%',
          tone: change >= 0 ? 'positive' : 'negative',
        });
        deltaSentence = ` That is ${dir} ${Math.abs(change).toFixed(1)}% compared with the preceding period, which came to ${formatValue(comparison.value, fmt)}.`;
      }
    }
    if (rows[0].orders !== undefined) {
      insights.push({ label: 'Orders', value: formatValue(rows[0].orders, 'number') });
    }

    return {
      headline: formatValue(value, fmt, { compact: true }),
      subline: `${metric.label} ${periodPhrase(plan)}`,
      description: `${metric.label} ${periodPhrase(plan)}${filterPhrase(plan)} is ${formatValue(value, fmt)}, calculated as ${metric.description}.${deltaSentence}`,
      insights,
    };
  }

  // ---- time series ------------------------------------------------------
  if (plan.timeGrain) {
    const series = rows.filter((r) => r.value !== null && r.value !== undefined);
    const first = series[0];
    const last = series[series.length - 1];
    const values = series.map((r) => Number(r.value));
    const total = values.reduce((s, v) => s + v, 0);
    const avg = total / (values.length || 1);
    const peak = series.reduce((a, b) => (Number(b.value) > Number(a.value) ? b : a), series[0]);
    const trough = series.reduce((a, b) => (Number(b.value) < Number(a.value) ? b : a), series[0]);
    const change = series.length > 1 ? pctChange(Number(last.value), Number(first.value)) : null;

    const dirWord = change === null ? 'stayed flat'
      : change > 3 ? `grew ${change.toFixed(1)}%`
        : change < -3 ? `fell ${Math.abs(change).toFixed(1)}%`
          : 'stayed broadly flat';

    const isSum = ['currency', 'number'].includes(fmt) && metric.id !== 'aov' && metric.id !== 'avg_csat';

    return {
      headline: change === null ? formatValue(last.value, fmt, { compact: true })
        : `${change >= 0 ? '+' : ''}${change.toFixed(1)}%`,
      subline: `${metric.label} by ${plan.timeGrain.label.toLowerCase()}, ${first.period} to ${last.period}`,
      description: `${metric.label} ${dirWord} between ${first.period} (${formatValue(first.value, fmt)}) and ${last.period} (${formatValue(last.value, fmt)}). `
        + `The strongest ${plan.timeGrain.label.toLowerCase()} was ${peak.period} at ${formatValue(peak.value, fmt)} and the weakest was ${trough.period} at ${formatValue(trough.value, fmt)}, `
        + `with a ${plan.timeGrain.label.toLowerCase()}ly average of ${formatValue(avg, fmt)} across ${series.length} periods${filterPhrase(plan)}.`,
      insights: [
        ...(isSum ? [{ label: 'Total', value: formatValue(total, fmt, { compact: true }) }] : []),
        { label: 'Average', value: formatValue(avg, fmt, { compact: true }) },
        { label: 'Peak', value: `${peak.period} · ${formatValue(peak.value, fmt, { compact: true })}` },
        { label: 'Change', value: change === null ? '-' : `${change >= 0 ? '+' : ''}${change.toFixed(1)}%`, tone: change >= 0 ? 'positive' : 'negative' },
      ],
    };
  }

  // ---- grouped / ranked -------------------------------------------------
  const top = rows[0];
  const total = rows.reduce((s, r) => s + Number(r.value || 0), 0);
  const share = total ? (Number(top.value) / total) * 100 : null;
  const dimLabel = plan.dimension.label.toLowerCase();
  const superlative = plan.direction === 'ASC' ? 'lowest' : 'highest';

  const named = rows.slice(0, 3).map((r) => `${r.label} (${formatValue(r.value, fmt)})`);
  const listSentence = named.length > 1
    ? `The leading ${plural(dimLabel)} are ${named.slice(0, -1).join(', ')} and ${named[named.length - 1]}.`
    : '';

  const isAverage = ['aov', 'avg_csat', 'avg_salary', 'avg_rating', 'margin_pct', 'avg_discount'].includes(metric.id);

  return {
    headline: String(top.label),
    subline: `${superlative} ${metric.label} · ${formatValue(top.value, fmt, { compact: true })}`,
    description: `${top.label} has the ${superlative} ${metric.label.toLowerCase()} ${periodPhrase(plan)}${filterPhrase(plan)} at ${formatValue(top.value, fmt)}`
      + (share !== null && !isAverage ? `, which is ${share.toFixed(1)}% of the ${formatValue(total, fmt)} across the ${rows.length} ${plural(dimLabel)} returned. ` : '. ')
      + listSentence,
    insights: [
      { label: `Top ${dimLabel}`, value: String(top.label) },
      { label: metric.label, value: formatValue(top.value, fmt, { compact: true }) },
      ...(isAverage ? [] : [{ label: 'Share of total', value: share === null ? '-' : share.toFixed(1) + '%' }]),
      { label: plural(plan.dimension.label), value: formatValue(rows.length, 'number') },
    ],
  };
}
