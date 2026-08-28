import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useApp } from '../context/AppContext.jsx';
import { formatValue } from '../lib/format.js';

// Brand sea green (#2E8B57). `primary` paints single-series marks in the exact
// brand colour; `series` is an ordinal ramp of the same hue for donut slices,
// which arrive sorted by value - so one hue stepping dark -> light encodes
// magnitude instead of throwing unrelated hues at a single measure. Steps are
// chosen per surface, never flipped; both ramps pass monotone-lightness,
// step-gap and surface-contrast checks.
const PALETTES = {
  light: {
    primary: '#2E8B57',
    series: ['#0f3f26', '#1d6440', '#2E8B57', '#4aa473', '#73c197'],
    grid: '#ebebeb', axis: '#767676', border: '#e2e2e2',
  },
  dark: {
    primary: '#73c197',
    series: ['#9adcb8', '#73c197', '#4aa473', '#2E8B57', '#1d6440'],
    grid: '#2b2b2b', axis: '#8a8a8a', border: '#2f2f2f',
  },
};

// "2026-06" -> "Jun 26", "2026-06-15" -> "Jun 15", quarters and weeks pass through.
function formatPeriod(p) {
  const s = String(p);
  const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  let m = s.match(/^(\d{4})-(\d{2})$/);
  if (m) return `${MONTHS[+m[2] - 1]} ${m[1].slice(2)}`;
  m = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (m) return `${MONTHS[+m[2] - 1]} ${+m[3]}`;
  return s;
}

const truncate = (s, n) => (String(s).length > n ? String(s).slice(0, n - 1) + '…' : String(s));

function ChartTooltip({ active, payload, label, valueFormat, isPeriod }) {
  if (!active || !payload || !payload.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <div className="t-label">{isPeriod ? formatPeriod(label) : label}</div>
      <div className="t-value">{formatValue(payload[0].value, valueFormat)}</div>
      {row.orders !== undefined && <div className="t-extra">{formatValue(row.orders, 'number')} orders</div>}
      {row.headcount !== undefined && <div className="t-extra">{formatValue(row.headcount, 'number')} employees</div>}
    </div>
  );
}

