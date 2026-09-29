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
 * Role-based policies and format-preserving encryption build on this in the
 * next stage; `mode` is the hook for them.
 */

'use strict';

const { detectInText, detectValue } = require('./pii-detectors');

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
 */
function maskSpans(str, nameSpans = []) {
  const spans = [
    ...detectInText(str),
    ...nameSpans.map((s) => ({ type: 'PERSON', start: s.start, end: s.end, value: str.slice(s.start, s.end) })),
  ].sort((a, b) => a.start - b.start);
  if (!spans.length) return { value: str, changed: false };
  let out = '';
  let pos = 0;
  for (const s of spans) {
    if (s.start < pos) continue; // overlaps an item already masked
    out += str.slice(pos, s.start) + maskValue(s.value, s.type, 'partial');
    pos = s.end;
  }
  return { value: out + str.slice(pos), changed: true };
}

/** Mask one value of a known PII type. Falls back to a full mask if the value does not fit the type. */
function maskValue(value, type, mode = 'partial') {
  if (value === null || value === undefined) return value;
  const str = String(value);
  if (!str.trim()) return value;
  if (mode === 'redact' || type === 'SECRET') return type === 'SECRET' ? '[REDACTED]' : `[${type}]`;
  // A cell holding several values or surrounding text (GROUP_CONCAT(email),
  // CONCAT('Call ', phone)): mask each detected item in place rather than
  // treating the whole string as one value. Nothing detectable -> full mask.
  if (SPAN_DETECTABLE.has(type) && detectValue(str) !== type) {
    const r = maskSpans(str);
    return r.changed ? r.value : maskAll(str);
  }
  const strategy = PARTIAL[type];
  const masked = strategy ? strategy(str) : null;
  return masked === null ? maskAll(str) : masked;
}

/**
 * Mask a query result using its column classification.
 *
 *   result          { columns, rows: [[...]] } from the query executor
 *   classification  classifyColumns() output, one entry per column
 *   mode            'partial' (default) | 'redact'
 *
 * Returns a new object (the input is not modified):
 *   { ...result, rows, masking: { mode, columns: [{ name, piiType, strategy }], maskedCells } }
 */
function mask(result, classification, { mode = 'partial' } = {}) {
  if (!result || !Array.isArray(result.rows)) throw new TypeError('mask() needs a query result with rows');
  const plan = result.columns.map((col, i) => {
    const cls = (classification && classification[i]) || {};
    const type = cls.piiType || null;
    let strategy = null;
    if (type === 'CONTAINS_PII') strategy = 'spans';
    else if (type === 'UNVERIFIED') strategy = 'full'; // could not be checked for names -> fail closed
    else if (type === 'MIXED') {
      // A column built from several tagged sources: if every part can be found by regex,
      // mask the spans; otherwise (a name is in there) mask the whole cell.
      const parts = cls.sourceTypes || [];
      strategy = parts.length && parts.every((t) => SPAN_DETECTABLE.has(t)) ? 'spans' : 'full';
    } else if (type) strategy = mode;
    return { name: col.name, piiType: type, strategy };
  });

  let maskedCells = 0;
  const rows = result.rows.map((row, ri) => row.map((v, i) => {
    const { piiType, strategy } = plan[i];
    if (!strategy || v === null || v === undefined || String(v).trim() === '') return v;
    let out;
    if (strategy === 'spans') {
      const names = (classification[i] && classification[i].personSpans && classification[i].personSpans[ri]) || [];
      const r = maskSpans(String(v), names);
      if (!r.changed) return v;
      out = r.value;
    } else if (strategy === 'full') {
      out = maskAll(String(v));
    } else {
      out = maskValue(v, piiType, strategy);
    }
    if (out !== v) maskedCells++;
    return out;
  }));

  return {
    ...result,
    rows,
    masking: { mode, columns: plan.filter((p) => p.strategy), maskedCells },
  };
}

module.exports = { mask, maskValue, maskSpans };
