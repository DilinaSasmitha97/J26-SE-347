import React from 'react';

/**
 * UserDetails Component (Section 1)
 *
 * Displays the currently logged-in persona and multi-tenant security context.
 * Provides a "Switch User" button to return to the selection screen.
 */
export default function UserDetails({ user, onSwitchUser }) {
  if (!user) return null;

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          <span>👤</span> Active Session
        </h3>
        <span className="section-tag">Section 1</span>
      </div>

      <div style={{ marginBottom: '16px' }}>
        <div style={{ fontSize: '1.05rem', fontWeight: '700', color: '#f8fafc' }}>
          Logged in as: <span style={{ color: 'var(--accent-blue)' }}>{user.name}</span>
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
          User ID: {user.userId}
        </div>
      </div>

      <div className="details-box" style={{ marginBottom: '16px' }}>
        <div className="details-grid">
          <div className="detail-item">
            <span className="detail-label">Role</span>
            <span className="detail-value">{user.role}</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Tenant ID</span>
            <span className="detail-value">{user.tenantId}</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Department ID</span>
            <span className="detail-value">{user.departmentId}</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Region</span>
            <span className="detail-value">{user.region}</span>
          </div>
        </div>
      </div>

      <button
        type="button"
        className="btn btn-secondary"
        style={{ width: '100%' }}
        onClick={onSwitchUser}
      >
        ⇄ Switch User
      </button>
    </div>
  );
}
