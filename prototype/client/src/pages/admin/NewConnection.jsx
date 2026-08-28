import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../../lib/api.js';
import { useApp } from '../../context/AppContext.jsx';
import { IconChevron, IconCheck, IconShield, IconDatabase } from '../../components/Icons.jsx';

// MySQL is the only database type this build supports.
const MYSQL_PORT = 3306;

export default function NewConnection() {
  const { toast, refreshConnections, setConnectionId } = useApp();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [touched, setTouched] = useState(false);
  const [form, setForm] = useState({
    name: '', engine: 'mysql', host: '', port: MYSQL_PORT,
    database: '', username: 'askdb_reader', password: '', ssl: true,
  });

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const missing = {
    name: !form.name.trim(),
    host: !form.host.trim(),
    database: !form.database.trim(),
  };
  const invalid = Object.values(missing).some(Boolean);

  const submit = async (e) => {
    e.preventDefault();
    setTouched(true);
    if (invalid) {
      toast('Fill in the highlighted fields first.', 'err');
      return;
    }
    setBusy(true);
    try {
      const { connection } = await api.createConnection(form);
      await refreshConnections();
      setConnectionId(connection.id);
      navigate(`/admin/connections/${connection.id}/setup`);
    } catch (err) {
      toast(err.message, 'err');
    } finally {
      setBusy(false);
    }
  };

  const err = (k) => touched && missing[k];

  return (
    <form className="new-conn" onSubmit={submit}>
      <button type="button" className="back-link" onClick={() => navigate('/admin/connections')}>
        <IconChevron size={14} style={{ transform: 'rotate(90deg)' }} />
        Back to databases
      </button>

      <div className="new-conn-grid">
        <div className="col" style={{ gap: 16 }}>
          <section className="card">
            <div className="card-head"><h3>1 · What is it called</h3></div>
            <div className="card-pad col" style={{ gap: 16 }}>
              <div className="field">
                <label htmlFor="nc-name">Display name</label>
                <input
                  id="nc-name"
                  className={`input${err('name') ? ' has-error' : ''}`}
                  value={form.name}
                  onChange={set('name')}
                  placeholder="Production analytics"
                  autoFocus
                />
                <span className={err('name') ? 'hint hint-error' : 'hint'}>
                  {err('name') ? 'Give the database a name your team will recognise.' :
                    'This is what your team sees when choosing a database.'}
                </span>
              </div>
            </div>
          </section>

          <section className="card">
            <div className="card-head"><h3>2 · Where to find it</h3></div>
            <div className="card-pad col" style={{ gap: 16 }}>
              <div className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="nc-host">Host</label>
                  <input
                    id="nc-host"
                    className={`input${err('host') ? ' has-error' : ''}`}
                    value={form.host}
                    onChange={set('host')}
                    placeholder="db.internal"
                  />
                  {err('host') && <span className="hint hint-error">A host address is required.</span>}
                </div>
                <div className="field" style={{ width: 130 }}>
                  <label htmlFor="nc-port">Port</label>
                  <input id="nc-port" className="input" type="number" value={form.port} onChange={set('port')} />
                </div>
              </div>
              <div className="field">
                <label htmlFor="nc-db">Database name</label>
                <input
                  id="nc-db"
                  className={`input${err('database') ? ' has-error' : ''}`}
                  value={form.database}
                  onChange={set('database')}
                  placeholder="analytics"
                />
                {err('database') && <span className="hint hint-error">Name the database to read from.</span>}
              </div>
            </div>
          </section>

          <section className="card">
            <div className="card-head"><h3>3 · How to sign in</h3></div>
            <div className="card-pad col" style={{ gap: 16 }}>
              <div className="row" style={{ gap: 14, alignItems: 'flex-start' }}>
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="nc-user">Username</label>
                  <input id="nc-user" className="input" value={form.username} onChange={set('username')} />
                </div>
                <div className="field" style={{ flex: 1 }}>
                  <label htmlFor="nc-pass">Password</label>
                  <input id="nc-pass" className="input" type="password" value={form.password}
                    onChange={set('password')} placeholder="••••••••" />
                </div>
              </div>
              <div className="toggle-row">
                <button
                  type="button"
                  className="switch"
                  data-on={form.ssl}
                  onClick={() => setForm((f) => ({ ...f, ssl: !f.ssl }))}
                  aria-label="Require a secure connection"
                />
                <div>
                  <div className="toggle-title">Require a secure connection</div>
                  <div className="toggle-sub">Encrypts traffic between AskDB and your database.</div>
                </div>
              </div>
            </div>
          </section>

          <div className="form-actions">
            <button type="button" className="btn" onClick={() => navigate('/admin/connections')}>
              Cancel
            </button>
            <button className="btn btn-primary" disabled={busy}>
              {busy ? 'Connecting…' : 'Add database'}
            </button>
          </div>
        </div>

        <aside className="col new-conn-side" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-head"><h3>Summary</h3></div>
            <div className="card-pad col" style={{ gap: 12 }}>
              <div className="summary-row">
                <span className="engine-badge">MY</span>
                <div style={{ minWidth: 0 }}>
                  <div className="summary-name">{form.name.trim() || 'Untitled database'}</div>
                  <div className="summary-target">
                    {form.host.trim() || 'host'}:{form.port}/{form.database.trim() || 'database'}
                  </div>
                </div>
              </div>
              <div className="summary-line">
                <IconDatabase size={14} />
                MySQL database
              </div>
              <div className="summary-line">
                <IconShield size={14} />
                {form.ssl ? 'Secure connection required' : 'Not encrypted'}
              </div>
              <div className="summary-line">
                <IconCheck size={14} />
                Signing in as {form.username.trim() || 'no user set'}
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-head"><h3>What happens next</h3></div>
            <div className="card-pad">
              <ol className="steps-list">
                <li>We connect and read the list of tables and fields.</li>
                <li>Nothing is copied out and nothing is ever changed — AskDB only reads.</li>
                <li>You choose which tables your team is allowed to ask about.</li>
              </ol>
            </div>
          </div>

          <div className="alert alert-info">
            In this demo build only the two sample databases carry data, so a new
            connection is saved but stays offline.
          </div>
        </aside>
      </div>
    </form>
  );
}
