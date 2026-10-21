# Integrated Secure NL-to-SQL Demo

This application combines the policy backend, NL-to-SQL service, SQLGlot
inspection service, Navodya's JavaScript security-validation package, PII NER,
Vonara's presentation/prediction service, and the React demonstration UI.

See [the architecture diagrams](ARCHITECTURE.md) for the current service topology,
tenant-isolation execution flow, and implementation map.
See [the component process flows](PROCESS_FLOW.md) for inputs, outputs, data
relationships, API payloads, and the internal SQL-generation steps.

## Request flow

`frontend -> [user clicks Generate SQL] -> backend -> intent classification (question only) -> [user clicks Continue to SQL] -> NL-to-SQL -> SQL safety / access checks -> tenant isolation repair -> independent tenant / policy revalidation -> read-only database -> PII masking -> data presentation (classified formats) -> frontend`

After **Validate & execute** the gateway keeps the masked result under a
`resultId`, and the page asks `POST /api/present-result` to show it in the
formats the intent classification recommended. Every recommended format gets a
tab: tables, a single-value card, Vega-Lite bar, pie and line charts, and a
summary. The summary is written by the configured LLM from computed facts and
shown only if every number in it matches those facts; otherwise the facts are
shown as written. A recommended format the actual rows cannot support (a pie
chart of 50 departments, a single value from 12 rows) keeps its tab and explains
why. Without a classification (Continue without classification) the formats are
chosen from the shape of the data.

