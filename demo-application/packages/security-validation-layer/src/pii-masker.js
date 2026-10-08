/**
 * PII masking — the last step before results leave the security layer for
 * Member 4's visualization layer:
 *
 *   validate -> execute (read-only) -> classifyColumns -> mask -> Member 4
 *
 * Each classified column is masked cell by cell with a strategy for its type.
 * 'partial' keeps just enough to be recognisable to the person it belongs to
 * (n***********@example.com, **** **** **** 1111); 'redact' replaces the whole
 * value with a type token ([EMAIL]). Two rules keep masking fail-safe:
 *   - a value that does not look like its type (MD5(email) is a hex hash, not
 *     an email) is fully masked instead of partially;
 *   - a MIXED column that includes a type regex cannot find inside text
 *     (PERSON, ADDRESS, ...) has the whole cell masked, because span-level
 *     masking would leave the name visible.
 *
 * Dynamic masking: with a masking policy, the action for each column depends
 * on the viewer's role (clear / partial / redact / fpe), so the same query
 * returns real values to an admin, pseudonyms to an analyst and masks to
 * support staff. 'fpe' uses format-preserving encryption (pii-fpe.js).
 */

'use strict';

const { detectInText, detectValue } = require('./pii-detectors');
const { resolveAction } = require('./masking-policy');

const MASK = '*';

// Types detectInText() can locate inside longer text.
const SPAN_DETECTABLE = new Set(['EMAIL', 'PHONE', 'NIC', 'CREDIT_CARD', 'IBAN', 'IP_ADDRESS']);

/** Replace every character except the kept ones; separators survive so the format stays readable. */
function maskChars(str, keep) {
  return [...str].map((ch, i) => (keep(ch, i) ? ch : MASK)).join('');
}

/** Full mask, length preserved (capped so long values do not produce walls of stars). */
function maskAll(str) {
  return MASK.repeat(Math.min(Math.max(str.length, 3), 12));
}

/** Mask all digits except the first `head` and last `tail` digits; non-digits stay. */
function maskDigits(str, head, tail) {
  const total = (str.match(/\d/g) || []).length;
  let seen = 0;
  return [...str].map((ch) => {
    if (!/\d/.test(ch)) return ch;
    seen++;
    return seen <= head || seen > total - tail ? ch : MASK;
  }).join('');
}

