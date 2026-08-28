import { useEffect, useState } from 'react';
import { api } from '../../lib/api.js';
import { dateTime, relativeTime } from '../../lib/format.js';

// Raw action codes ("settings.updated") are internal, so they get a plain
// label before anything reaches the screen.
const ACTION_LABEL = {
  'settings.updated': 'Setting changed',
  'connection.created': 'Database connected',
  'connection.deleted': 'Database removed',
  'connection.tested': 'Connection tested',
  'user.invited': 'Person invited',
  'user.updated': 'Role changed',
};
const label = (a) => ACTION_LABEL[a] || String(a).replace(/[._]/g, ' ');

export default function Activity() {
  const [audit, setAudit] = useState([]);
  const [history, setHistory] = useState([]);
  const [tab, setTab] = useState('changes');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.audit().catch(() => ({ audit: [] })),
      api.history().catch(() => ({ history: [] })),
    ]).then(([a, h]) => {
      setAudit(a.audit || []);
      setHistory(h.history || []);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="skeleton" style={{ height: 240 }} />;

  return (
    <>
      <div className="tabs mb">
        <button className={`tab${tab === 'changes' ? ' active' : ''}`} onClick={() => setTab('changes')}>
          Setting changes
        </button>
        <button className={`tab${tab === 'questions' ? ' active' : ''}`} onClick={() => setTab('questions')}>
          Questions asked
        </button>
      </div>

      {tab === 'changes' && (
        <div className="card">
          {audit.map((a) => (
            <div className="setting-row" key={a.id}>
              <div className="info">
                <h4>{label(a.action)}</h4>
                <p>{a.detail}</p>
              </div>
              <div className="ctl small muted">{a.actor} · {dateTime(a.at)}</div>
            </div>
          ))}
          {audit.length === 0 && <div className="empty"><p>Nothing has been changed yet.</p></div>}
        </div>
      )}

      {tab === 'questions' && (
        <div className="card">
          {history.map((h) => (
            <div className="setting-row" key={h.id}>
              <div className="info">
                <h4 className="q">{h.question}</h4>
                <p>{h.user} · {relativeTime(h.askedAt)}</p>
              </div>
              <div className="ctl small muted">{h.headline}</div>
            </div>
          ))}
          {history.length === 0 && <div className="empty"><p>No questions have been asked yet.</p></div>}
        </div>
      )}
    </>
  );
}
