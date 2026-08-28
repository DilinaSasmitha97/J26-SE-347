import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider, useApp } from './context/AppContext.jsx';
import Shell from './components/Shell.jsx';
import AdminShell from './components/AdminShell.jsx';
import Login from './pages/Login.jsx';
import Ask from './pages/Ask.jsx';
import Dashboard from './pages/admin/Dashboard.jsx';
import Connections from './pages/admin/Connections.jsx';
import NewConnection from './pages/admin/NewConnection.jsx';
import SetupConnection from './pages/admin/SetupConnection.jsx';
import ConnectionDetail from './pages/admin/ConnectionDetail.jsx';
import Configure from './pages/admin/Configure.jsx';
import Users from './pages/admin/Users.jsx';
import Activity from './pages/admin/Activity.jsx';

function Toasts() {
  const { toasts } = useApp();
  return (
    <div className="toast-host">
      {toasts.map((t) => (
        <div className={`toast ${t.tone === 'ok' ? 'ok' : t.tone === 'err' ? 'err' : ''}`} key={t.id}>
          {t.message}
        </div>
      ))}
    </div>
  );
}

function Loading() {
  return <div style={{ display: 'grid', placeItems: 'center', height: '100%' }} className="muted">Loading…</div>;
}

// Everyone signed in can reach the ask screen.
function Protected({ children }) {
  const { user, booting } = useApp();
  if (booting) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  return <Shell>{children}</Shell>;
}

// The admin console is owners only; anyone else is sent to the ask screen.
function OwnerOnly({ children }) {
  const { user, booting, isOwner } = useApp();
  if (booting) return <Loading />;
  if (!user) return <Navigate to="/login" replace />;
  if (!isOwner) return <Navigate to="/app/ask" replace />;
  return <AdminShell>{children}</AdminShell>;
}

// Owners start in the console, everyone else starts asking questions.
function homeFor(user) {
  return user?.role === 'owner' ? '/admin' : '/app/ask';
}

function Router() {
  const { user, booting } = useApp();
  return (
    <Routes>
      <Route
        path="/login"
        element={booting ? null : user ? <Navigate to={homeFor(user)} replace /> : <Login />}
      />

      <Route path="/app/ask" element={<Protected><Ask /></Protected>} />

      <Route path="/admin" element={<OwnerOnly><Dashboard /></OwnerOnly>} />
      <Route path="/admin/connections" element={<OwnerOnly><Connections /></OwnerOnly>} />
      <Route path="/admin/connections/new" element={<OwnerOnly><NewConnection /></OwnerOnly>} />
      <Route path="/admin/connections/:id/setup" element={<OwnerOnly><SetupConnection /></OwnerOnly>} />
      <Route path="/admin/connections/:id" element={<OwnerOnly><ConnectionDetail /></OwnerOnly>} />
      <Route path="/admin/configure" element={<OwnerOnly><Configure /></OwnerOnly>} />
      <Route path="/admin/users" element={<OwnerOnly><Users /></OwnerOnly>} />
      <Route path="/admin/activity" element={<OwnerOnly><Activity /></OwnerOnly>} />

      <Route path="*" element={<Navigate to={user ? homeFor(user) : '/login'} replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Router />
        <Toasts />
      </BrowserRouter>
    </AppProvider>
  );
}