const PARTIAL = {
  EMAIL(v) {
    const at = v.lastIndexOf('@');
    if (at < 1) return null;
    const local = v.slice(0, at);
    return local[0] + MASK.repeat(local.length - 1) + v.slice(at);
  },
  PHONE(v) {
    const digits = (v.match(/\d/g) || []).length;
    if (digits < 7) return null;
    // Keep the country/operator prefix and the last two digits: +9477*****67, 077*****67.
    return maskDigits(v, v.trim().startsWith('+') ? 4 : 3, 2);
  },
  NIC(v) {
    // The leading digits encode birth year and day — those are what must go.
    const s = v.trim();
    if (/^\d{9}[VvXx]$/.test(s)) return MASK.repeat(7) + s.slice(7);
    if (/^\d{12}$/.test(s)) return MASK.repeat(10) + s.slice(10);
    return null;
  },
  CREDIT_CARD(v) {
    const digits = (v.match(/\d/g) || []).length;
    if (digits < 12) return null;
    return maskDigits(v, 0, 4); // PCI DSS: at most the last four digits may be shown
  },
  IBAN(v) {
    const s = v.replace(/\s/g, '');
    if (!/^[A-Z]{2}\d{2}/i.test(s)) return null;
    let alnum = 0;
    const total = (v.match(/[A-Za-z0-9]/g) || []).length;
    return maskChars(v, (ch) => {
      if (!/[A-Za-z0-9]/.test(ch)) return true;
      alnum++;
      return alnum <= 2 || alnum > total - 4;
    });
  },
  IP_ADDRESS(v) {
    const parts = v.trim().split('.');
    if (parts.length !== 4) return null;
    return `${parts[0]}.${parts[1]}.*.*`;
  },
  PERSON(v) {
    // Initials only: Nimal Perera -> N**** P*****
    return v.replace(/\p{L}[\p{L}\p{M}'-]*/gu, (w) => w[0] + MASK.repeat(w.length - 1));
  },
  DATE_OF_BIRTH(v) {
    const m = v.match(/^(\d{4})([-/.])\d{1,2}\2\d{1,2}/);
    return m ? `${m[1]}${m[2]}**${m[2]}**` : null;
  },
  ADDRESS: () => null, // no safe partial form — always fully masked
  SECRET: () => '[REDACTED]',
};

/**
 * Mask every PII span inside a longer string: regex-detected items, plus any
 * name spans the NER stage found for this cell ({ start, end } offsets).
 * `actionFor(type)` picks the action per span, so one cell can mix actions.
 */
function maskSpans(str, nameSpans = [], actionFor = () => 'partial', fpe = null) {
  const spans = [
    ...detectInText(str),
    ...nameSpans.map((s) => ({ type: 'PERSON', start: s.start, end: s.end, value: str.slice(s.start, s.end) })),
  ].sort((a, b) => a.start - b.start);
  if (!spans.length) return { value: str, changed: false };
  let out = '';
  let pos = 0;
  for (const s of spans) {
    if (s.start < pos) continue; // overlaps an item already masked
    out += str.slice(pos, s.start) + maskValue(s.value, s.type, actionFor(s.type), fpe);
    pos = s.end;
  }
  const value = out + str.slice(pos);
  return { value, changed: value !== str };
}

/**
 * Apply one action to one value of a known PII type:
 *   clear    unchanged
 *   partial  type-specific partial mask (falls back to a full mask)
 *   redact   [TYPE] token
 *   fpe      format-preserving encryption (falls back to redact when the type
 *            or value cannot be encrypted, or no key is configured)
 */
function maskValue(value, type, action = 'partial', fpe = null) {
  if (value === null || value === undefined) return value;
  const str = String(value);
  if (!str.trim() || action === 'clear') return value;
  if (type === 'SECRET') return '[REDACTED]';
  // A cell holding several values or surrounding text (GROUP_CONCAT(email),
  // CONCAT('Call ', phone)): handle each detected item in place rather than
  // treating the whole string as one value. Nothing detectable -> full mask.
  if (SPAN_DETECTABLE.has(type) && detectValue(str) !== type) {
    const r = maskSpans(str, [], () => action, fpe);
    return r.changed ? r.value : (action === 'redact' ? `[${type}]` : maskAll(str));
  }
  if (action === 'redact') return `[${type}]`;
  if (action === 'fpe') {
    const encrypted = fpe ? fpe.protect(str, type) : null;
    return encrypted === null ? `[${type}]` : encrypted;
  }
  const strategy = PARTIAL[type];
  const masked = strategy ? strategy(str) : null;
  return masked === null ? maskAll(str) : masked;
}

/**
 * Mask a query result using its column classification.
 *
 *   result          { columns, rows: [[...]] } from the query executor
 *   classification  classifyColumns() (+ applyNer()) output, one entry per column
 *   options
 *     role, policy  dynamic masking: the action per PII type comes from the
 *                   role's entry in the masking policy (masking-policy.js)
 *     mode          without a policy: one action for everything ('partial' | 'redact')
 *     fpe           createPiiFpe() instance, needed for the 'fpe' action
 *
 * Returns a new object (the input is not modified):
 *   { ...result, rows, masking: { role, columns: [{ name, piiType, action, pseudonymised }], maskedCells } }
 * `pseudonymised` marks columns whose values are encrypted look-alikes, so
 * consumers never mistake them for real data.
 */
function mask(result, classification, { mode = 'partial', role = null, policy = null, fpe = null } = {}) {
  if (!result || !Array.isArray(result.rows)) throw new TypeError('mask() needs a query result with rows');
  const actionFor = (type, sources) => (policy ? resolveAction(policy, role, type, sources) : mode);

  const plan = result.columns.map((col, i) => {
    const cls = (classification && classification[i]) || {};
    const type = cls.piiType || null;
    const sources = cls.sources || [];
    let strategy = null;
    let action = null;
    if (type === 'CONTAINS_PII') {
      strategy = 'spans';
      action = 'per-span';
    } else if (type === 'UNVERIFIED') {
      // Could not be checked for names: only a role allowed to see everything gets it unmasked.
      action = actionFor('UNVERIFIED', sources);
      strategy = action === 'clear' ? null : 'full';
    } else if (type === 'MIXED') {
      // Several tagged sources in one column: mask span by span if regex can find every
      // part; otherwise (a name is in there) mask the whole cell unless the role may see all parts.
      const parts = cls.sourceTypes || [];
      const actions = parts.map((t) => actionFor(t, sources));
      if (actions.length && actions.every((a) => a === 'clear')) action = 'clear';
      else if (parts.length && parts.every((t) => SPAN_DETECTABLE.has(t))) { strategy = 'spans'; action = 'per-span'; }
      else { strategy = 'full'; action = 'full'; }
    } else if (type) {
      action = actionFor(type, sources);
      strategy = action === 'clear' ? null : 'value';
    }
    return { name: col.name, piiType: type, action, strategy, sources };
  });

  let maskedCells = 0;
  const rows = result.rows.map((row, ri) => row.map((v, i) => {
    const { piiType, action, strategy, sources } = plan[i];
    if (!strategy || v === null || v === undefined || String(v).trim() === '') return v;
    let out;
    if (strategy === 'spans') {
      const names = (classification[i] && classification[i].personSpans && classification[i].personSpans[ri]) || [];
      out = maskSpans(String(v), names, (t) => actionFor(t, sources), fpe).value;
    } else if (strategy === 'full') {
      out = maskAll(String(v));
    } else {
      out = maskValue(v, piiType, action, fpe);
    }
    if (out !== v) maskedCells++;
    return out;
  }));

  return {
    ...result,
    rows,
    masking: {
      role: policy ? role : null,
      mode: policy ? null : mode,
      columns: plan.filter((p) => p.action).map(({ name, piiType, action }) => ({
        name, piiType, action, pseudonymised: action === 'fpe',
      })),
      maskedCells,
    },
  };
}

module.exports = { mask, maskValue, maskSpans };