export default function ChartPanel({ chart, rows, view }) {
  const { theme } = useApp();
  const p = PALETTES[theme === 'dark' ? 'dark' : 'light'];
  const fmt = chart.valueFormat;
  const type = view || chart.type;

  if (!rows || !rows.length) {
    return <div className="empty"><p>No rows to plot.</p></div>;
  }

  const axisTick = { fontSize: 11.5, fill: p.axis };

  // Axis ticks read better without cents - the tooltip carries full precision.
  const tickFormatter = (v) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return String(v);
    const unit = fmt === 'currency' ? '$' : '';
    const suffix = fmt === 'percent' ? '%' : '';
    if (Math.abs(n) >= 1000000) return `${unit}${(n / 1000000).toFixed(1)}M${suffix}`;
    if (Math.abs(n) >= 1000) return `${unit}${Math.round(n / 1000)}K${suffix}`;
    return `${unit}${Math.round(n * 100) / 100}${suffix}`;
  };

  // ---- single headline number ------------------------------------------
  if (type === 'stat') {
    const row = rows[0];
    return (
      <div className="stat-hero">
        <div className="big">{formatValue(row.value, fmt)}</div>
        <div className="cap">{chart.title}</div>
      </div>
    );
  }

  // ---- time series -------------------------------------------------------
  if (type === 'line') {
    return (
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={286}>
          <LineChart data={rows} margin={{ top: 8, right: 30, bottom: 4, left: 4 }}>
            <CartesianGrid vertical={false} stroke={p.grid} />
            <XAxis
              dataKey="period"
              tick={axisTick}
              tickLine={false}
              axisLine={{ stroke: p.border }}
              tickFormatter={formatPeriod}
              interval={chart.dense ? Math.floor(rows.length / 8) : 0}
              minTickGap={8}
            />
            <YAxis
              tick={axisTick}
              tickLine={false}
              axisLine={false}
              tickFormatter={tickFormatter}
              width={62}
            />
            <Tooltip
              content={<ChartTooltip valueFormat={fmt} isPeriod />}
              cursor={{ stroke: p.axis, strokeWidth: 1, strokeDasharray: '3 3' }}
            />
            <Line
              type="monotone"
              dataKey="value"
              stroke={p.primary}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4.5, strokeWidth: 2, stroke: 'var(--surface)' }}
              name={chart.yLabel}
            />
          </LineChart>
        </ResponsiveContainer>
        <div className="chart-note">{chart.title}</div>
      </div>
    );
  }

  // ---- composition -------------------------------------------------------
  if (type === 'donut') {
    const total = rows.reduce((s, r) => s + Number(r.value || 0), 0);
    return (
      <div className="chart-wrap">
        <ResponsiveContainer width="100%" height={286}>
          <PieChart>
            <Pie
              data={rows}
              dataKey="value"
              nameKey="label"
              innerRadius={62}
              outerRadius={100}
              paddingAngle={2}
              stroke="var(--surface)"
              strokeWidth={2}
            >
              {rows.map((_, i) => (
                <Cell key={i} fill={p.series[i % p.series.length]} />
              ))}
            </Pie>
            <Tooltip content={<ChartTooltip valueFormat={fmt} />} />
            <Legend
              verticalAlign="middle"
              align="right"
              layout="vertical"
              iconType="circle"
              iconSize={8}
              formatter={(v, entry) => (
                <span style={{ color: 'var(--text-2)', fontSize: 12.5 }}>
                  {truncate(v, 22)}
                  <span style={{ color: 'var(--text-3)' }}>
                    {'  '}{total ? ((entry.payload.value / total) * 100).toFixed(0) : 0}%
                  </span>
                </span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="chart-note">{chart.title}</div>
      </div>
    );
  }

  // ---- magnitude across categories --------------------------------------
  const horizontal = chart.orientation === 'horizontal';
  const xKey = chart.xKey || 'label';
  const barHeight = Math.max(286, rows.length * 30 + 40);

  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height={horizontal ? barHeight : 286}>
        <BarChart
          data={rows}
          layout={horizontal ? 'vertical' : 'horizontal'}
          margin={{ top: 8, right: 20, bottom: 4, left: 4 }}
          barCategoryGap={horizontal ? 8 : '22%'}
        >
          <CartesianGrid
            vertical={horizontal}
            horizontal={!horizontal}
            stroke={p.grid}
          />
          {horizontal ? (
            <>
              <XAxis type="number" tick={axisTick} tickLine={false} axisLine={{ stroke: p.border }} tickFormatter={tickFormatter} />
              <YAxis
                type="category"
                dataKey={xKey}
                tick={axisTick}
                tickLine={false}
                axisLine={false}
                width={148}
                tickFormatter={(v) => truncate(v, 20)}
              />
            </>
          ) : (
            <>
              <XAxis
                dataKey={xKey}
                tick={axisTick}
                tickLine={false}
                axisLine={{ stroke: p.border }}
                tickFormatter={(v) => truncate(v, 14)}
                interval={0}
              />
              <YAxis tick={axisTick} tickLine={false} axisLine={false} tickFormatter={tickFormatter} width={62} />
            </>
          )}
          <Tooltip
            content={<ChartTooltip valueFormat={fmt} isPeriod={xKey === 'period'} />}
            cursor={{ fill: 'var(--surface-3)', opacity: 0.55 }}
          />
          <Bar
            dataKey="value"
            fill={p.primary}
            radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}
            maxBarSize={horizontal ? 22 : 54}
            name={chart.yLabel}
          />
        </BarChart>
      </ResponsiveContainer>
      <div className="chart-note">{chart.title}</div>
    </div>
  );
}
