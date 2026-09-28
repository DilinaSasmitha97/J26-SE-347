/**
 * Regex-driven PII detectors — the pattern half of the PII pipeline (the NER
 * half handles names and other free-text entities).
 *
 * Each detector pairs a *candidate* regex with a *validator*. The regex is
 * deliberately loose so formatting variations are found ("077 123 4567",
 * "+94-77-1234567"); the validator then rejects look-alikes, which is what
 * keeps order numbers, amounts and dates from being masked:
 *
 *   EMAIL        local@domain.tld
 *   PHONE        Sri Lankan mobile/landline (+94 / 0094 / 0 prefix), or any
 *                international +<country code> number of E.164 length
 *   NIC          Sri Lankan National Identity Card — old (9 digits + V/X) and
 *                new (12 digits); the embedded birth year and day-of-year
 *                (+500 for women) must be plausible
 *   CREDIT_CARD  13–19 digits, known issuer prefix, Luhn checksum
 *   IBAN         country code + check digits, ISO 7064 mod-97 checksum
 *   IP_ADDRESS   IPv4 with every octet 0–255
 *
 * detectInText(text)  -> every PII span inside a longer string
 * detectValue(value)  -> the PII type when a *whole* cell is one PII value
 */

'use strict';

const digitsOnly = (s) => s.replace(/\D/g, '');

// --- validators -------------------------------------------------------------

function luhnValid(digits) {
  let sum = 0;
  let double = false;
  for (let i = digits.length - 1; i >= 0; i--) {
    let d = digits.charCodeAt(i) - 48;
    if (double) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    double = !double;
  }
  return sum % 10 === 0;
}

// Visa, Mastercard (51–55, 2221–2720), Amex, Discover/UnionPay, JCB, Diners.
const CARD_PREFIX = /^(4|5[1-5]|2[2-7]|3[47]|6|35|30|36|38)/;

function isCreditCard(match) {
  const d = digitsOnly(match);
  return d.length >= 13 && d.length <= 19 && CARD_PREFIX.test(d) && luhnValid(d) && !/^(\d)\1+$/.test(d);
}

/** Day-of-year code in a Sri Lankan NIC: 1–366 for men, 501–866 for women. */
function validNicDay(day) {
  return (day >= 1 && day <= 366) || (day >= 501 && day <= 866);
}

function isNic(match) {
  const s = match.toUpperCase();
  if (/^\d{9}[VX]$/.test(s)) {
    return validNicDay(Number(s.slice(2, 5)));
  }
  if (/^\d{12}$/.test(s)) {
    const year = Number(s.slice(0, 4));
    return year >= 1900 && year <= new Date().getFullYear() && validNicDay(Number(s.slice(4, 7)));
  }
  return false;
}

function isPhone(match) {
  const compact = match.replace(/[\s\-().]/g, '');
  // Sri Lanka: 9 national digits after the prefix; mobiles are 07x, landlines 0[1-9]x.
  const lk = compact.match(/^(?:\+94|0094|0)(\d{9})$/);
  if (lk) return /^(7[0-8]|[1-6]\d|8[1-9]|9[1-9])/.test(lk[1]);
  // Other countries: + followed by 8–15 digits (E.164), not starting with 0.
  return /^\+[1-9]\d{7,14}$/.test(compact);
}

function isIban(match) {
  const s = match.replace(/\s/g, '').toUpperCase();
  if (!/^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$/.test(s)) return false;
  const rearranged = s.slice(4) + s.slice(0, 4);
  let remainder = 0;
  for (const ch of rearranged) {
    const n = ch >= 'A' ? String(ch.charCodeAt(0) - 55) : ch;
    for (const digit of n) remainder = (remainder * 10 + Number(digit)) % 97;
  }
  return remainder === 1;
}

function isIpv4(match) {
  return match.split('.').every((o) => Number(o) <= 255 && String(Number(o)) === o);
}

// --- detectors ----------------------------------------------------------------
// Order matters only for tie-breaking overlaps of equal length (higher first).

const DETECTORS = [
  {
    type: 'EMAIL',
    pattern: /[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}/g,
    validate: () => true,
  },
  {
    type: 'CREDIT_CARD',
    pattern: /(?<![\d-])\d(?:[ -]?\d){12,18}(?![\d-])/g,
    validate: isCreditCard,
  },
  {
    type: 'IBAN',
    pattern: /\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b/g,
    validate: isIban,
  },
  {
    type: 'NIC',
    pattern: /(?<![\dA-Za-z])(?:\d{9}[VvXx]|\d{12})(?![\dA-Za-z])/g,
    validate: isNic,
  },
  {
    type: 'PHONE',
    pattern: /(?<![\d+(])(?:\+|00|\()?\d[\d\s\-().]{7,17}\d(?!\d)/g,
    validate: isPhone,
  },
  {
    type: 'IP_ADDRESS',
    pattern: /(?<![\d.])\d{1,3}(?:\.\d{1,3}){3}(?![\d.])/g,
    validate: isIpv4,
  },
];

const PII_TYPES = DETECTORS.map((d) => d.type);

/**
 * Find every PII span in a string. Overlapping candidates are resolved in
 * favour of the longer match (a card number beats a phone number found inside
 * it), then by detector order.
 */
function detectInText(text) {
  if (text === null || text === undefined) return [];
  const str = String(text);
  const found = [];
  DETECTORS.forEach((det, rank) => {
    det.pattern.lastIndex = 0;
    for (const m of str.matchAll(det.pattern)) {
      const value = m[0].trim();
      const start = m.index + m[0].indexOf(value);
      if (det.validate(value)) found.push({ type: det.type, value, start, end: start + value.length, rank });
    }
  });

  found.sort((a, b) => (b.end - b.start) - (a.end - a.start) || a.rank - b.rank);
  const kept = [];
  for (const f of found) {
    if (kept.every((k) => f.end <= k.start || f.start >= k.end)) kept.push(f);
  }
  return kept.sort((a, b) => a.start - b.start).map(({ rank, ...span }) => span);
}

/** The PII type when the whole value is a single PII item, else null. */
function detectValue(value) {
  if (value === null || value === undefined) return null;
  const str = String(value).trim();
  if (!str) return null;
  const spans = detectInText(str);
  return spans.length === 1 && spans[0].start === 0 && spans[0].end === str.length ? spans[0].type : null;
}

module.exports = {
  detectInText,
  detectValue,
  PII_TYPES,
  // validators, exported for inspection
  luhnValid,
  isCreditCard,
  isNic,
  isPhone,
  isIban,
  isIpv4,
};
