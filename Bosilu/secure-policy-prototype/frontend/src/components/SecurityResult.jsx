import React from 'react';

/**
 * SecurityResult Component
 *
 * Renders the evaluation results of the 3 security checkers:
 * 1. Tenant Check (PASS / FAIL)
 * 2. Row Filter Check (PASS / FAIL)
 * 3. Table / Column Check (PASS / FAIL)
 * Followed by the Final Decision: ALLOW (green) or DENY (red).
 */
export default function SecurityResult({ result }) {
  if (!result) return null;

  const isAllowed = result.decision === 'ALLOW';
  const tenantCheck = result.checks?.tenant || {};
  const rowFilterCheck = result.checks?.rowFilters || {};
  const tableColumnCheck = result.checks?.tableColumns || {};

  return (
    <div className="card" style={{ marginTop: '24px' }}>
      <div className="card-header">
        <h3 className="card-title">
          <span>📊</span> Security Check Result
        </h3>
        <span
          className={`decision-badge ${isAllowed ? 'allow' : 'deny'}`}
        >
          {result.decision}
        </span>
      </div>

      <div className="result-box">
        {/* Banner with Final Decision */}
        <div className={`result-header ${isAllowed ? 'allow' : 'deny'}`}>
          <span>FINAL DECISION</span>
          <span style={{ fontSize: '1.25rem', letterSpacing: '0.05em' }}>
            {isAllowed ? '✓ ALLOW' : '✕ DENY'}
          </span>
        </div>

        {/* 3 Individual Check Results */}
        <div className="checks-grid">
          {/* 1. Tenant Check */}
          <div className="check-row">
            <div className="check-info">
              <span className="check-title">1. Tenant Check</span>
              <span className="check-message">
                {tenantCheck.message || (tenantCheck.status === 'PASS' ? 'Tenant isolation verified' : 'Tenant violation')}
              </span>
            </div>
            <span className={`status-badge ${tenantCheck.status === 'PASS' ? 'pass' : 'fail'}`}>
              {tenantCheck.status || 'FAIL'}
            </span>
          </div>

          {/* 2. Row Filter Check */}
          <div className="check-row">
            <div className="check-info">
              <span className="check-title">2. Row Filter Check</span>
              <span className="check-message">
                {rowFilterCheck.message || (rowFilterCheck.status === 'PASS' ? 'Required row filters present' : 'Missing required filter')}
              </span>
            </div>
            <span className={`status-badge ${rowFilterCheck.status === 'PASS' ? 'pass' : 'fail'}`}>
              {rowFilterCheck.status || 'FAIL'}
            </span>
          </div>

          {/* 3. Table / Column Check */}
          <div className="check-row">
            <div className="check-info">
              <span className="check-title">3. Table / Column Check</span>
              <span className="check-message">
                {tableColumnCheck.message || (tableColumnCheck.status === 'PASS' ? 'Tables and columns permitted' : 'Unauthorized table or column')}
              </span>
            </div>
            <span className={`status-badge ${tableColumnCheck.status === 'PASS' ? 'pass' : 'fail'}`}>
              {tableColumnCheck.status || 'FAIL'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
