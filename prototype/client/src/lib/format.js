const nf = new Intl.NumberFormat('en-US');
const nf2 = new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export function formatValue(value, format, { compact = false } = {}) {
  if (value === null || value === undefined || value === '') return '—';
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
  if (compact && Math.abs(n) >= 10000) return (n / 1000).toFixed(1) + 'K';
  return nf.format(Math.round(n * 100) / 100);
}

export function relativeTime(iso) {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.round(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export const dateTime = (iso) =>
  !iso ? '—' : new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });

export function toCsv(columns, rows) {
  const esc = (v) => {
    const s = v === null || v === undefined ? '' : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const head = columns.map((c) => esc(c.label)).join(',');
  const body = rows.map((r) => columns.map((c) => esc(r[c.key])).join(',')).join('\n');
  return `${head}\n${body}`;
}

export function downloadCsv(filename, csv) {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// Very small SQL highlighter - enough to make the query panel read well.
const KEYWORDS = /\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|LIMIT|JOIN|LEFT JOIN|INNER JOIN|ON|AND|OR|NOT IN|IN|AS|DESC|ASC|HAVING|DISTINCT|CASE|WHEN|THEN|ELSE|END)\b/g;
const FUNCS = /\b(SUM|COUNT|AVG|ROUND|MIN|MAX|SUBSTR|COALESCE)\s*\(/g;

export function highlightSql(sql) {
  if (!sql) return '';
  const escaped = sql.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return escaped
    .replace(/'([^']*)'/g, "<span class='str'>'$1'</span>")
    .replace(KEYWORDS, "<span class='kw'>$1</span>")
    .replace(FUNCS, "<span class='fn'>$1</span>(")
    .replace(/\b(\d+\.?\d*)\b/g, "<span class='num'>$1</span>");
}
