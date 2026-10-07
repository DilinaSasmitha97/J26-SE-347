// Calls the component exactly as an orchestrator will once the team's
// services are connected: a masked result in Member 2's format goes to the
// real /api/v4/present and /api/v4/simulate. Only fetching that result uses
// the demo routes (stand-ins for Members 1-3, see demo_api.py).

async function call(path, body) {
  const res = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    // fall through to the status error below
  }
  if (!res.ok || (data && data.status === "ERROR")) {
    const detail = (data && (data.detail || data.message || data.error)) || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

/** Liveness and capability report of the real API (pipeline version, LLM). */
export const health = () => call("/api/v4/health");

export const listDatasets = () => call("/demo/datasets");

/** Member 2's masked payload for a dataset, plus the security context and schema. */
export const fetchRows = (datasetId) => call("/demo/rows", { dataset_id: datasetId });

export function present(question, source, { useLlmSummary = false } = {}) {
  return call("/api/v4/present", {
    user_query: question,
    member2_result: source.member2_result,
    schema_meta: source.schema_meta,
    security_context: source.security_context,
    use_llm_summary: useLlmSummary,
  });
}

export function simulate(question, source, scenarioText) {
  return call("/api/v4/simulate", {
    user_query: question,
    member2_result: source.member2_result,
    schema_meta: source.schema_meta,
    security_context: source.security_context,
    scenario_text: scenarioText,
  });
}
