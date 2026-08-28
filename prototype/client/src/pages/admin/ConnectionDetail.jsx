import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api } from '../../lib/api.js';
import { useApp } from '../../context/AppContext.jsx';
import { formatValue, dateTime } from '../../lib/format.js';
import { IconChevron, IconRefresh, IconSettings, IconCheck } from '../../components/Icons.jsx';

const engineName = (e) => (e === 'mysql' ? 'MySQL' : String(e || '').toUpperCase());
const engineCode = (e) => (e === 'mysql' ? 'MY' : String(e).slice(0, 2).toUpperCase());

function TableList({ connectionId }) {
  const [schema, setSchema] = useState(null);
  const [open, setOpen] = useState(null);
  const [samples, setSamples] = useState({});

  useEffect(() => {
    setSchema(null);
    setOpen(null);
    api.schema(connectionId).then(setSchema).catch(() => setSchema({ tables: [] }));
  }, [connectionId]);

  const toggle = async (table) => {
    const next = open === table.name ? null : table.name;
    setOpen(next);
    if (next && !samples[table.name]) {
      try {
        const { rows } = await api.sample(connectionId, table.name);
        setSamples((s) => ({ ...s, [table.name]: rows }));
      } catch { /* sample data is optional */ }
    }
  };

  if (!schema) return <div className="card-pad"><div className="skeleton" style={{ height: 160 }} /></div>;
  if (!schema.tables.length) {
    return (
      <div className="empty">
        <h3>Nothing to show yet</h3>
        <p>This database is offline, so its contents have not been read.</p>
      </div>
    );
  }

  return (
    <div className="card-pad col" style={{ gap: 8 }}>
      {schema.tables.map((t) => (
        <div className="schema-table" key={t.name}>
          <div className="schema-head" onClick={() => toggle(t)}>
            <IconChevron
              size={14}
              style={{
                transform: open === t.name ? 'rotate(0deg)' : 'rotate(-90deg)',
                transition: 'transform .15s', color: 'var(--text-3)',
              }}
            />
            <span className="n">{t.label || t.name}</span>
            <span className="d">{t.description}</span>
            <div className="spacer" />
            {t.blocked && <span className="pill pill-bad">hidden</span>}
            <span className="pill">{formatValue(t.rowCount, 'number')} records</span>
            <span className="pill">{t.columns.length} fields</span>
          </div>

          {open === t.name && (
            <div className="schema-cols">
              {t.columns.map((c) => (
                <div className="col-row" key={c.name}>
                  <div className="cn">
                    {c.name}
                    {c.name === t.primaryKey && <span className="tag tag-pk">id</span>}
                    {c.pii && <span className="tag tag-pii">personal</span>}
                    {c.sensitive && <span className="tag tag-sens">sensitive</span>}
                  </div>
                  <div className="ct">{c.type}</div>
                  <div className="cd">{c.description}</div>
                </div>
              ))}

              {samples[t.name]?.length > 0 && (
                <div className="schema-sample">
                  <div className="small muted mb">Sample records</div>
                  <div className="table-scroll">
                    <table className="data">
                      <thead>
                        <tr>{Object.keys(samples[t.name][0]).slice(0, 7).map((k) => <th key={k}>{k}</th>)}</tr>
                      </thead>
                      <tbody>
                        {samples[t.name].slice(0, 5).map((r, i) => (
                          <tr key={i}>
                            {Object.keys(samples[t.name][0]).slice(0, 7).map((k) => (
                              <td key={k}>{String(r[k] ?? '—')}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

export default function ConnectionDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { connectionId, setConnectionId, refreshConnections, toast, isOwner } = useApp();
  const [conn, setConn] = useState(null);
  const [testing, setTesting] = useState(false);
  const [missing, setMissing] = useState(false);

  const load = useCallback(() => {
    api.connection(id)
      .then((r) => setConn(r.connection))
      .catch(() => setMissing(true));
  }, [id]);

  useEffect(() => { load(); }, [load]);

  const test = async () => {
    setTesting(true);
    try {
      const res = await api.testConnection(id);
      toast(res.message, res.ok ? 'ok' : 'err');
      load();
      refreshConnections();
    } catch (err) {
      toast(err.message, 'err');
    } finally {
      setTesting(false);
    }
  };

  const remove = async () => {
    if (!window.confirm(`Remove “${conn.name}”? Your team will no longer be able to ask questions about it. The database itself is not touched.`)) return;
    try {
      await api.deleteConnection(id);
      toast(`${conn.name} was removed`, 'ok');
      await refreshConnections();
      navigate('/admin/connections');
    } catch (err) {
      toast(err.message, 'err');
    }
  };

  if (missing) {
    return (
      <div className="empty">
        <h3>Database not found</h3>
        <p>It may have been removed.</p>
        <button className="btn btn-sm" onClick={() => navigate('/admin/connections')}>Back to databases</button>
      </div>
    );
  }
  if (!conn) return <div className="skeleton" style={{ height: 280 }} />;

  const online = conn.status === 'connected';
  const isActive = connectionId === conn.id;

  return (
    <>
      <button className="back-link" onClick={() => navigate('/admin/connections')}>
        <IconChevron size={14} style={{ transform: 'rotate(90deg)' }} />
        Back to databases
      </button>

      <div className="card detail-head">
        <div className="detail-id">
          <span className="engine-badge">{engineCode(conn.engine)}</span>
          <div style={{ minWidth: 0 }}>
            <h2>{conn.name}</h2>
            <p className="mono">{conn.host}:{conn.port}/{conn.database}</p>
          </div>
          <span className={`pill ${online ? 'pill-ok' : 'pill-bad'}`}>
            <span className="dot" />{online ? 'online' : 'offline'}
          </span>
        </div>

        {conn.statusMessage && !online && (
          <div className="alert alert-warn">{conn.statusMessage}</div>
        )}

        <div className="detail-facts">
          <div><span>Type</span><b>{engineName(conn.engine)}</b></div>
          <div><span>Signs in as</span><b>{conn.username}</b></div>
          <div><span>Connection</span><b>{conn.ssl ? 'Secure' : 'Not secure'}</b></div>
          <div><span>Tables</span><b>{conn.tableCount || '—'}</b></div>
          <div><span>Records</span><b>{conn.rowCount ? formatValue(conn.rowCount, 'number') : '—'}</b></div>
          <div><span>Last checked</span><b>{conn.lastSyncedAt ? dateTime(conn.lastSyncedAt) : 'Never'}</b></div>
        </div>

        <div className="detail-actions">
          <button className="btn btn-sm" onClick={test} disabled={testing}>
            <IconRefresh /> {testing ? 'Testing…' : 'Test connection'}
          </button>
          <button
            className={`btn btn-sm${isActive ? ' btn-primary' : ''}`}
            onClick={() => { setConnectionId(conn.id); toast(`${conn.name} selected`, 'ok'); }}
            disabled={isActive}
          >
            {isActive ? <><IconCheck /> Selected</> : 'Select'}
          </button>
          <button
            className="btn btn-sm"
            onClick={() => { setConnectionId(conn.id); navigate('/admin/configure'); }}
          >
            <IconSettings /> Configure
          </button>
          <div className="spacer" />
          {isOwner && (
            <button className="btn btn-sm btn-ghost btn-danger" onClick={remove}>Remove</button>
          )}
        </div>
      </div>

      <section className="card">
        <div className="card-head">
          <h3>Tables</h3>
          <div className="spacer" />
          <p>Select a table to see its fields and a few sample records</p>
        </div>
        <TableList connectionId={id} />
      </section>
    </>
  );
}
