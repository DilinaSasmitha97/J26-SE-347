import { useState } from 'react';
import ChartPanel from './ChartPanel.jsx';
import { formatValue, toCsv, downloadCsv } from '../lib/format.js';
import { useApp } from '../context/AppContext.jsx';
import {
  IconChart, IconTable, IconSteps,
  IconDownload, IconRefresh, IconAlert, IconCheck,
} from './Icons.jsx';

function DataTable({ columns, rows }) {
  if (!rows.length) return <div className="empty"><p>No matching records were found.</p></div>;
  return (
    <>
      <div className="table-scroll" style={{ maxHeight: 420, overflowY: 'auto' }}>
        <table className="data">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} className={c.type === 'measure' ? 'num' : ''}>{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={c.key} className={c.type === 'measure' ? 'num' : ''}>
                    {c.type === 'measure' ? formatValue(r[c.key], c.format) : String(r[c.key] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-foot">{rows.length} row{rows.length === 1 ? '' : 's'}</div>
    </>
  );
}

export default function AnswerCard({ result, onFollowUp, onRerun }) {
  const { toast } = useApp();
  const hasChart = result.chart && !['empty', 'table'].includes(result.chart.type);
  const [tab, setTab] = useState(hasChart ? 'chart' : 'table');
  const [chartView, setChartView] = useState(null);

  const { answer, chart, rows = [], columns = [], steps = [] } = result;
  const alternates = (chart && chart.alternates) || [];
  const isTextHeadline = /[a-z]/i.test(String(answer.headline)) && !/^[$+\-0-9]/.test(String(answer.headline));

  const exportCsv = () => {
    downloadCsv('askdb-result.csv', toCsv(columns, rows));
    toast('Downloaded askdb-result.csv', 'ok');
  };

  const tabs = [
    hasChart && { id: 'chart', label: 'Chart', Icon: IconChart },
    rows.length > 0 && { id: 'table', label: 'Table', Icon: IconTable },
    steps.length > 0 && { id: 'steps', label: 'How I got this', Icon: IconSteps },
  ].filter(Boolean);

  // The meta strip stays free of internals - no confidence score, no plan
  // type, no database table names.
  const showMeta = result.status !== 'ok' || result.rowCount > 0;

  return (
    <div className="answer fade-in">
      {showMeta && (
        <div className="answer-meta">
          {result.status === 'blocked' && <span className="pill pill-bad"><IconAlert size={12} /> Not permitted</span>}
          {result.status === 'clarify' && <span className="pill pill-warn"><IconAlert size={12} /> Needs detail</span>}
          {result.status === 'error' && <span className="pill pill-bad"><IconAlert size={12} /> Something went wrong</span>}
          <div className="spacer" />
          {result.rowCount > 0 && (
            <span>{result.rowCount} result{result.rowCount === 1 ? '' : 's'}</span>
          )}
        </div>
      )}

      <div className="answer-body">
        <div className={`headline${isTextHeadline ? ' text' : ''}`}>{answer.headline}</div>
        <div className="subline">{answer.subline}</div>

        {answer.insights?.length > 0 && (
          <div className="insights">
            {answer.insights.map((it, i) => (
              <div className="insight" key={i}>
                <div className="k">{it.label}</div>
                <div className={`v ${it.tone || ''}`}>{it.value}</div>
              </div>
            ))}
          </div>
        )}

        <p className="description">{answer.description}</p>

        {result.lowConfidence && result.status === 'ok' && (
          <div className="alert alert-warn mt">
            This one was a little unclear. Open “How I got this” to check it matches what you meant.
          </div>
        )}
        {result.metricInferred && result.status === 'ok' && !result.lowConfidence && (
          <div className="alert alert-info mt">
            The question did not say what to measure, so {result.plan?.metric} was used.
          </div>
        )}
      </div>

      {tabs.length > 0 && (
        <>
          <div className="tabs">
            {tabs.map((t) => (
              <button
                key={t.id}
                className={`tab${tab === t.id ? ' active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                <span className="row gap-sm"><t.Icon size={14} />{t.label}</span>
              </button>
            ))}
          </div>

          <div className="tab-panel">
            {tab === 'chart' && (
              <>
                {alternates.filter((a) => a !== 'table').length > 0 && (
                  <div className="row gap-sm mb">
                    <button
                      className={`btn btn-sm${!chartView ? ' btn-primary' : ''}`}
                      onClick={() => setChartView(null)}
                    >
                      {chart.type === 'bar' ? 'Bar' : chart.type === 'line' ? 'Line' : 'Default'}
                    </button>
                    {alternates.filter((a) => a !== 'table').map((a) => (
                      <button
                        key={a}
                        className={`btn btn-sm${chartView === a ? ' btn-primary' : ''}`}
                        onClick={() => setChartView(a)}
                      >
                        {a[0].toUpperCase() + a.slice(1)}
                      </button>
                    ))}
                  </div>
                )}
                <ChartPanel chart={chart} rows={rows} view={chartView} />
              </>
            )}
            {tab === 'table' && <DataTable columns={columns} rows={rows} />}
            {tab === 'steps' && (
              <div className="steps">
                {steps.map((s, i) => (
                  <div className="step" key={i}>
                    <div className="step-num">{i + 1}</div>
                    <div>
                      <h4>{s.title}</h4>
                      <p>{s.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {rows.length > 0 && (
        <div className="answer-actions">
          <button className="btn btn-sm" onClick={exportCsv}><IconDownload /> Download</button>
          {onRerun && (
            <button className="btn btn-sm btn-ghost" onClick={onRerun}><IconRefresh /> Ask again</button>
          )}
          <div className="spacer" />
          <span className="small muted row gap-sm"><IconCheck size={13} /> View only — your data is never changed</span>
        </div>
      )}

      {result.followUps?.length > 0 && onFollowUp && (
        <div className="followups">
          <div className="label">Follow-up questions</div>
          {result.followUps.map((f, i) => (
            <button className="chip" key={i} onClick={() => onFollowUp(f)}>{f}</button>
          ))}
        </div>
      )}
    </div>
  );
}
