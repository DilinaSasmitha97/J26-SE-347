import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext.jsx';
import Avatar from './Avatar.jsx';
import { IconSun, IconMoon, IconLogout, IconCheck, IconDatabase, IconSettings } from './Icons.jsx';

// A Google-style account button: a bare avatar floating in the corner that
// opens a popover holding everything the old top bar used to carry -
// identity, the active database, the theme switch and sign out.
function AccountMenu() {
  const { user, logout, theme, toggleTheme, connections, connectionId, setConnectionId, isOwner } = useApp();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const navigate = useNavigate();
  const active = connections.find((c) => c.id === connectionId);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKeyDown = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div className="account" ref={wrapRef}>
      <button
        className="account-btn"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account: ${user?.name}`}
        title={user?.name}
      >
        <Avatar user={user} size="lg" />
        <span
          className={`account-status ${active?.status === 'connected' ? 'is-ok' : 'is-bad'}`}
          title={active?.status === 'connected' ? `Connected to ${active?.name}` : active?.statusMessage || 'Offline'}
        />
      </button>

      {open && (
        <div className="account-menu" role="menu">
          <div className="account-id">
            <Avatar user={user} size="xl" />
            <div style={{ minWidth: 0 }}>
              <div className="account-name">{user?.name}</div>
              <div className="account-mail">{user?.email}</div>
              <span className="pill pill-accent" style={{ marginTop: 8 }}>{user?.role}</span>
            </div>
          </div>

          <div className="account-section">
            <div className="account-label"><IconDatabase /> Database</div>
            {connections.map((c) => (
              <button
                key={c.id}
                className={`account-item${c.id === connectionId ? ' is-active' : ''}`}
                onClick={() => { setConnectionId(c.id); setOpen(false); }}
                role="menuitemradio"
                aria-checked={c.id === connectionId}
              >
                <span className={`dot ${c.status === 'connected' ? 'dot-ok' : 'dot-bad'}`} />
                <span className="account-item-text">
                  <span className="account-item-name">{c.name}</span>
                  <span className="account-item-sub">{c.engine} · {c.status}</span>
                </span>
                {c.id === connectionId && <IconCheck />}
              </button>
            ))}
          </div>

          <div className="account-section">
            {isOwner && (
              <button className="account-item" onClick={() => navigate('/admin')} role="menuitem">
                <IconSettings />
                <span className="account-item-text">
                  <span className="account-item-name">Admin console</span>
                </span>
              </button>
            )}
            <button className="account-item" onClick={toggleTheme} role="menuitem">
              {theme === 'dark' ? <IconSun /> : <IconMoon />}
              <span className="account-item-text">
                <span className="account-item-name">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</span>
              </span>
            </button>
            <button className="account-item is-danger" onClick={logout} role="menuitem">
              <IconLogout />
              <span className="account-item-text">
                <span className="account-item-name">Sign out</span>
              </span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function Shell({ children }) {
  return (
    <div className="shell">
      <main className="main">
        <AccountMenu />
        {children}
      </main>
    </div>
  );
}
