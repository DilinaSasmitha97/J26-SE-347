import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api.js';
import { formatValue, relativeTime } from '../../lib/format.js';
import { IconPlus, IconAlert } from '../../components/Icons.jsx';

const engineCode = (e) => (e === 'mysql' ? 'MY' : String(e).slice(0, 2).toUpperCase());

function Stat({ label, value, detail }) {
  return (
    <div className="stat">
      <span className="k">{label}</span>
      <span className="v">{value}</span>
      <span className="s">{detail}</span>
    </div>
  );
}

// Status reads better as a coloured dot beside plain text than as a filled
// pill, which shouts in a dense table.
function Status({ online }) {
  return (
    <span className={`status ${online ? 'is-on' : 'is-off'}`}>
      <span className="dot" />{online ? 'Online' : 'Offline'}
    </span>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api.overview().then(setData).catch(() => setData({ stats: {}, recent: [], connections: [] }));
  }, []);

  if (!data) return <div className="skeleton" style={{ height: 280 }} />;

  const s = data.stats || {};
  const connections = data.connections || [];
  const recent = (data.recent || []).slice(0, 4);
  const offline = connections.filter((c) => c.status !== 'connected');

  return (
    <>
      <div className="card stat-strip">
        <Stat
          label="Databases"
          value={formatValue(s.connections, 'number')}
          detail={`${s.connected || 0} online · ${offline.length} offline`}
        />
        <Stat
          label="Records available"
          value={formatValue(s.rowsIndexed, 'number')}
          detail="ready to be asked about"
        />
        <Stat
          label="Questions asked"
          value={formatValue(s.questions, 'number')}
          detail={s.avgResponseMs ? `answered in ${s.avgResponseMs} ms on average` : 'no questions yet'}
        />
        <Stat
          label="People"
          value={formatValue(s.users, 'number')}
          detail="with access to this workspace"
        />
      </div>

      {offline.length > 0 && (
        <div className="notice">
          <IconAlert size={16} />
          <span className="notice-text">
            <b>
              {offline.length === 1
                ? `${offline[0].name} is offline`
                : `${offline.length} databases are offline`}
            </b>
            {' — '}nobody can ask questions about {offline.length === 1 ? 'it' : 'them'}.
          </span>
          <button className="btn btn-sm" onClick={() => navigate('/admin/connections')}>
            Review
          </button>
        </div>
      )}

      <div className="admin-grid">
        <section className="card">
          <div className="card-head">
            <h3>Databases</h3>
            <div className="spacer" />
            <button className="btn btn-sm" onClick={() => navigate('/admin/connections/new')}>
              <IconPlus /> Connect
            </button>
          </div>

          {connections.length === 0 ? (
            <div className="empty"><p>No databases connected yet.</p></div>
          ) : (
            <table className="data dash-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Status</th>
                    <th className="num">Tables</th>
                    <th className="num">Records</th>
                  </tr>
                </thead>
                <tbody>
                  {connections.map((c) => (
                    <tr key={c.id} onClick={() => navigate('/admin/connections')}>
                      <td>
                        <span className="dash-name">
                          <span className="engine-badge sm">{engineCode(c.engine)}</span>
                          <span>
                            <b>{c.name}</b>
                            <em>{c.host}/{c.database}</em>
                          </span>
                        </span>
                      </td>
                      <td><Status online={c.status === 'connected'} /></td>
                      <td className="num">{c.tableCount || '—'}</td>
                      <td className="num">{c.rowCount ? formatValue(c.rowCount, 'number') : '—'}</td>
                    </tr>
                  ))}
                </tbody>
            </table>
          )}
        </section>

        <section className="card">
          <div className="card-head">
            <h3>Recent questions</h3>
            <div className="spacer" />
            <button className="btn btn-sm btn-ghost" onClick={() => navigate('/admin/activity')}>
              View all
            </button>
          </div>

          {recent.length === 0 ? (
            <div className="empty"><p>No questions have been asked yet.</p></div>
          ) : (
            <ul className="feed">
              {recent.map((h) => (
                <li key={h.id}>
                  <div className="feed-main">
                    <span className="feed-q">{h.question}</span>
                    <span className="feed-meta">{h.user} · {relativeTime(h.askedAt)}</span>
                  </div>
                  {h.headline && <span className="feed-answer">{h.headline}</span>}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
