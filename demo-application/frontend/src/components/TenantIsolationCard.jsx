import React from 'react';

const LABELS = {
  REPAIRED: 'Repaired and verified', UNCHANGED_VERIFIED: 'Verified',
  CANNOT_REPAIR: 'Cannot safely repair', BLOCKED: 'Blocked', UNAVAILABLE: 'Unavailable'
};
const ACTIONS = {
  REPLACE_WRONG_TENANT: 'Corrected tenant value',
  ADD_MISSING_TENANT_FILTER: 'Added missing tenant restriction'
};

export default function TenantIsolationCard({ result, loading = false }) {
  const passed = result?.finalVerification === 'PASS'
    && ['REPAIRED', 'UNCHANGED_VERIFIED'].includes(result?.status);
  const failed = Boolean(result && !passed);
  return (
    <section aria-label="Tenant isolation repair" aria-busy={loading}
      className={`pl-result-card pl-tenant-card ${failed ? 'is-fail' : passed ? 'is-pass' : ''}`}>
      <div className="pl-result-head">
        <h3>Tenant isolation repair</h3>
        <span className={`pl-pill ${loading ? 'pl-pill-loading' : failed ? 'pl-pill-error' : passed ? 'pl-pill-pass' : ''}`}>
          {loading ? 'Checking' : result ? LABELS[result.status] || 'Not verified' : 'Waiting'}
        </span>
      </div>
      {loading ? <p className="pl-muted" role="status">Checking each table alias and verifying tenant restrictions before execution…</p>
        : !result ? <p className="pl-muted">Validate &amp; execute checks tenant isolation, repairs supported missing or incorrect restrictions, and verifies the final SQL before execution.</p>
          : <>
            <p className={failed ? 'pl-error-text' : 'pl-muted'} role={failed ? 'alert' : undefined}>{result.message}</p>
            {result.reasonCode && <p className="pl-mono pl-reason">{result.reasonCode}</p>}
            <div className="pl-meta-row">
              <span>Final verification: {passed ? 'PASS' : 'FAIL'}</span>
              <span>{result.applied ? 'Query repaired' : 'No repair applied'}</span>
            </div>
            {failed && <p className="pl-muted">Execution is blocked. Review the query and policy, or simplify unsupported query structures.</p>}
            {result.findings?.length > 0 && <div className="pl-table-wrap"><table className="pl-data-table">
              <caption>Tenant coverage before repair</caption>
              <thead><tr><th>Table / alias</th><th>Tenant column</th><th>Finding</th></tr></thead>
              <tbody>{result.findings.map((finding, index) => <tr key={`${finding.alias}-${index}`}>
                <td>{finding.table} / {finding.alias}</td><td>{finding.column}</td><td>{finding.status}</td>
              </tr>)}</tbody>
            </table></div>}
            {result.changes?.length > 0 && <ul aria-label="Tenant isolation changes">{result.changes.map((change, index) => <li key={index}>
              {ACTIONS[change.action] || change.action} for <code>{change.alias}</code>
              {change.previousValue != null && ` (was ${change.previousValue})`}
              {change.placement === 'JOIN_ON' && ' in the join condition'}.
            </li>)}</ul>}
            {result.originalSql && <details><summary>Original SQL</summary><pre>{result.originalSql}</pre></details>}
            {passed && result.finalSql && <div className="pl-tenant-sql">
              <p className="pl-label">Final verified SQL</p><pre aria-label="Final verified SQL">{result.finalSql}</pre>
            </div>}
          </>}
    </section>
  );
}
