import { useCallback, useEffect, useState } from 'react';
import { api } from '../../lib/api.js';
import { useApp } from '../../context/AppContext.jsx';
import { IconPlus } from '../../components/Icons.jsx';

const engineCode = (e) => (e === 'mysql' ? 'MY' : String(e).slice(0, 2).toUpperCase());

const TABS = [
  { id: 'answers', label: 'Answers', blurb: 'What an answer looks like and how much it explains' },
  { id: 'limits', label: 'Limits', blurb: 'How much work a single question may cost' },
  { id: 'privacy', label: 'Privacy', blurb: 'What personal and commercial detail may be shown' },
  { id: 'wording', label: 'Your wording', blurb: 'Teach the system the words your company uses' },
  { id: 'visibility', label: 'Tables', blurb: 'Which tables people may ask about' },
];

function Row({ title, description, children }) {
  return (
    <div className="setting-row">
      <div className="info">
        <h4>{title}</h4>
        <p>{description}</p>
      </div>
      <div className="ctl">{children}</div>
    </div>
  );
}

export default function Configure() {
  const { connections, connectionId, setConnectionId, connection, isOwner, toast } = useApp();
  const [tab, setTab] = useState('answers');
  const [settings, setSettings] = useState(null);
  const [schema, setSchema] = useState([]);
  const [saving, setSaving] = useState(false);
  const [term, setTerm] = useState({ term: '', maps_to: '' });

  const load = useCallback(async () => {
    if (!connectionId) return;
    setSettings(null);
    const [s, sc] = await Promise.all([
      api.settings(connectionId).catch(() => null),
      api.schema(connectionId).catch(() => ({ tables: [] })),
    ]);
    if (s) setSettings(s.settings);
    setSchema(sc.tables || []);
  }, [connectionId]);

  useEffect(() => { load(); }, [load]);

  // Each change writes straight through, so its effect shows up on the ask
  // screen immediately.
  const save = async (patch) => {
    if (!isOwner) return toast('Only workspace owners can change settings.', 'err');
    setSettings((cur) => ({ ...cur, ...patch }));
    setSaving(true);
    try {
      await api.saveSettings(connectionId, patch);
      toast('Saved', 'ok');
    } catch (err) {
      toast(err.message, 'err');
      load();
    } finally {
      setSaving(false);
    }
  };

  const addTerm = (e) => {
    e.preventDefault();
    if (!term.term.trim() || !term.maps_to.trim()) return;
    save({ glossary: [...(settings.glossary || []), { id: `g${Date.now()}`, ...term }] });
    setTerm({ term: '', maps_to: '' });
  };

  const Switch = ({ k }) => (
    <button
      className="switch"
      data-on={!!settings[k]}
      disabled={!isOwner || saving}
      onClick={() => save({ [k]: !settings[k] })}
      aria-label={k}
    />
  );

  return (
    <>
      <div className="card config-bar">
        <span className="engine-badge">{engineCode(connection?.engine)}</span>
        <div className="config-bar-id">
          <span className="config-bar-name">{connection?.name}</span>
          <span className="config-bar-sub">Settings below apply only to this database</span>
        </div>
        <div className="spacer" />
        <label htmlFor="cfg-db" className="small muted">Configuring</label>
        <select
          id="cfg-db"
          className="select"
          value={connectionId || ''}
          onChange={(e) => setConnectionId(e.target.value)}
          style={{ width: 'auto' }}
        >
          {connections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {!isOwner && (
        <div className="alert alert-warn mb">
          Your role cannot change these settings, so they are shown read-only.
        </div>
      )}

      {!settings ? (
        <div className="skeleton" style={{ height: 260 }} />
      ) : (
        <>
          <div className="segmented">
            {TABS.map((t) => (
              <button
                key={t.id}
                className={`segment${tab === t.id ? ' active' : ''}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="config-head">
            <h2>{TABS.find((t) => t.id === tab)?.label}</h2>
            <p>{TABS.find((t) => t.id === tab)?.blurb}</p>
          </div>

          {tab === 'answers' && (
            <div className="card">
              <Row title="Show charts automatically" description="Pick a chart that suits the shape of each answer.">
                <Switch k="auto_chart" />
              </Row>
              <Row title="Show how the answer was reached" description="Adds a plain-language breakdown under every answer.">
                <Switch k="show_reasoning" />
              </Row>
              <Row title="Amount of detail" description="How much explanation accompanies the short answer.">
                <select className="select" value={settings.narrative_style} disabled={!isOwner}
                  onChange={(e) => save({ narrative_style: e.target.value })}>
                  <option value="concise">Brief</option>
                  <option value="balanced">Balanced</option>
                  <option value="detailed">Detailed</option>
                </select>
              </Row>
              <Row title="Ignore cancelled and refunded orders" description="Revenue answers skip orders that never completed, unless the question asks about order status.">
                <Switch k="exclude_cancelled" />
              </Row>
            </div>
          )}

          {tab === 'limits' && (
            <div className="card">
              <Row title="Most records per answer" description="Stops a very broad question from pulling an entire table.">
                <select className="select" value={settings.max_rows} disabled={!isOwner}
                  onChange={(e) => save({ max_rows: Number(e.target.value) })}>
                  {[100, 250, 500, 1000, 5000].map((n) => <option key={n} value={n}>{n} records</option>)}
                </select>
              </Row>
              <Row title="Give up after" description="A question taking longer than this is stopped, so one heavy request cannot slow the database.">
                <select className="select" value={settings.timeout_ms} disabled={!isOwner}
                  onChange={(e) => save({ timeout_ms: Number(e.target.value) })}>
                  {[5000, 15000, 30000, 60000].map((n) => <option key={n} value={n}>{n / 1000} seconds</option>)}
                </select>
              </Row>
              <Row title="Combine information from several tables" description="Turn off to keep answers to one table at a time.">
                <Switch k="allow_joins" />
              </Row>
            </div>
          )}

          {tab === 'privacy' && (
            <div className="card">
              <Row title="Names, emails and phone numbers" description="How personal details appear in answers.">
                <select className="select" value={settings.mask_pii} disabled={!isOwner}
                  onChange={(e) => save({ mask_pii: e.target.value })}>
                  <option value="off">Show in full</option>
                  <option value="mask">Shorten (Nimal P.)</option>
                  <option value="block">Never show</option>
                </select>
              </Row>
              <Row title="Hide commercially sensitive figures" description="Cost, profit margin, salary and performance figures become unavailable to questions.">
                <Switch k="hide_sensitive_metrics" />
              </Row>
              <Row title="Never changes your data" description="AskDB only ever reads. This is always on and cannot be turned off.">
                <span className="pill pill-ok"><span className="dot" />always on</span>
              </Row>
            </div>
          )}

          {tab === 'wording' && (
            <div className="card">
              <div className="card-pad" style={{ paddingBottom: 10 }}>
                <p className="small muted">
                  Teach the system the words your company uses. Map “top line” to “revenue”
                  and anyone can ask about the top line and get the right answer.
                </p>
              </div>
              {(settings.glossary || []).map((g) => (
                <div className="glossary-row" key={g.id}>
                  <span className="term">{g.term}</span>
                  <span className="arrow">→</span>
                  <span className="term">{g.maps_to}</span>
                  <div className="spacer" />
                  {isOwner && (
                    <button
                      className="btn btn-sm btn-ghost"
                      onClick={() => save({ glossary: settings.glossary.filter((x) => x.id !== g.id) })}
                    >
                      Remove
                    </button>
                  )}
                </div>
              ))}
              {(settings.glossary || []).length === 0 && (
                <div className="empty"><p>No custom wording yet.</p></div>
              )}
              {isOwner && (
                <form className="card-pad row glossary-add" onSubmit={addTerm}>
                  <input className="input" placeholder="Your word" value={term.term}
                    onChange={(e) => setTerm({ ...term, term: e.target.value })} />
                  <span className="arrow">→</span>
                  <input className="input" placeholder="What it means (e.g. revenue)" value={term.maps_to}
                    onChange={(e) => setTerm({ ...term, maps_to: e.target.value })} />
                  <button className="btn btn-primary"><IconPlus /> Add</button>
                </form>
              )}
            </div>
          )}

          {tab === 'visibility' && (
            <div className="card">
              <div className="card-pad" style={{ paddingBottom: 10 }}>
                <p className="small muted">
                  Turn a table off to keep it out of every answer. People will be told it is
                  unavailable rather than getting a partial result.
                </p>
              </div>
              {schema.map((t) => {
                const blocked = (settings.blocked_tables || []).includes(t.name);
                return (
                  <div className="setting-row" key={t.name}>
                    <div className="info">
                      <h4>{t.label || t.name}</h4>
                      <p>{t.description}</p>
                    </div>
                    <div className="ctl">
                      {blocked && <span className="pill pill-bad">hidden</span>}
                      <button
                        className="switch"
                        data-on={!blocked}
                        disabled={!isOwner || saving}
                        onClick={() => {
                          const list = settings.blocked_tables || [];
                          save({
                            blocked_tables: blocked
                              ? list.filter((x) => x !== t.name)
                              : [...list, t.name],
                          });
                        }}
                        aria-label={`Allow ${t.name}`}
                      />
                    </div>
                  </div>
                );
              })}
              {schema.length === 0 && (
                <div className="empty"><p>This database is offline, so its tables are unknown.</p></div>
              )}
            </div>
          )}
        </>
      )}
    </>
  );
}
