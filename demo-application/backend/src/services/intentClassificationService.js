// Question-only intent classification. Forwards nothing but the question to the
// presentation service and accepts only a response that satisfies the contract:
// { nl_query, intent, presentation_types, prediction_needed }.

const INTENTS = Object.freeze([
  'TREND_ANALYSIS', 'COMPARISON', 'RANKING', 'PROPORTION', 'DISTRIBUTION',
  'CORRELATION', 'ANOMALY_DETECTION', 'KPI_SINGLE_VALUE', 'DETAIL_LOOKUP'
]);
const PRESENTATION_TYPES = Object.freeze(['table', 'single_value', 'bar_chart', 'pie_chart', 'line_chart', 'summary']);
const MAX_QUERY_CHARS = 2000;

class IntentClassificationError extends Error {
  constructor(code, message, status = 502) {
    super(message);
    this.name = 'IntentClassificationError';
    this.code = code;
    this.status = status;
  }
}

function validateClassificationRequest(body) {
  const nlQuery = body?.nl_query;
  if (typeof nlQuery !== 'string' || !nlQuery.trim() || nlQuery.length > MAX_QUERY_CHARS) {
    return { error: `Provide nl_query as a question of 1-${MAX_QUERY_CHARS.toLocaleString('en-US')} characters.` };
  }
  return { value: nlQuery };
}

// Returns a description of the first contract violation, or null.
function classificationProblem(payload, nlQuery) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return 'response is not a JSON object';
  if (payload.nl_query !== nlQuery) return 'nl_query does not echo the submitted question';
  if (!INTENTS.includes(payload.intent)) return 'intent is not a supported value';
  const types = payload.presentation_types;
  if (!Array.isArray(types) || !types.length) return 'presentation_types must be a non-empty array';
  if (types.some((type) => !PRESENTATION_TYPES.includes(type))) return 'presentation_types contains an unsupported value';
  if (new Set(types).size !== types.length) return 'presentation_types contains duplicates';
  if (typeof payload.prediction_needed !== 'boolean') return 'prediction_needed must be a Boolean';
  return null;
}

// Validates a classification the browser sends back for presentation:
// { intent, presentation_types } from the classifier's vocabulary.
function classificationChoiceProblem(classification) {
  if (!classification || typeof classification !== 'object' || Array.isArray(classification)) return 'classification must be an object';
  if (!INTENTS.includes(classification.intent)) return 'classification.intent is not a supported value';
  const types = classification.presentation_types;
  if (!Array.isArray(types) || !types.length) return 'classification.presentation_types must be a non-empty array';
  if (types.some((type) => !PRESENTATION_TYPES.includes(type))) return 'classification.presentation_types contains an unsupported value';
  if (new Set(types).size !== types.length) return 'classification.presentation_types contains duplicates';
  return null;
}

function serviceUrl() {
  return `${(process.env.PRESENTATION_SERVICE_URL || 'http://127.0.0.1:8004').replace(/\/$/, '')}/api/v4/classify-intent`;
}

async function classifyIntent(nlQuery, { signal } = {}) {
  const timeoutMs = Number(process.env.INTENT_CLASSIFICATION_TIMEOUT_MS || 30000);
  const signals = [AbortSignal.timeout(timeoutMs), signal].filter(Boolean);
  let response, payload;
  try {
    response = await fetch(serviceUrl(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nl_query: nlQuery }),
      signal: AbortSignal.any(signals)
    });
    payload = await response.json();
  } catch {
    if (signal?.aborted) throw new IntentClassificationError('CLASSIFICATION_CANCELLED', 'The classification request was cancelled.', 499);
    if (response) throw new IntentClassificationError('CLASSIFICATION_INVALID', 'The classifier returned a non-JSON response.');
    throw new IntentClassificationError('CLASSIFICATION_UNAVAILABLE', 'The intent classifier could not be reached or timed out.', 503);
  }
  if (!response.ok) {
    throw new IntentClassificationError('CLASSIFICATION_FAILED', `The intent classifier rejected the request (HTTP ${response.status}).`);
  }
  const problem = classificationProblem(payload, nlQuery);
  if (problem) throw new IntentClassificationError('CLASSIFICATION_INVALID', `The classifier response is invalid: ${problem}.`);
  return {
    nl_query: nlQuery,
    intent: payload.intent,
    presentation_types: [...payload.presentation_types],
    prediction_needed: payload.prediction_needed
  };
}

module.exports = {
  INTENTS,
  PRESENTATION_TYPES,
  MAX_QUERY_CHARS,
  IntentClassificationError,
  validateClassificationRequest,
  classificationProblem,
  classificationChoiceProblem,
  classifyIntent
};
