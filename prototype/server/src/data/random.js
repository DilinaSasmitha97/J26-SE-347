// Deterministic PRNG so every demo run shows identical data.
export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const pick = (rnd, arr) => arr[Math.floor(rnd() * arr.length)];
export const between = (rnd, min, max) => min + rnd() * (max - min);
export const intBetween = (rnd, min, max) => Math.floor(between(rnd, min, max + 1));
export const round2 = (n) => Math.round(n * 100) / 100;

// Weighted pick: entries are [value, weight]
export function weighted(rnd, entries) {
  const total = entries.reduce((s, e) => s + e[1], 0);
  let r = rnd() * total;
  for (const [value, w] of entries) {
    r -= w;
    if (r <= 0) return value;
  }
  return entries[entries.length - 1][0];
}
