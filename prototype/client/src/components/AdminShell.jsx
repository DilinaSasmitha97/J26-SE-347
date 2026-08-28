import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext.jsx';
import Avatar from './Avatar.jsx';
import {
  IconGrid, IconDatabase, IconSettings, IconUsers, IconHistory,
  IconSparkle, IconSun, IconMoon, IconLogout,
} from './Icons.jsx';

const NAV = [
  { to: '/admin', end: true, label: 'Dashboard', Icon: IconGrid },
  { to: '/admin/connections', label: 'Databases', Icon: IconDatabase },
  { to: '/admin/configure', label: 'Configuration', Icon: IconSettings },
  { to: '/admin/users', label: 'Users & roles', Icon: IconUsers },
  { to: '/admin/activity', label: 'Activity', Icon: IconHistory },
];

const TITLES = {
  '/admin': ['Dashboard', 'Health and usage across your workspace'],
  '/admin/connections': ['Databases', 'Connect a database and browse what it holds'],
  '/admin/connections/new': ['Connect a database', 'Point AskDB at a MySQL database'],
  '/admin/configure': ['Configuration', 'Control how questions are answered'],
  '/admin/users': ['Users & roles', 'Who can sign in, and what they may do'],
  '/admin/activity': ['Activity', 'Setting changes and questions asked'],
};
const SETUP_TITLE = ['Set up database', 'Teach the system what your data means'];
const DETAIL_TITLE = ['Database', 'Connection details and what it holds'];

export default function AdminShell({ children }) {
  const { user, logout, theme, toggleTheme } = useApp();
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [title, subtitle] = TITLES[pathname]
    || (/^\/admin\/connections\/[^/]+\/setup$/.test(pathname) ? SETUP_TITLE
      : /^\/admin\/connections\/[^/]+$/.test(pathname) ? DETAIL_TITLE
        : ['Admin', '']);

  return (
    <div className="admin-shell">
      <aside className="admin-side">
        <div className="admin-brand">
          <div className="brand-mark">A</div>
          <div>
            <div className="brand-name">AskDB</div>
            <div className="brand-sub">Admin console</div>
          </div>
        </div>

        <div className="admin-side-label">Manage</div>
        <nav className="admin-side-nav">
          {NAV.map(({ to, end, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `admin-link${isActive ? ' active' : ''}`}
            >
              <Icon />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="admin-side-foot">
          <button className="admin-link" onClick={() => navigate('/app/ask')}>
            <IconSparkle />
            Open ask screen
          </button>
          <button className="admin-link" onClick={toggleTheme}>
            {theme === 'dark' ? <IconSun /> : <IconMoon />}
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </button>

          <div className="admin-user">
            <Avatar user={user} />
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="user-name">{user?.name}</div>
              <div className="user-role">{user?.role}</div>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={logout} title="Sign out" aria-label="Sign out">
              <IconLogout />
            </button>
          </div>
        </div>
      </aside>

      <main className="admin-main">
        <header className="admin-header">
          <div className="admin-header-text">
            <h1>{title}</h1>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <div className="spacer" />
          <div className="admin-header-user">
            <div className="admin-header-id">
              <span className="user-name">{user?.name}</span>
              <span className="user-role">{user?.role}</span>
            </div>
            <Avatar user={user} />
          </div>
        </header>
        <div className="admin-content">{children}</div>
      </main>
    </div>
  );
}
