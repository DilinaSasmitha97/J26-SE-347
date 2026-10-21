import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Icon } from '../App.jsx';

const KIND_LABELS = {
  statement: 'Statement', clause: 'Clause', table: 'Table', column: 'Column', operator: 'Operator',
  literal: 'Literal', function: 'Function', subquery: 'Subquery', alias: 'Alias', list: 'List', variable: 'Variable'
};
const LEGEND = ['statement', 'clause', 'table', 'column', 'operator', 'function', 'literal', 'subquery'];

// Diagram geometry (px). Labels use the 12px monospace font, so width is predictable.
const CHAR_W = 7.3;
const NODE_H = 30;
const ROW = 40;
const GAP = 44;
const PAD = 16;

const SQL_KEYWORDS = new Set(('SELECT FROM WHERE AND OR NOT IN IS NULL AS ON JOIN INNER LEFT RIGHT FULL OUTER CROSS GROUP BY ORDER '
  + 'HAVING LIMIT OFFSET DISTINCT UNION ALL CASE WHEN THEN ELSE END LIKE BETWEEN EXISTS ASC DESC WITH FOR UPDATE INSERT INTO '
  + 'VALUES DELETE SET DROP TABLE CAST COUNT SUM AVG MIN MAX').split(' '));

function highlightSql(sql) {
  const parts = String(sql).split(/('(?:''|[^'])*'|"(?:""|[^"])*"|\b\d+(?:\.\d+)?\b|\b[A-Za-z_]+\b)/);
  return parts.map((part, i) => {
    if (i % 2 === 0) return part;
    if (/^['"]/.test(part)) return <span key={i} className="ast-tok-str">{part}</span>;
    if (/^\d/.test(part)) return <span key={i} className="ast-tok-num">{part}</span>;
    if (SQL_KEYWORDS.has(part.toUpperCase())) return <span key={i} className="ast-tok-kw">{part}</span>;
    return part;
  });
}

function countNodes(node) {
  if (!node) return 0;
  return 1 + node.children.reduce((sum, child) => sum + countNodes(child), 0);
}

function collectFlags(node, path = 'r', out = []) {
  if (!node) return out;
  if (node.flagged) out.push({ path, label: node.label, reason: node.flagged });
  node.children.forEach((child, i) => collectFlags(child, `${path}.${i}`, out));
  return out;
}

/** Left-to-right tidy layout: columns by depth, leaves stacked, parents centred on their children. */
function layoutTree(root, collapsed) {
  const nodes = [];
  const edges = [];
  const colWidth = [];
  let slot = 0;

  const visit = (node, depth, path) => {
    const hidden = collapsed.has(path);
    const kids = hidden ? [] : node.children;
    const badge = hidden && node.children.length ? 30 : 0;
    const width = Math.max(56, Math.ceil(node.label.length * CHAR_W) + 34 + badge);
    colWidth[depth] = Math.max(colWidth[depth] || 0, width);
    const item = { node, path, depth, width, collapsed: hidden, hiddenCount: hidden ? countNodes(node) - 1 : 0 };
    nodes.push(item);
    if (!kids.length) {
      item.y = slot * ROW;
      slot += 1;
    } else {
      const children = kids.map((child, i) => visit(child, depth + 1, `${path}.${i}`));
      children.forEach((child) => edges.push({ from: item, to: child }));
      item.y = (children[0].y + children[children.length - 1].y) / 2;
    }
    return item;
  };
  visit(root, 0, 'r');

  const colX = [];
  colWidth.reduce((x, w, d) => { colX[d] = x; return x + w + GAP; }, PAD);
  nodes.forEach((item) => { item.x = colX[item.depth]; item.y += PAD; });
  const width = colX[colX.length - 1] + colWidth[colWidth.length - 1] + PAD;
  const height = Math.max(slot, 1) * ROW - (ROW - NODE_H) + PAD * 2;
  return { nodes, edges, width, height };
}

function TreeDiagram({ tree }) {
  const [collapsed, setCollapsed] = useState(() => new Set());
  const [hover, setHover] = useState(null);
  const layout = useMemo(() => layoutTree(tree, collapsed), [tree, collapsed]);
  const toggle = (path) => setCollapsed((prev) => {
    const next = new Set(prev);
    if (next.has(path)) next.delete(path); else next.add(path);
    return next;
  });

  return (
    <div className="ast-canvas">
      <svg width={layout.width} height={layout.height} role="tree" aria-label="Syntax tree diagram">
        {layout.edges.map(({ from, to }) => {
          const x1 = from.x + from.width;
          const y1 = from.y + NODE_H / 2;
          const x2 = to.x;
          const y2 = to.y + NODE_H / 2;
          const mid = (x1 + x2) / 2;
          return <path key={to.path} className={`ast-edge ${hover && to.path.startsWith(hover) ? 'is-lit' : ''}`}
            d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`} />;
        })}
        {layout.nodes.map((item) => {
          const { node, path } = item;
          const expandable = node.children.length > 0;
          const kind = KIND_LABELS[node.kind] || node.kind;
          const props = expandable ? {
            role: 'button', tabIndex: 0, 'aria-expanded': !item.collapsed,
            'aria-label': `${item.collapsed ? 'Expand' : 'Collapse'} ${node.label}`,
            onClick: () => toggle(path),
            onKeyDown: (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle(path); } }
          } : { role: 'treeitem', 'aria-label': `${kind} ${node.label}` };
          return (
            <g key={path} transform={`translate(${item.x},${item.y})`}
              className={`ast-gnode ast-kind-${node.kind} ${node.flagged ? 'is-flagged' : ''} ${expandable ? 'is-expandable' : ''}`}
              onMouseEnter={() => setHover(path)} onMouseLeave={() => setHover(null)} {...props}>
              <title>{node.flagged ? `${kind} · ${node.flagged}` : kind}</title>
              <rect className="ast-gnode-box" width={item.width} height={NODE_H} rx="7" />
              <rect className="ast-gnode-accent" width="3" height={NODE_H - 12} x="0" y="6" rx="1.5" />
              <circle className="ast-gnode-dot" cx="15" cy={NODE_H / 2} r="3.5" />
              <text className="ast-gnode-label" x="26" y={NODE_H / 2} dominantBaseline="central">{node.label}</text>
              {item.collapsed && (
                <g transform={`translate(${item.width - 30},7)`}>
                  <rect className="ast-gnode-badge" width="24" height="16" rx="8" />
                  <text className="ast-gnode-badge-text" x="12" y="8" dominantBaseline="central" textAnchor="middle">+{item.hiddenCount}</text>
                </g>
              )}
              {node.flagged && <circle className="ast-gnode-alert" cx={item.width} cy="0" r="5" />}
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function RuleRow({ stage, index }) {
  const failed = stage.status === 'fail';
  const status = failed ? 'Failed' : stage.status === 'pass' ? 'Passed' : 'Skipped';
  return (
    <li className={`ast-rule is-${stage.status}`}>
      <details open={failed}>
        <summary>
          <span className="ast-rule-mark" aria-hidden="true">
            {stage.status === 'skipped' ? '–' : <Icon name={failed ? 'close' : 'check'} size={11} />}
          </span>
          <span className="ast-rule-index">{String(index + 1).padStart(2, '0')}</span>
          <span className="ast-rule-label">{stage.label}</span>
          <span className="ast-rule-observed" title={stage.observed}>{stage.observed}</span>
          <span className="visually-hidden">{status}</span>
        </summary>
        <div className="ast-rule-detail">
          <p>{stage.description}</p>
          {stage.violations.map((v, i) => <p key={i} className="ast-violation">{v}</p>)}
        </div>
      </details>
    </li>
  );
}

/** Popup explaining the SQL safety (AST) check: the parsed tree and every validator rule. */
export default function AstTraceDialog({ trace, onClose }) {
  const closeButton = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;
  const [tab, setTab] = useState('tree');

  useEffect(() => {
    closeButton.current?.focus();
    const onKey = (event) => { if (event.key === 'Escape') close.current(); };
    document.addEventListener('keydown', onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = overflow; };
  }, []);

  const failed = trace.stages.filter((s) => s.status === 'fail').length;
  const passed = trace.stages.filter((s) => s.status === 'pass').length;
  const total = trace.stages.length;
  const nodes = countNodes(trace.tree);
  const flags = collectFlags(trace.tree);
  const parsed = Boolean(trace.tree);

  const steps = [
    { label: 'Raw SQL', meta: `${trace.sql.length} chars`, state: 'done' },
    { label: 'Parse', meta: trace.parser, state: parsed ? 'done' : 'fail' },
    { label: 'Syntax tree', meta: parsed ? `${nodes}${trace.truncated ? '+' : ''} nodes · ${trace.statementType}` : 'not built', state: parsed ? 'done' : 'skip' },
    { label: 'Rule checks', meta: `${passed} / ${total} passed`, state: failed ? 'fail' : parsed ? 'done' : 'skip' },
    { label: 'Verdict', meta: trace.safe ? 'Approved' : 'Rejected', state: trace.safe ? 'done' : 'fail' }
  ];

  return createPortal(
    <div className="pl-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="pl-modal ast-modal" role="dialog" aria-modal="true" aria-labelledby="ast-dialog-title">
        <header className="ast-head">
          <span className="ast-head-icon"><Icon name="code" size={18} /></span>
          <div>
            <h2 id="ast-dialog-title">SQL safety (AST) check</h2>
            <p>How the security validation layer parsed this query and checked every node before execution.</p>
          </div>
          <span className={`ast-verdict ${trace.safe ? 'is-safe' : 'is-blocked'}`}>
            <Icon name={trace.safe ? 'shield' : 'close'} size={14} />{trace.safe ? 'Safe' : 'Blocked'}
          </span>
          <button type="button" ref={closeButton} className="ast-close" onClick={onClose} aria-label="Close AST view"><Icon name="close" size={16} /></button>
        </header>

        <ol className="ast-pipeline" aria-label="Validation flow">
          {steps.map((step, i) => (
            <li key={step.label} className={`is-${step.state}`}>
              <span className="ast-pipeline-num">{step.state === 'fail' ? '!' : i + 1}</span>
              <span><b>{step.label}</b><small>{step.meta}</small></span>
            </li>
          ))}
        </ol>

        <pre className="ast-sql" aria-label="Validated SQL">{highlightSql(trace.sql)}</pre>

        <div className="ast-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === 'tree'} className={tab === 'tree' ? 'is-active' : ''} onClick={() => setTab('tree')}>
            Syntax tree{flags.length > 0 && <span className="ast-tab-badge">{flags.length}</span>}
          </button>
          <button type="button" role="tab" aria-selected={tab === 'rules'} className={tab === 'rules' ? 'is-active' : ''} onClick={() => setTab('rules')}>
            Rule checks{failed > 0 && <span className="ast-tab-badge">{failed}</span>}
          </button>
        </div>

        <div className="ast-body">
          <section className={`ast-panel ${tab === 'tree' ? 'is-active' : ''}`} aria-label="Abstract syntax tree">
            <div className="ast-panel-head">
              <h3>Abstract syntax tree</h3>
              <div className="ast-legend">{LEGEND.map((kind) => <span key={kind} className={`ast-kind-${kind}`}><i />{KIND_LABELS[kind]}</span>)}</div>
            </div>
            {parsed ? <TreeDiagram tree={trace.tree} /> : (
              <div className="ast-empty">
                <strong>No syntax tree</strong>
                <p>{trace.parseError || 'The SQL could not be parsed.'}</p>
                <span>The query was rejected before any rule could walk the tree.</span>
              </div>
            )}
            {flags.length > 0 && (
              <ul className="ast-findings" aria-label="Flagged nodes">
                {flags.map((flag) => <li key={flag.path}><code>{flag.label}</code><span>{flag.reason}</span></li>)}
              </ul>
            )}
            <p className="ast-hint">{parsed ? 'Click a node to collapse or expand its branch. Hover to trace its subtree.' : ''}{trace.truncated ? ' Large tree: only the first nodes are shown.' : ''}</p>
          </section>

          <section className={`ast-panel ${tab === 'rules' ? 'is-active' : ''}`} aria-label="Rule checks">
            <div className="ast-panel-head">
              <h3>Rule checks</h3>
              <span className={`ast-score ${failed ? 'is-fail' : ''}`}>{passed} / {total} passed</span>
            </div>
            <div className="ast-progress" aria-hidden="true">
              <i className="pass" style={{ width: `${(passed / total) * 100}%` }} />
              <i className="fail" style={{ width: `${(failed / total) * 100}%` }} />
            </div>
            <ol className="ast-rules">{trace.stages.map((stage, i) => <RuleRow key={stage.id} stage={stage} index={i} />)}</ol>
          </section>
        </div>
      </div>
    </div>,
    document.body
  );
}
