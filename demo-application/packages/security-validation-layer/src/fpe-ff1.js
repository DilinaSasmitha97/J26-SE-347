/**
 * FF1 format-preserving encryption — NIST SP 800-38G (Rev. 1), AES as the
 * block cipher. Encrypts a string of numerals (digits, letters, ...) in some
 * radix into another string of the same length and alphabet, reversibly.
 *
 * Used for pseudonymisation (GDPR Art. 4(5)): the same input under the same
 * key and tweak always gives the same output, so encrypted columns can still
 * be grouped, joined and counted, while re-identification needs the key.
 *
 * Verified against the NIST FF1 sample vectors (see the self-test in
 * verifyFF1()). Rev. 1 requires radix^length >= 1,000,000; shorter inputs are
 * refused rather than weakly encrypted.
 */

'use strict';

const crypto = require('crypto');

const MIN_DOMAIN = 1000000n;
const ROUNDS = 10;

function aesEcb(key) {
  const algo = { 16: 'aes-128-ecb', 24: 'aes-192-ecb', 32: 'aes-256-ecb' }[key.length];
  if (!algo) throw new Error('FF1 key must be 16, 24 or 32 bytes');
  return (block) => {
    const c = crypto.createCipheriv(algo, key, null);
    c.setAutoPadding(false);
    return Buffer.concat([c.update(block), c.final()]);
  };
}

/** CBC-MAC with a zero IV over whole blocks — the PRF of SP 800-38G. */
function prf(ciph, data) {
  let y = Buffer.alloc(16);
  for (let i = 0; i < data.length; i += 16) {
    const block = Buffer.alloc(16);
    for (let j = 0; j < 16; j++) block[j] = y[j] ^ data[i + j];
    y = ciph(block);
  }
  return y;
}

function bigFromBytes(buf) {
  return buf.length ? BigInt('0x' + buf.toString('hex')) : 0n;
}

function bytesFromBig(n, len) {
  const hex = n.toString(16).padStart(len * 2, '0');
  return Buffer.from(hex.slice(-len * 2), 'hex');
}

function num(digits, radix) {
  let x = 0n;
  for (const d of digits) x = x * radix + BigInt(d);
  return x;
}

function str(x, radix, len) {
  const out = new Array(len);
  for (let i = len - 1; i >= 0; i--) {
    out[i] = Number(x % radix);
    x /= radix;
  }
  return out;
}

const mod = (a, m) => ((a % m) + m) % m;

/** Core FF1 on numeral arrays. decrypt runs the Feistel rounds backwards. */
function ff1(key, tweak, radixNum, X, decrypt) {
  const radix = BigInt(radixNum);
  const n = X.length;
  if (radixNum < 2 || radixNum > 65536) throw new Error('FF1 radix must be 2..65536');
  if (radix ** BigInt(n) < MIN_DOMAIN) throw new Error(`FF1 input too short: radix^length must be >= 1,000,000`);

  const ciph = aesEcb(key);
  const t = tweak.length;
  const u = Math.floor(n / 2);
  const v = n - u;
  let A = X.slice(0, u);
  let B = X.slice(u);
  const b = Math.ceil(Math.ceil(v * Math.log2(radixNum)) / 8);
  const d = 4 * Math.ceil(b / 4) + 4;

  const P = Buffer.alloc(16);
  P[0] = 1; P[1] = 2; P[2] = 1;
  P.writeUIntBE(radixNum, 3, 3);
  P[6] = 10;
  P[7] = u % 256;
  P.writeUInt32BE(n, 8);
  P.writeUInt32BE(t, 12);

  const padLen = mod(-t - b - 1, 16);
  const roundOrder = decrypt ? [...Array(ROUNDS).keys()].reverse() : [...Array(ROUNDS).keys()];

  for (const i of roundOrder) {
    const m = i % 2 === 0 ? u : v;
    const other = decrypt ? A : B; // the half fed to the round function
    const Q = Buffer.concat([tweak, Buffer.alloc(padLen), Buffer.from([i]), bytesFromBig(num(other, radix), b)]);
    const R = prf(ciph, Buffer.concat([P, Q]));

    // S = first d bytes of R || CIPH(R xor [1]) || CIPH(R xor [2]) || ...
    const blocks = [R];
    for (let j = 1; j < Math.ceil(d / 16); j++) {
      const x = Buffer.from(R);
      const jb = bytesFromBig(BigInt(j), 16);
      for (let k = 0; k < 16; k++) x[k] ^= jb[k];
      blocks.push(ciph(x));
    }
    const y = bigFromBytes(Buffer.concat(blocks).subarray(0, d));
    const modulus = radix ** BigInt(m);

    if (!decrypt) {
      const c = mod(num(A, radix) + y, modulus);
      A = B;
      B = str(c, radix, m);
    } else {
      const c = mod(num(B, radix) - y, modulus);
      B = A;
      A = str(c, radix, m);
    }
  }
  return [...A, ...B];
}

/**
 * Encrypt/decrypt a string over an alphabet (its length is the radix).
 * Every character must belong to the alphabet.
 */
function createFF1(key, alphabet) {
  const keyBuf = Buffer.isBuffer(key) ? key : Buffer.from(key, 'hex');
  const radix = alphabet.length;
  const index = new Map([...alphabet].map((ch, i) => [ch, i]));
  const toNumerals = (s) => [...s].map((ch) => {
    if (!index.has(ch)) throw new Error(`character "${ch}" is not in the FF1 alphabet`);
    return index.get(ch);
  });
  const toString = (numerals) => numerals.map((i) => alphabet[i]).join('');
  const tweakBuf = (tweak) => (Buffer.isBuffer(tweak) ? tweak : Buffer.from(String(tweak || ''), 'utf8'));

  return {
    radix,
    minLength: Math.ceil(Math.log(1000000) / Math.log(radix) - 1e-9),
    encrypt: (s, tweak) => toString(ff1(keyBuf, tweakBuf(tweak), radix, toNumerals(s), false)),
    decrypt: (s, tweak) => toString(ff1(keyBuf, tweakBuf(tweak), radix, toNumerals(s), true)),
  };
}

const DIGITS = '0123456789';
const BASE36 = '0123456789abcdefghijklmnopqrstuvwxyz';

/** NIST SP 800-38G FF1 sample vectors; throws if the implementation disagrees. */
function verifyFF1() {
  const k128 = '2B7E151628AED2A6ABF7158809CF4F3C';
  const vectors = [
    { key: k128, tweak: '', alphabet: DIGITS, pt: '0123456789', ct: '2433477484' },
    { key: k128, tweak: '39383736353433323130', alphabet: DIGITS, pt: '0123456789', ct: '6124200773' },
    { key: k128, tweak: '3737373770717273373737', alphabet: BASE36, pt: '0123456789abcdefghi', ct: 'a9tv40mll9kdu509eum' },
  ];
  for (const v of vectors) {
    const f = createFF1(v.key, v.alphabet);
    const tweak = Buffer.from(v.tweak, 'hex');
    const ct = f.encrypt(v.pt, tweak);
    if (ct !== v.ct) throw new Error(`FF1 self-test failed: ${v.pt} -> ${ct}, expected ${v.ct}`);
    if (f.decrypt(ct, tweak) !== v.pt) throw new Error(`FF1 self-test failed to decrypt ${ct}`);
  }
  return vectors.length;
}

module.exports = { createFF1, verifyFF1, DIGITS, BASE36 };
