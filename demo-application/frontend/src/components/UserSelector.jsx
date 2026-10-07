import React from 'react';

/**
 * UserSelector Component
 *
 * Implements the initial fake login screen allowing the user to select
 * a predefined demo persona (Manager A, Employee A, Manager B, Employee B)
 * and view their multi-tenant attributes before proceeding to the dashboard.
 */
export default function UserSelector({ users, selectedUser, onSelectUser, onLogin }) {
  if (!selectedUser) return null;

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <span className="section-tag" style={{ display: 'inline-block', marginBottom: '12px' }}>
          Prototype Phase 1
        </span>
        <h2>Secure Multi-Tenant SQL Policy Demo</h2>
        <p>Select a simulated user profile to explore policy-grounded query isolation.</p>

        <div className="form-group">
          <label className="form-label" htmlFor="user-select">
            Select User
          </label>
          <select
            id="user-select"
            className="form-select"
            value={selectedUser.userId}
            onChange={(e) => {
              const user = users.find((u) => u.userId === e.target.value);
              if (user) onSelectUser(user);
            }}
          >
            {users.map((u) => (
              <option key={u.userId} value={u.userId}>
                {u.name} ({u.role}) - Tenant {u.tenantId}
              </option>
            ))}
          </select>
        </div>

        <div className="details-box">
          <span className="form-label" style={{ marginBottom: '10px' }}>
            User Context Details
          </span>
          <div className="details-grid">
            <div className="detail-item">
              <span className="detail-label">Role</span>
              <span className="detail-value">{selectedUser.role}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Tenant ID</span>
              <span className="detail-value">{selectedUser.tenantId}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Department ID</span>
              <span className="detail-value">{selectedUser.departmentId}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Region</span>
              <span className="detail-value">{selectedUser.region}</span>
            </div>
          </div>
        </div>

        <button
          type="button"
          className="btn btn-primary btn-large"
          onClick={() => onLogin(selectedUser)}
        >
          Login as {selectedUser.name}
        </button>
      </div>
    </div>
  );
}
