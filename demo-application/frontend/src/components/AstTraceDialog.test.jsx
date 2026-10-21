import React from 'react';
import { it, expect, vi } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';
import AstTraceDialog from './AstTraceDialog.jsx';

const leaf = (kind, label, extra = {}) => ({ kind, label, children: [], ...extra });

const blocked = {
  sql: 'SELECT * FROM users WHERE id = 5 OR 1=1',
  safe: false,
  statementType: 'SELECT',
  parser: 'node-sql-parser (MySQL)',
  parseError: null,
  truncated: false,
  tree: { kind: 'statement', label: 'SELECT', children: [
    { kind: 'clause', label: 'FROM', children: [leaf('table', 'users')] },
    { kind: 'clause', label: 'WHERE', flagged: 'Always-true condition', children: [
      { kind: 'operator', label: 'OR', children: [leaf('column', 'id'), leaf('literal', '1')] }] }] },
  stages: [
    { id: 'parse', label: 'Parse into an AST', description: 'Parser.', status: 'pass', observed: 'Parsed successfully', violations: [] },
    { id: 'tautology', label: 'Always-true predicates', description: 'Folding.', status: 'fail', observed: '1 predicate(s) evaluated',
      violations: ['Always-true condition makes a WHERE/HAVING/ON filter match every row'] }
  ]
};

it('shows the syntax tree with flagged nodes and every rule result', () => {
  render(<AstTraceDialog trace={blocked} onClose={() => {}} />);
  const dialog = screen.getByRole('dialog', { name: 'SQL safety (AST) check' });
  expect(within(dialog).getByText('Blocked')).toBeTruthy();
  const tree = within(dialog).getByLabelText('Abstract syntax tree');
  expect(within(tree).getByText('users')).toBeTruthy();
  expect(within(tree).getByText('Always-true condition')).toBeTruthy();
  const rules = within(dialog).getByLabelText('Rule checks');
  expect(within(rules).getByText(/match every row/)).toBeTruthy();
  expect(within(rules).getByText('1 / 2 passed')).toBeTruthy();
  expect(within(rules).getByText('Always-true predicates').closest('details').open).toBe(true);
  expect(within(rules).getByText('Parse into an AST').closest('details').open).toBe(false);
});

it('collapses a branch and closes on Escape', () => {
  const onClose = vi.fn();
  render(<AstTraceDialog trace={blocked} onClose={onClose} />);
  fireEvent.click(screen.getByRole('button', { name: 'Collapse WHERE' }));
  expect(screen.queryByText('id')).toBeNull();
  fireEvent.keyDown(document, { key: 'Escape' });
  expect(onClose).toHaveBeenCalled();
});

it('explains a query that never produced a tree', () => {
  render(<AstTraceDialog trace={{ ...blocked, tree: null, parseError: 'Failed to parse SQL: unexpected token' }} onClose={() => {}} />);
  expect(screen.getByText('No syntax tree')).toBeTruthy();
  expect(screen.getByText(/unexpected token/)).toBeTruthy();
});
