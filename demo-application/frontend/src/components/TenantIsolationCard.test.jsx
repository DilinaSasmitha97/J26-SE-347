import React from 'react';
import { it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import TenantIsolationCard from './TenantIsolationCard.jsx';

it('shows waiting and checking before a result', () => {
  const { rerender } = render(<TenantIsolationCard />);
  expect(screen.getByText('Waiting')).toBeTruthy();
  rerender(<TenantIsolationCard loading />);
  expect(screen.getByRole('status').textContent).toMatch(/each table alias/);
});

it('shows changed aliases and the final verified SQL separately from the draft', () => {
  render(<TenantIsolationCard result={{ status: 'REPAIRED', applied: true, finalVerification: 'PASS',
    message: 'Repaired.', originalSql: 'SELECT name FROM tenants WHERE id=102',
    finalSql: 'SELECT name FROM tenants WHERE id = 101',
    findings: [{ alias: 'tenants', table: 'tenants', column: 'id', status: 'WRONG_TENANT' }],
    changes: [{ alias: 'tenants', action: 'REPLACE_WRONG_TENANT', previousValue: '102' }] }} />);
  expect(screen.getByText('Repaired and verified')).toBeTruthy();
  expect(screen.getByLabelText('Final verified SQL').textContent).toMatch(/id = 101/);
  expect(within(screen.getByLabelText('Tenant isolation changes')).getByRole('listitem').textContent).toMatch(/was 102/);
});

it('does not expose a final SQL candidate on failure', () => {
  render(<TenantIsolationCard result={{ status: 'CANNOT_REPAIR', finalVerification: 'FAIL',
    message: 'Unsupported nested query.', reasonCode: 'UNSUPPORTED_QUERY_SHAPE', finalSql: 'unverified candidate' }} />);
  expect(screen.getByRole('alert').textContent).toMatch(/Unsupported nested query/);
  expect(screen.getByText(/Execution is blocked/)).toBeTruthy();
  expect(screen.queryByLabelText('Final verified SQL')).toBeNull();
});
