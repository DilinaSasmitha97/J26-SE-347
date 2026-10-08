/**
 * Format-preserving pseudonymisation of PII values, built on FF1.
 *
 * protect(value, type) encrypts just the identifying part of a value and keeps
 * its shape, so the result still validates and displays like the original:
 *
 *   EMAIL        local part (a-z0-9) encrypted, punctuation + domain kept
 *   PHONE        "+94" / leading "0" kept, remaining digits encrypted
 *   NIC          digits encrypted, V/X suffix kept
 *   CREDIT_CARD  all digits but the last four encrypted (PCI DSS allows last 4)
 *   IBAN         country code kept, the rest encrypted
 *   PERSON       letters encrypted, capitalisation and spaces kept
 *   IP_ADDRESS   the 32-bit address encrypted, still a valid IPv4
 *
 * reveal(value, type) is the exact inverse — re-identification needs the key,
 * which is what makes this pseudonymisation rather than anonymisation.
 * The tweak binds each ciphertext to its PII type (and optional context such
 * as a tenant id), so the same digits as a phone and as a NIC encrypt
 * differently. Types without a safe format-preserving form (ADDRESS, SECRET,
 * DATE_OF_BIRTH), and values too short for FF1's minimum domain, return null;
 * the caller then redacts instead.
 */

'use strict';

const { createFF1, DIGITS } = require('./fpe-ff1');

const LOWER36 = '0123456789abcdefghijklmnopqrstuvwxyz';
const UPPER36 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const LETTERS = 'abcdefghijklmnopqrstuvwxyz';
const BITS = '01';

/**
 * Encrypt (or decrypt) only the characters selected by `pick`, in place,
 * leaving every other character where it was.
 */
function transformSelected(value, pick, cipher, tweak, decrypt, mapIn = (c) => c, mapOut = (c) => c) {
  const chars = [...value];
  const positions = [];
  for (let i = 0; i < chars.length; i++) if (pick(chars[i], i)) positions.push(i);
  if (positions.length < cipher.minLength) return null;
  const plain = positions.map((i) => mapIn(chars[i])).join('');
  const out = decrypt ? cipher.decrypt(plain, tweak) : cipher.encrypt(plain, tweak);
  positions.forEach((pos, k) => { chars[pos] = mapOut(out[k], chars[pos]); });
  return chars.join('');
}

const isDigit = (c) => c >= '0' && c <= '9';

function createPiiFpe(key, { context = '' } = {}) {
  if (!key) throw new Error('FPE key is required');
  const keyBuf = Buffer.isBuffer(key) ? key : Buffer.from(key, 'hex');
  const digits = createFF1(keyBuf, DIGITS);
  const lower36 = createFF1(keyBuf, LOWER36);
  const upper36 = createFF1(keyBuf, UPPER36);
  const letters = createFF1(keyBuf, LETTERS);
  const bits = createFF1(keyBuf, BITS);
  const tweakFor = (type) => `svl:${context}:${type}`;

  const handlers = {
    EMAIL(v, t, dec) {
      const at = v.lastIndexOf('@');
      if (at < 1) return null;
      const local = v.slice(0, at).toLowerCase();
      const isAlnum = (c) => isDigit(c) || (c >= 'a' && c <= 'z');
      const out = transformSelected(local, isAlnum, lower36, t, dec);
      return out === null ? null : out + v.slice(at);
    },
    PHONE(v, t, dec) {
      // Keep the country code (+94 / 0094) or trunk prefix (0) so the number still routes as Sri Lankan.
      let keep = 0;
      const compact = v.replace(/\D/g, '');
      if (v.trim().startsWith('+')) keep = 2;
      else if (compact.startsWith('00')) keep = 4;
      else if (compact.startsWith('0')) keep = 1;
      let seen = 0;
      return transformSelected(v, (c) => isDigit(c) && ++seen > keep, digits, t, dec);
    },
    NIC(v, t, dec) {
      return transformSelected(v, isDigit, digits, t, dec);
    },
    CREDIT_CARD(v, t, dec) {
      const total = (v.match(/\d/g) || []).length;
      let seen = 0;
      return transformSelected(v, (c) => isDigit(c) && ++seen <= total - 4, digits, t, dec);
    },
    IBAN(v, t, dec) {
      let seen = 0;
      const isAlnum = (c) => /[A-Za-z0-9]/.test(c);
      return transformSelected(v.toUpperCase(), (c) => isAlnum(c) && ++seen > 2, upper36, t, dec);
    },
    PERSON(v, t, dec) {
      // ASCII letters only; capitalisation is restored per position.
      const isLetter = (c) => /[A-Za-z]/.test(c);
      if (/[^\x00-\x7F]/.test(v)) return null;
      return transformSelected(v, isLetter, letters, t, dec,
        (c) => c.toLowerCase(),
        (out, orig) => (orig === orig.toUpperCase() ? out.toUpperCase() : out));
    },
    IP_ADDRESS(v, t, dec) {
      const parts = v.trim().split('.');
      if (parts.length !== 4 || parts.some((p) => !/^\d{1,3}$/.test(p) || Number(p) > 255)) return null;
      const bitString = parts.map((p) => Number(p).toString(2).padStart(8, '0')).join('');
      const out = dec ? bits.decrypt(bitString, t) : bits.encrypt(bitString, t);
      return [0, 8, 16, 24].map((i) => parseInt(out.slice(i, i + 8), 2)).join('.');
    },
  };

  function run(value, type, decrypt) {
    if (value === null || value === undefined) return value;
    const handler = handlers[type];
    if (!handler) return null;
    try {
      return handler(String(value), tweakFor(type), decrypt);
    } catch (e) {
      return null; // e.g. a character outside the alphabet: caller redacts
    }
  }

  return {
    protect: (value, type) => run(value, type, false),
    reveal: (value, type) => run(value, type, true),
    supports: (type) => Boolean(handlers[type]),
  };
}

module.exports = { createPiiFpe };
