import { createContext, useContext, useEffect, useMemo, useState, useCallback } from 'react';
import { api, setToken, clearToken, getToken } from '../lib/api.js';

const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

const THEME_KEY = 'askdb.theme';
const CONN_KEY = 'askdb.connection';

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(true);
  const [connections, setConnections] = useState([]);
  const [connectionId, setConnectionId] = useState(localStorage.getItem(CONN_KEY) || 'retail');
  const [theme, setTheme] = useState(localStorage.getItem(THEME_KEY) || 'light');
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  useEffect(() => {
    localStorage.setItem(CONN_KEY, connectionId);
  }, [connectionId]);

  const toast = useCallback((message, tone = 'info') => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3200);
  }, []);

  const refreshConnections = useCallback(async () => {
    try {
      const { connections: list } = await api.connections();
      setConnections(list);
      // Keep the selected connection valid if it disappeared.
      setConnectionId((current) => (list.some((c) => c.id === current) ? current : list[0]?.id));
      return list;
    } catch {
      return [];
    }
  }, []);

  // Restore the session on first load.
  useEffect(() => {
    (async () => {
      if (!getToken()) return setBooting(false);
      try {
        const { user: me } = await api.me();
        setUser(me);
        await refreshConnections();
      } catch {
        clearToken();
      } finally {
        setBooting(false);
      }
    })();
  }, [refreshConnections]);

  const login = useCallback(async (email, password) => {
    const { token, user: me } = await api.login(email, password);
    setToken(token);
    setUser(me);
    await refreshConnections();
    return me;
  }, [refreshConnections]);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    setConnections([]);
  }, []);

  const connection = useMemo(
    () => connections.find((c) => c.id === connectionId) || null,
    [connections, connectionId]
  );

  const value = {
    user, booting, login, logout,
    connections, connection, connectionId, setConnectionId, refreshConnections,
    theme, setTheme, toggleTheme: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
    toast, toasts,
    isOwner: user?.role === 'owner',
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
