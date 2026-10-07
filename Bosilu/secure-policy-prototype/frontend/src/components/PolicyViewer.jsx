import React, { useState } from 'react';

/**
 * PolicyViewer Component (Section 2)
 *
 * Visualizes the effective policy grounded for the active user:
 * - Allowed Tables (✓)
 * - Blocked Columns (✕)
 * - Required Row Filters (=)
 * - Expandable Raw Policy JSON
 */
export default function PolicyViewer({ policy }) {
  const [showRaw, setShowRaw] = useState(false);

  if (!policy) {
    return (
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">Effective Policy</h3>
        </div>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading policy...</p>
      </div>
    );
  }

  const allowedTables = policy.allowedTables || [];
  const deniedColumns = policy.deniedColumns || [];
  const rowRules = policy.rowRules || [];

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          <span>🛡️</span> Effective Policy
        </h3>
        <span className="section-tag">Section 2</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.825rem', marginBottom: '14px', color: 'var(--text-muted)' }}>
        <span>ID: <strong style={{ color: 'var(--text-main)' }}>{policy.policyId}</strong></span>
        <span>Version: <strong style={{ color: 'var(--text-main)' }}>{policy.version}</strong></span>
      </div>

      {/* Allowed Tables */}
      <div className="policy-section-title">Allowed Tables</div>
      <ul className="policy-list">
        {allowedTables.length > 0 ? (
          allowedTables.map((table) => (
            <li key={table} className="policy-list-item allow">
              <span>✓</span> {table}
            </li>
          ))
        ) : (
          <li className="policy-list-item" style={{ color: 'var(--text-muted)' }}>None defined</li>
        )}
      </ul>

      {/* Blocked Columns */}
      <div className="policy-section-title">Blocked Columns</div>
      <ul className="policy-list">
        {deniedColumns.length > 0 ? (
          deniedColumns.map((col) => (
            <li key={col} className="policy-list-item deny">
              <span>✕</span> {col}
            </li>
          ))
        ) : (
          <li className="policy-list-item" style={{ color: 'var(--text-muted)' }}>None defined</li>
        )}
      </ul>

      {/* Required Filters */}
      <div className="policy-section-title">Required Filters</div>
      <ul className="policy-list">
        {rowRules.length > 0 ? (
          rowRules.map((rule, idx) => (
            <li key={idx} className="policy-list-item filter">
              <span>⚙</span> {rule.table}.{rule.field} {rule.operator} {rule.value}
            </li>
          ))
        ) : (
          <li className="policy-list-item" style={{ color: 'var(--text-muted)' }}>No row filters defined</li>
        )}
      </ul>

      {/* Optional Raw JSON view */}
      <div style={{ marginTop: '16px' }}>
        <button
          type="button"
          className="expand-toggle"
          onClick={() => setShowRaw(!showRaw)}
        >
          {showRaw ? '▲ Hide Raw Policy JSON' : '▼ View Raw Policy JSON'}
        </button>

        {showRaw && (
          <pre className="raw-json">
            {JSON.stringify(policy, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
