/**
 * NER stage of the PII pipeline — finds people's names, which regex cannot.
 *
 *   validate -> execute -> classifyColumns -> applyNer -> mask
 *
 * applyNer() looks only at columns the earlier signals left open (not PII, or
 * CONTAINS_PII) that hold real text and were not declared NONE. It samples their values and asks the
 * Python NER service (pii_service/ner_service.py) for PERSON spans:
 *   - most sampled values are a whole name  -> the column is PERSON
 *   - some cells contain a name in text     -> CONTAINS_PII, with per-row
 *                                              name spans for mask() to hide
 *
 * If the service is unreachable the layer fails closed by default: every text
 * column that could not be checked is marked UNVERIFIED and fully masked. A
 * security layer that silently skips name detection would leak exactly the
 * data it exists to protect. failMode 'open' keeps the values and only warns.
 */

'use strict';

/** Minimal client for the NER service. */
function createNerClient({ url = 'http://127.0.0.1:5002', timeoutMs = 5000 } = {}) {
  async function analyze(texts, entities = ['PERSON']) {
    if (!url) throw new Error('NER service not configured');
    const res = await fetch(`${url}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ texts, entities }),
      signal: AbortSignal.timeout(timeoutMs),
    });
    if (!res.ok) throw new Error(`NER service returned HTTP ${res.status}`);
    const body = await res.json();
    if (!Array.isArray(body.results) || body.results.length !== texts.length) {
      throw new Error('NER service returned a malformed response');
    }
    return body.results;
  }

  async function health() {
    try {
      const res = await fetch(`${url}/health`, { signal: AbortSignal.timeout(1500) });
      return res.ok ? await res.json() : { status: 'error', httpStatus: res.status };
    } catch (e) {
      return { status: 'unavailable', detail: e.message };
    }
  }

  return { analyze, health, url };
}

/** A column is worth running NER on if its values contain letters (not ids, amounts or dates). */
function textValueIndexes(rows, col, limit) {
  const idx = [];
  for (let r = 0; r < rows.length && idx.length < limit; r++) {
    const v = rows[r][col];
    if (typeof v === 'string' && /\p{L}/u.test(v)) idx.push(r);
  }
  return idx;
}

/**
 * Enrich a classification with NER results, in place.
 * Returns { status: 'ok' | 'skipped' | 'unavailable', warnings, elapsedMs }.
 */
async function applyNer(result, classification, client, options = {}) {
  const { failMode = 'closed', sampleSize = 50, sampleThreshold = 0.6, isolatedThreshold = 0.3 } = options;
  const started = Date.now();
  const warnings = [];

  const candidates = [];
  classification.forEach((cls, col) => {
    if (cls.piiType !== null && cls.piiType !== 'CONTAINS_PII') return;
    if (cls.declaredSafe) return; // reviewed as not personal data in pii_columns.json
    const sample = textValueIndexes(result.rows, col, sampleSize);
    if (sample.length) candidates.push({ col, sample });
  });
  if (!candidates.length) return { status: 'skipped', warnings, elapsedMs: 0 };

  const texts = candidates.flatMap(({ col, sample }) => sample.map((r) => result.rows[r][col]));
  let found;
  try {
    found = await client.analyze(texts);
  } catch (e) {
    for (const { col } of candidates) {
      const cls = classification[col];
      if (failMode === 'closed') {
        cls.piiType = 'UNVERIFIED';
        cls.method = 'ner-unavailable';
        cls.confidence = null;
      }
    }
    warnings.push(failMode === 'closed'
      ? `NER service unavailable (${e.message}) — ${candidates.length} text column(s) could not be checked for names and were fully masked`
      : `NER service unavailable (${e.message}) — ${candidates.length} text column(s) were NOT checked for names`);
    return { status: 'unavailable', warnings, elapsedMs: Date.now() - started };
  }

  let offset = 0;
  for (const { col, sample } of candidates) {
    const spans = found.slice(offset, offset + sample.length);
    offset += sample.length;
    const cls = classification[col];

    // "Whole" = one PERSON span covers the entire (trimmed) cell, e.g. a name
    // column. "Embedded" = a name inside longer text, e.g. a notes column.
    let wholeNames = 0;
    let embeddedNames = 0;
    sample.forEach((r, k) => {
      const people = spans[k].filter((s) => s.type === 'PERSON');
      if (!people.length) return;
      const raw = result.rows[r][col];
      const from = raw.length - raw.trimStart().length;
      const to = raw.trimEnd().length;
      if (people.some((s) => s.start <= from && s.end >= to)) wholeNames++;
      else embeddedNames++;
    });
    cls.evidence = { ...(cls.evidence || {}), ner: { sampled: sample.length, wholeNames, embeddedNames } };

    if (cls.piiType === null && wholeNames / sample.length >= sampleThreshold) {
      cls.piiType = 'PERSON';
      cls.method = 'ner-sample';
      cls.confidence = wholeNames === sample.length ? 'high' : 'medium';
      continue;
    }
    // A name inside text always counts. Isolated one-word hits in a column of
    // short labels (NER reading the city "Kandy" as a person) only count when
    // they are a real share of the column; otherwise they are noise, kept in
    // the evidence but not masked.
    if (!embeddedNames && wholeNames / sample.length < isolatedThreshold) {
      if (wholeNames) cls.evidence.ner.ignoredIsolatedHits = wholeNames;
      continue;
    }

    // Names appear inside text: collect name spans for every row, not just the sample.
    const allRows = textValueIndexes(result.rows, col, Infinity);
    let rowSpans = spans;
    if (allRows.length > sample.length) {
      try {
        rowSpans = await client.analyze(allRows.map((r) => result.rows[r][col]));
      } catch (e) {
        cls.piiType = 'UNVERIFIED';
        cls.method = 'ner-unavailable';
        warnings.push(`NER failed part-way on column ${cls.name}; fully masked`);
        continue;
      }
    }
    cls.personSpans = {};
    allRows.forEach((r, k) => {
      const people = rowSpans[k].filter((s) => s.type === 'PERSON');
      if (people.length) cls.personSpans[r] = people.map(({ start, end }) => ({ start, end }));
    });
    if (cls.piiType === null) {
      cls.piiType = 'CONTAINS_PII';
      cls.method = 'ner-scan';
      cls.confidence = 'medium';
    }
  }

  return { status: 'ok', warnings, elapsedMs: Date.now() - started };
}

module.exports = { createNerClient, applyNer };
