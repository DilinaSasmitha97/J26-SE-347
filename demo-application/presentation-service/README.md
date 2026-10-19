# Vonara presentation service in the integrated demo

This folder contains a standalone copy of Vonara's runtime modules. The original
`Vonara/` folder is preserved. The service has no database connection and uses
hybrid LLM/rule intent analysis, statistical forecasting, charts and verified summaries.

From `demo-application` on Windows, install once:

```powershell
python -m venv .\presentation-service\.venv
.\presentation-service\.venv\Scripts\python.exe -m pip install -r .\presentation-service\requirements.txt
```

Start it in its own terminal:

```powershell
.\presentation-service\.venv\Scripts\python.exe .\presentation-service\run_server.py
```

The server listens on `127.0.0.1:8004`. Set `PRESENTATION_PORT` to override the
port and update the Node gateway's `PRESENTATION_SERVICE_URL` accordingly.
LLM-assisted intent classification is enabled by default in the Node gateway.
Copy `.env.example` to `.env` in this folder and fill `GROQ_API_KEY`:

```dotenv
PRESENTATION_LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

The Groq adapter requests a JSON response. Use a model available to your Groq
account with JSON-output support. Provider settings belong to this folder's
`.env`; the service does not discover the NL-to-SQL service's environment file.
The `.env` is ignored by Git. Restart the presentation service and Node gateway
after configuration changes. `GET /api/v4/health` reports provider, active model,
and key availability without returning the key.

Only the question, permitted schema and grounding context are supplied to the
LLM for intent analysis. Numerical forecasting and summary generation stay
deterministic (`use_llm_summary=false`). Missing keys or failed LLM calls fall
back to rules; the analysis metadata records the actual mode. To disable hybrid
classification, set `PRESENTATION_USE_LLM=false` in `demo-application/.env`.

Internal routes:

- `POST /api/v4/classify-intent`: question-only classification (package
  `intent_classification/`). Returns `nl_query` (echoed unchanged), `intent`,
  `presentation_types` and `prediction_needed`. The request accepts only
  `nl_query`; any other field is rejected (422). Rules run first, using the
  stage-8 Vonara lexicon and confidence formula copied into
  `intent_classification/vonara_rules.py`; formats follow the intent or the
  formats the user names. A decision below 0.55 confidence is sent to the LLM
  (one attempt), which replaces it only at 0.60 or more. No key, a transport
  error or invalid output keeps the rule answers. A declined forecast and
  "only <format>" always win. Each request logs one line with the confidences
  and `classified_by` (rules, llm or rules+llm); confidences are never returned.
- `POST /api/v4/predict`: prediction layer (package `prediction_layer/`).
  `{member2_result, user_query, intent, prediction_needed}`. Drives the
  stage-2..8 modules from the intent classification instead of the old
  analyzer: Stage 1 `map_intent_to_strategy`, Stage 2 `assess_readiness`,
  Stage 3 `select_model` (benchmark guard), Stage 4 `generate_forecast` (95%
  bands, horizon from the question), `strategies.execute`, Stage 5
  `detect_anomalies(method="COMBINED")`, Stage 7 `summarize` with verified LLM
  narration. Forecast charts extend the line chart with
  `visualization.extend_with_forecast`. Modes: FORECAST, or ANOMALY_ONLY for an
  anomaly question. No what-if simulation (Stage 6).
- `POST /api/v4/render`: data presentation layer (package `data_presentation/`).
  `{member2_result, user_query, intent, presentation_types}` → one view per
  type, in order, each `available` or with a `reason`. Tables reuse
  `response_renderer.build_table_block`; charts are Vega-Lite v5 built per
  requested type (pie 2–8 non-negative slices, bar top 25, line needs a time
  axis); the summary uses `summarization.summarize` with verified LLM narration
  (`PRESENTATION_LLM_SUMMARY=false` keeps it to computed facts). No forecasting
  code runs here.
- `POST /api/v4/analyze`: question understanding before generation.
- `POST /api/v4/present`: full processing of masked execution results.
- `POST /api/v4/simulate`: a scenario over already-authorized masked rows.
- `GET /api/v4/health`: liveness and installed forecasting capabilities.

The React app calls only the Node gateway, never these routes directly. Keep
this service on the internal network. The demo gateway uses the user and policy
JSON supplied by the operator; it does not load a saved demo-user registry or
authenticate the pasted claims.

Differences from the original prototype:

- All runtime code lives in this folder, with no import dependency on `Vonara/`.
- Public gateway requests use schema filtered by the operator's supplied policy
  and tenant/role claims from the pasted user JSON.
- REST presentation caching is disabled. Direct pipeline caching includes schema,
  full security context, masking/truncation metadata, and forecast policy in its key.
- Request models bound question/scenario lengths, confidence and horizon.
- Runtime dependencies support Python 3.10+. The original research requirements
  are preserved in `requirements-vonara-reference.txt`; their benchmark scores
  are not claims about this demo environment.

From this folder, run the integration tests:

```powershell
.\.venv\Scripts\python.exe -m unittest test_demo_integration test_intent_classification test_data_presentation test_prediction_layer -v
```

Permissions come from the supplied policy JSON. No role policy files are loaded
by the demo gateway.
Hiring trends can use `employees.joined_date`; a useful forecast needs enough
complete observations with an adequate signal. Short, constant, noisy, raw-row
or capped histories may be refused. The UI displays that reason.

The gateway temporarily stores masked results for ten minutes, with at most
100 entries per Node process. A server restart or capacity eviction invalidates
the result ID. Simulation checks the current identity, tenant and full effective
policy before using it. No raw rows are accepted from the browser for simulation.
