import React, { useEffect } from 'react';

/**
 * SqlInput Component (Section 3)
 *
 * Textarea for entering SQL query representing output from future NL-to-SQL AI component.
 * Features quick-test example buttons tailored to the currently selected user's tenant & department.
 */
export default function SqlInput({ user, sql, setSql, onCheckSql, loading }) {
  const tenantId = user?.tenantId ?? 101;
  const departmentId = user?.departmentId ?? 1;
  const wrongTenantId = tenantId === 101 ? 102 : 101;

  // Templates customized dynamically based on logged in user
  const examples = {
    safe: `SELECT name\nFROM employees\nWHERE tenant_id = ${tenantId}\nAND department_id = ${departmentId};`,
    missingTenant: `SELECT name\nFROM employees\nWHERE department_id = ${departmentId};`,
    wrongTenant: `SELECT name\nFROM employees\nWHERE tenant_id = ${wrongTenantId}\nAND department_id = ${departmentId};`,
    missingDepartment: `SELECT name\nFROM employees\nWHERE tenant_id = ${tenantId};`,
    blockedColumn: `SELECT name, salary\nFROM employees\nWHERE tenant_id = ${tenantId}\nAND department_id = ${departmentId};`,
    blockedTable: `SELECT *\nFROM payroll_secrets\nWHERE tenant_id = ${tenantId};`
  };

  // Automatically load Safe SQL when user switches
  useEffect(() => {
    setSql(examples.safe);
  }, [user?.userId]);

  return (
    <div className="card">
      <div className="card-header">
        <h3 className="card-title">
          <span>⚡</span> Fake Generated SQL
        </h3>
        <span className="section-tag">Section 3</span>
      </div>

      <div className="form-group" style={{ marginBottom: '10px' }}>
        <label className="form-label" htmlFor="sql-input">
          Generated SQL
        </label>
        <textarea
          id="sql-input"
          className="sql-textarea"
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          placeholder="Enter SQL query here..."
          rows={5}
        />
        <p className="sql-hint">
          ℹ️ For this demo, manually enter SQL here. This represents SQL that will later come from the NL-to-SQL AI component.
        </p>
      </div>

      {/* Quick Test Example Buttons */}
      <div className="examples-bar">
        <span className="examples-label">Quick Test Scenarios:</span>
        <button
          type="button"
          className="btn-chip"
          onClick={() => setSql(examples.safe)}
        >
          ✓ Safe SQL
        </button>
        <button
          type="button"
          className="btn-chip"
          onClick={() => setSql(examples.missingTenant)}
        >
          ✕ Missing Tenant
        </button>
        <button
          type="button"
          className="btn-chip"
          onClick={() => setSql(examples.wrongTenant)}
        >
          ✕ Wrong Tenant
        </button>
        <button
          type="button"
          className="btn-chip"
          onClick={() => setSql(examples.missingDepartment)}
        >
          ✕ Missing Department
        </button>
        <button
          type="button"
          className="btn-chip"
          onClick={() => setSql(examples.blockedColumn)}
        >
          ✕ Blocked Column
        </button>
        <button
          type="button"
          className="btn-chip"
          onClick={() => setSql(examples.blockedTable)}
        >
          ✕ Blocked Table
        </button>
      </div>

      <button
        type="button"
        className="btn btn-primary btn-large"
        style={{ marginTop: '8px' }}
        onClick={onCheckSql}
        disabled={loading || !sql.trim()}
      >
        {loading ? 'Evaluating Policy Rules...' : '🛡️ Check SQL'}
      </button>
    </div>
  );
}
