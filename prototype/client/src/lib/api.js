const TOKEN_KEY = 'askdb.token';

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request(path, { method = 'GET', body } = {}) {
  const res = await fetch(`/api${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });

  let data = null;
  try {
    data = await res.json();
  } catch {
    data = null;
  }

  if (!res.ok) {
    const error = new Error((data && data.error) || `Request failed (${res.status})`);
    error.status = res.status;
    throw error;
  }
  return data;
}

export const api = {
  login: (email, password) => request('/auth/login', { method: 'POST', body: { email, password } }),
  me: () => request('/auth/me'),

  connections: () => request('/connections'),
  connection: (id) => request(`/connections/${id}`),
  createConnection: (body) => request('/connections', { method: 'POST', body }),
  testConnection: (id) => request(`/connections/${id}/test`, { method: 'POST' }),
  deleteConnection: (id) => request(`/connections/${id}`, { method: 'DELETE' }),

  schema: (id) => request(`/connections/${id}/schema`),
  sample: (id, table) => request(`/connections/${id}/schema/${table}/sample`),
  suggestions: (id) => request(`/connections/${id}/suggestions`),
  review: (id) => request(`/connections/${id}/review`),
  saveReview: (id, answers) => request(`/connections/${id}/review`, { method: 'POST', body: { answers } }),

  ask: (question, connectionId) => request('/ask', { method: 'POST', body: { question, connectionId } }),

  history: (connectionId) => request(`/history${connectionId ? `?connectionId=${connectionId}` : ''}`),
  clearHistory: () => request('/history', { method: 'DELETE' }),

  settings: (id) => request(`/admin/settings/${id}`),
  saveSettings: (id, body) => request(`/admin/settings/${id}`, { method: 'PUT', body }),
  users: () => request('/admin/users'),
  inviteUser: (body) => request('/admin/users', { method: 'POST', body }),
  updateUser: (id, body) => request(`/admin/users/${id}`, { method: 'PUT', body }),
  audit: () => request('/admin/audit'),

  overview: () => request('/overview'),
};