When the classification asks for a forecast (`prediction_needed`), or the
question is about anomalies (`ANOMALY_DETECTION`), the page also calls
`POST /api/predict-result`. The prediction layer maps the intent to a
predictive strategy, checks data readiness (points, missing periods,
stationarity, signal quality, truncation) and refuses with a reason when the
data cannot support a forecast. Otherwise it selects a model (linear regression,
Holt, SARIMA, seasonal naive or naive, kept only if it beats the naive
benchmarks on the series' own history) and forecasts the requested horizon
("next 6 months"; 3 periods by default) with 95% prediction bands. It also flags
historical anomalies and predicted threshold breaches (IQR fence + Z-score) and
writes a unified historical + predictive summary whose numbers are verified.
The result appears in a separate Prediction card with Forecast, Forecast table,
Anomalies, Readiness & method and Summary tabs. What-if simulation is not part
of this flow. The older all-in-one prediction pipeline stays switched off
(`PRESENTATION_PREDICTION_ENABLED=false`).

Intent classification is a separate step that runs before SQL generation. It
reads only the question and returns the analytical intent (one of
`TREND_ANALYSIS`, `COMPARISON`, `RANKING`, `PROPORTION`, `DISTRIBUTION`,
`CORRELATION`, `ANOMALY_DETECTION`, `KPI_SINGLE_VALUE`, `DETAIL_LOOKUP`),
recommended presentation types (`table`, `single_value`, `bar_chart`,
`pie_chart`, `line_chart`, `summary`) and whether a forecast is requested. It
uses no schema, policy, user claims or rules, so it works while those editors
are empty. These are recommendations: whether the returned rows support a chart
type or a forecast is decided after execution.

Rules decide first: the stage-8 Vonara keyword scoring gives each decision a
confidence. A decision at or above 0.55 is final; a weaker one is sent to the
LLM, whose answer replaces it only when the LLM's own confidence is at least
0.60. Without a provider key, or if the LLM fails, the rule answers stay. A
declined forecast ("without predictions") and "only <format>" always win.
Confidences and the deciding source appear only in the presentation service's
console log, never in the response.

The frontend calls only the Node backend. User policy, Authenticated user and
NL-to-SQL rules start empty and remain editable. Paste or upload your own JSON;
the application does not load stored demo users or role policy files. Reset
clears those fields. User and policy are required; extra NL-to-SQL rules are
optional. User JSON must include `userId` and `role`. Policy JSON must include
`allowedTables`; its `valueFrom` filters resolve against the supplied user claims.
The gateway uses this manual context for generation, checks, masking and scenarios.
This console treats the operator's inputs as demo context, without authenticating
those claims. Tenant enforcement requires a positive integer `user.tenantId`;
use a decimal string for IDs above JavaScript's safe integer range. A deployed
system must supply identity and policy from authenticated server context.

Tenant isolation is a separate mandatory stage in **Validate & execute**.
It corrects missing or incorrect simple tenant equalities and completes coverage
for every table alias, including repeated tables and self joins. Its trusted
ownership registry is `sqlglot-service/tenant_registry.json`, synchronized with
the `enterprise_hrms_alpha` schema from `Dump20261021.sql`. All 51 directly
tenant-scoped tables, including `tenants`, use `tenant_id`. See the
[registry coverage notes](sqlglot-service/tenant_registry.md) for excluded shared
and parent-owned tables and compatibility with the older demo schema.
Missing policy tenant rules never make
a registered table global. Conflicting tenant policy values block the request.
Additional employee/department row restrictions must already be present as
verifiable mandatory conditions; the tenant repair stage does not invent them.

The current repair rules support one SELECT over registered physical tables,
inner/cross joins, left joins, aggregation, ordering, limits and window functions.
Left-joined sources receive guards in their own ON conditions so unmatched rows
are preserved. CTEs, nested queries, set operations, right/full joins, NATURAL/
USING joins, qualified databases, custom/unrecognized functions, unbound parameters, unknown ownership and
ambiguous/conflicting Boolean tenant expressions are refused rather than
executed. This is deterministic AST repair; there is no LLM repair fallback.

The **Tenant isolation repair** frontend card reports `REPAIRED`,
`UNCHANGED_VERIFIED`, `CANNOT_REPAIR`, `BLOCKED`, or `UNAVAILABLE`, with initial
alias findings, changes, original SQL and final verified SQL. Final verification
reparses the serialized SQL, checks mandatory tenant and additional row guards,
then reruns SQL safety and access checks. Only that verified candidate reaches
execution, with trusted tenant values bound separately in MySQL and SQLite.
Service failures block execution. `/api/secure-query` with `execute: false`
previews the verified repair; `/api/verify-sql` remains validation-only and
does not repair SQL. The NL service's legacy `/api/v1/ask` rejects
`execute_query: true` with `GATEWAY_EXECUTION_REQUIRED`, preventing direct
execution outside the security gateway.

Restart SQLGlot, the backend and frontend after installing this feature.
SQLGlot's tested version is pinned in its requirements file. Run isolation tests:

```powershell
Push-Location .\sqlglot-service
.\.venv\Scripts\python.exe -m unittest -v test_tenant_isolation
Pop-Location
npm test --prefix .\backend
npm test --prefix .\frontend
```

The gateway sends exactly two fields to the NL-to-SQL service: `user_query`
(the question) and `injected_rules` (your pasted rules JSON object, or `null`).
It does not append user-policy constraints, Vonara analysis hints or the
intent classification. The SQL
service formats the provided JSON for its model prompt and generates its own
schema, entity and relationship hints internally. The submitted rules appear
under the SQL draft without overwriting your editors. Editing any context field
invalidates the draft. User policy is applied during SQL validation and execution.

In the pipeline UI, nothing is classified while you type. Click **Generate
SQL** to classify the question: the intent card shows the intent, the
recommended formats, **Prediction needed: Yes/No**, and the structured JSON. No
SQL is generated yet. Click **Continue to SQL** to send the question to the
NL-to-SQL service. If classification fails, the card shows the error with
**Retry classification**, and **Continue without classification** generates SQL
anyway. Changing the question cancels a pending classification and clears its
result, the SQL draft and execution results; late responses for an older
question are ignored. Editing policy, user or rules invalidates the SQL draft
but keeps the classification of an unchanged question.

After **Continue to SQL** creates a draft, review or edit
the SQL in step 2. Click **Validate & execute** to run security and policy checks
on that edited SQL before read-only execution and masking. Generation does not
execute the query, and editing SQL clears results from the previous version.

## Start the services

Install the new service and frontend dependencies once from `demo-application`:

```powershell
python -m venv .\presentation-service\.venv
.\presentation-service\.venv\Scripts\python.exe -m pip install -r .\presentation-service\requirements.txt
npm install --prefix .\frontend
```

Open five terminals from `demo-application`:

```powershell
# 1. SQLGlot inspection
.\sqlglot-service\.venv\Scripts\python.exe -m uvicorn app:app --app-dir .\sqlglot-service --host 127.0.0.1 --port 8001

# 2. NL-to-SQL (requires an API key in nl-to-sql-service/.env)
.\nl-to-sql-service\.venv\Scripts\python.exe .\nl-to-sql-service\run_server.py

# 3. Navodya PII NER sidecar
.\.ner-venv\Scripts\python.exe .\packages\security-validation-layer\pii_service\ner_service.py

# 4. Node backend
npm start --prefix .\backend

# 5. Vonara intent, presentation and prediction
.\presentation-service\.venv\Scripts\python.exe .\presentation-service\run_server.py
```

Then start the frontend in another terminal:

```powershell
npm run dev --prefix .\frontend
```

Open `http://localhost:3000/#/pipeline`.

## Database selection

MySQL is attempted first using the variables documented in `.env.example`.
For the portable demo, the backend automatically falls back to the bundled
read-only SQLite database if MySQL is unavailable or rejects authentication.
Set `DB_TYPE=sqlite` to select SQLite directly, or `SQLITE_FALLBACK=false` to
require MySQL.

## Main endpoints

- `POST /api/classify-intent`: `{ "nl_query": "..." }` (1-2,000 characters) →
  `{ "nl_query", "intent", "presentation_types", "prediction_needed" }`. Needs no user,
  policy or rules; only `nl_query` is forwarded to the presentation service's
  `/api/v4/classify-intent`. The gateway rejects a response that does not echo
  the question exactly, has an unknown intent, contains unknown or repeated types, or lacks a Boolean
  `prediction_needed` (502). An unreachable classifier returns 503.
- `POST /api/predict-result`: `{ user, policy, resultId, classification }` where
  `classification` is `{ intent, presentation_types, prediction_needed }`.
  Runs only for a forecast request or an `ANOMALY_DETECTION` intent (400
  `PREDICTION_NOT_REQUESTED` otherwise), on the masked result stored for that
  user and policy (404 otherwise). Returns `{ mode, strategy, readiness, model,
  forecast, anomalies, chart, summary }`.
- `POST /api/present-result`: `{ user, policy, resultId, classification }` →
  `{ source, intent, row_count, views: [{ type, label, available, reason, notes, block }] }`.
  Renders only the masked result the gateway stored for that user and policy
  (404 otherwise); rows sent by the browser are ignored. `classification` is
  `{ intent, presentation_types }` from `/api/classify-intent`, or `null` to let
  the data decide. Charts are Vega-Lite v5 specs.
- `POST /api/generate-sql`: generate a SQL draft from the question and pasted
  NL-to-SQL rules for review, without execution. It does not classify or
  analyze the question and returns no classification.
- `POST /api/secure-query`: authoritative generation, validation, policy check,
  optional read-only execution, classification and masking.
- `GET /api/security-health`: database, NER and in-process validation health.
- `GET /api/presentation-health`: Vonara service availability and capabilities.
- `POST /api/simulate`: `{ user, policy, resultId, scenarioText }`, using an authorized
  result held by the gateway, without another SQL execution.
- `POST /api/verify-sql`: compatibility validation endpoint.

The secure response never includes unmasked database rows.

Completed executions also return `presentation`, `presentationStatus`, and a
temporary `resultId` when a question was supplied. The UI renders the response's
declared answer, summary, table and chart blocks, with forecast intervals,
readiness messages, anomalies and numerical claim details. It preserves the
original question when executing edited SQL. Changes to question or identity
invalidate the draft; SQL edits clear previous presentation and scenarios.

If Vonara is unavailable, secure execution still returns the masked table with
`presentationStatus: UNAVAILABLE`. For SQL-only execution, presentation is
skipped. See `.env.example` for service URLs and timeouts; set
`PRESENTATION_ENABLED=false` to disable the optional service.

Generation and execution requests include `{ user, policy, rules }` alongside
the question or SQL. There is no stored-policy fallback when either context
object is missing. Simulation requires the same user and effective policy as
execution. The hiring-trend example can refuse a forecast when history is
insufficient. Analytics require a suitable supplied policy and historical data.

Details and service tests are documented in
[`presentation-service/README.md`](presentation-service/README.md). Run gateway
tests with `npm test --prefix .\backend`, frontend tests with
`npm test --prefix .\frontend`, and build with `npm run build --prefix .\frontend`.
The frontend build preserves existing output files (`emptyOutDir: false`).
With the presentation service running, `npm run test:chart --prefix .\frontend`
also compiles and renders real API forecast/scenario charts to SVG using the
frontend's installed Vega stack and synthetic validation rows, and
`npm run test:forecast --prefix .\frontend` renders the prediction layer's
forecast and anomaly charts, and
`npm run test:render --prefix .\frontend` does the same for every bar, pie and
line chart the data presentation layer returns.

LLM-assisted intent classification is enabled. Configure a Groq API key in
`presentation-service/.env` using that folder's `.env.example`, then restart
the presentation service and gateway. Intent classification always decides with
rules first and asks the LLM only for low-confidence decisions; without a key
those decisions keep the rule answer. To keep classification rules-only, set
`PRESENTATION_LLM_PROVIDER=none` in `presentation-service/.env`. Set
`PRESENTATION_USE_LLM=false` in this folder's `.env` to disable the LLM requests
of the post-execution analysis. Summaries remain deterministic. No key is sent to the
browser, and the NL-to-SQL provider settings remain independent.
