import { useCallback, useEffect, useState } from 'react';
import { api } from '../../lib/api.js';
import { useApp } from '../../context/AppContext.jsx';
import { relativeTime } from '../../lib/format.js';
import Avatar from '../../components/Avatar.jsx';
import { IconPlus } from '../../components/Icons.jsx';

const ROLES = [
  { id: 'owner', label: 'Owner', blurb: 'Full control, including these settings' },
  { id: 'viewer', label: 'Viewer', blurb: 'Can ask questions and download results' },
];

export default function Users() {
  const { isOwner, toast, user: me } = useApp();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [inviting, setInviting] = useState(false);
  const [invite, setInvite] = useState({ name: '', email: '', role: 'viewer' });

  const load = useCallback(async () => {
    try {
      const { users: list } = await api.users();
      setUsers(list || []);
    } catch {
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sendInvite = async (e) => {
    e.preventDefault();
    try {
      await api.inviteUser(invite);
      toast(`Invited ${invite.email}`, 'ok');
      setInvite({ name: '', email: '', role: 'viewer' });
      setInviting(false);
      load();
    } catch (err) {
      toast(err.message, 'err');
    }
  };

  const changeRole = async (u, role) => {
    try {
      await api.updateUser(u.id, { role });
      toast(`${u.name} is now ${role}`, 'ok');
      load();
    } catch (err) {
      toast(err.message, 'err');
    }
  };

  if (loading) return <div className="skeleton" style={{ height: 240 }} />;

  return (
    <>
      <div className="admin-actions">
        <span className="lead">
          {users.length} {users.length === 1 ? 'person has' : 'people have'} access
        </span>
        <div className="spacer" />
        {isOwner && (
          <button className="btn btn-primary" onClick={() => setInviting(true)}>
            <IconPlus /> Invite someone
          </button>
        )}
      </div>

      <div className="card mb">
        <div className="card-head"><h3>People with access</h3></div>
        {users.map((u) => (
          <div className="setting-row" key={u.id}>
            <Avatar user={u} />
            <div className="info">
              <h4>
                {u.name}
                {u.id === me?.id && <span className="pill pill-accent" style={{ marginLeft: 8 }}>you</span>}
              </h4>
              <p>{u.email} · last seen {relativeTime(u.lastActive)}</p>
            </div>
            <div className="ctl">
              <select
                className="select"
                value={u.role}
                disabled={!isOwner || u.id === me?.id}
                title={u.id === me?.id ? 'You cannot change your own role' : undefined}
                onChange={(e) => changeRole(u, e.target.value)}
              >
                {ROLES.map((r) => <option key={r.id} value={r.id}>{r.label}</option>)}
              </select>
            </div>
          </div>
        ))}
      </div>

      <div className="card">
        <div className="card-head"><h3>What each role can do</h3></div>
        {ROLES.map((r) => (
          <div className="setting-row" key={r.id}>
            <div className="info">
              <h4>{r.label}</h4>
              <p>{r.blurb}</p>
            </div>
            <div className="ctl small muted">
              {users.filter((u) => u.role === r.id).length} {users.filter((u) => u.role === r.id).length === 1 ? 'person' : 'people'}
            </div>
          </div>
        ))}
      </div>

      {inviting && (
        <div className="modal-backdrop" onClick={() => setInviting(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={sendInvite}>
            <div className="modal-head">
              <h3>Invite a teammate</h3>
              <p>They will be able to ask questions about the databases you allow.</p>
            </div>
            <div className="modal-body">
              <div className="field">
                <label>Name</label>
                <input className="input" value={invite.name} placeholder="Alex Fernando"
                  onChange={(e) => setInvite({ ...invite, name: e.target.value })} />
              </div>
              <div className="field">
                <label>Email</label>
                <input className="input" type="email" required value={invite.email} placeholder="alex@company.com"
                  onChange={(e) => setInvite({ ...invite, email: e.target.value })} />
              </div>
              <div className="field">
                <label>Role</label>
                <select className="select" value={invite.role}
                  onChange={(e) => setInvite({ ...invite, role: e.target.value })}>
                  {ROLES.map((r) => <option key={r.id} value={r.id}>{r.label} — {r.blurb.toLowerCase()}</option>)}
                </select>
              </div>
            </div>
            <div className="modal-foot">
              <button type="button" className="btn" onClick={() => setInviting(false)}>Cancel</button>
              <button className="btn btn-primary">Send invite</button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
