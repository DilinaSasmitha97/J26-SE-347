import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../../context/AppContext.jsx';
import { formatValue, relativeTime } from '../../lib/format.js';
import { IconPlus, IconChevron } from '../../components/Icons.jsx';

const engineCode = (e) => (e === 'mysql' ? 'MY' : String(e).slice(0, 2).toUpperCase());

export default function Connections() {
  const { connections, refreshConnections, connectionId, isOwner } = useApp();
  const navigate = useNavigate();

  useEffect(() => { refreshConnections(); }, [refreshConnections]);

  const online = connections.filter((c) => c.status === 'connected').length;

  return (
    <>
      <div className="admin-actions">
        <span className="lead">
          {connections.length} {connections.length === 1 ? 'database' : 'databases'} · {online} online
        </span>
        <div className="spacer" />
        {isOwner && (
          <button className="btn btn-sm" onClick={() => navigate('/admin/connections/new')}>
            <IconPlus /> Connect a database
          </button>
        )}
      </div>

      {connections.length === 0 ? (
        <div className="card">
          <div className="empty">
            <h3>No databases yet</h3>
            <p>Connect a MySQL database and your team can start asking questions about it.</p>
          </div>
        </div>
      ) : (
        <div className="conn-grid">
          {connections.map((c) => {
            const isOnline = c.status === 'connected';
            return (
              <button
                key={c.id}
                className={`card conn-card${connectionId === c.id ? ' is-selected' : ''}`}
                onClick={() => navigate(`/admin/connections/${c.id}`)}
              >
                <div className="conn-top">
                  <span className="engine-badge">{engineCode(c.engine)}</span>
                  <span className="conn-id">
                    <span className="conn-name">{c.name}</span>
                    <span className="conn-host">{c.host}/{c.database}</span>
                  </span>
                  <span className={`status ${isOnline ? 'is-on' : 'is-off'}`}>
                    <span className="dot" />{isOnline ? 'Online' : 'Offline'}
                  </span>
                </div>

                <div className="conn-meta">
                  <span><b>{c.tableCount || '—'}</b> tables</span>
                  <span><b>{c.rowCount ? formatValue(c.rowCount, 'number') : '—'}</b> records</span>
                  <span>{c.ssl ? 'Secure' : 'Not secure'}</span>
                </div>

                <div className="conn-foot">
                  <span className="small muted">
                    {c.lastSyncedAt ? `Checked ${relativeTime(c.lastSyncedAt)}` : 'Never checked'}
                  </span>
                  <div className="spacer" />
                  {connectionId === c.id && <span className="conn-selected">Selected</span>}
                  <IconChevron size={14} style={{ transform: 'rotate(-90deg)', color: 'var(--text-3)' }} />
                </div>
              </button>
            );
          })}
        </div>
      )}
    </>
  );
}
