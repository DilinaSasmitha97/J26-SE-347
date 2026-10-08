# Integrated Secure NL-to-SQL Demo

This application combines the policy backend, NL-to-SQL service, SQLGlot
inspection service, Navodya's JavaScript security-validation package, PII NER,
Vonara's presentation/prediction service, and the React demonstration UI.

## Request flow

`frontend -> backend -> Vonara intent analysis -> NL-to-SQL -> Navodya validation -> SQLGlot policy checks -> read-only database -> PII masking -> Vonara presentation/prediction -> frontend`

The frontend calls only the Node backend. User policy, Authenticated user and
NL-to-SQL rules start empty and remain editable. Paste or upload your own JSON;
the application does not load stored demo users or role policy files. Reset
clears those fields. User and policy are required; extra NL-to-SQL rules are
optional. User JSON must include `userId` and `role`. Policy JSON must include
`allowedTables`; its `valueFrom` filters resolve against the supplied user claims.
The gateway uses this manual context for generation, checks, masking and scenarios.
This console treats the operator's inputs as demo context, without authenticating
those claims. Tenant AST rewriting is intentionally not part of this version.
Queries missing the supplied policy's required tenant/user filters are rejected.

The gateway sends exactly two fields to the NL-to-SQL service: `user_query`
(the question) and `injected_rules` (your pasted rules JSON object, or `null`).
It does not append user-policy constraints or Vonara analysis hints. The SQL
service formats the provided JSON for its model prompt and generates its own
schema, entity and relationship hints internally. The submitted rules appear
under the SQL draft without overwriting your editors. Editing any context field
invalidates the draft. User policy is applied during SQL validation and execution.

In the pipeline UI, click **Generate SQL** to create a draft, then review or edit
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

- `POST /api/generate-sql`: generate a SQL draft from the question and pasted
  NL-to-SQL rules for review, without execution. Returns
  `analysis` and `analysisStatus`; questions identified as non-data requests are
  rejected before generation. If analysis is unavailable, policy-grounded SQL
  generation from the question and pasted rules remains available.
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
frontend's installed Vega stack and synthetic validation rows.

LLM-assisted intent classification is enabled. Configure a Groq API key in
`presentation-service/.env` using that folder's `.env.example`, then restart
the presentation service and gateway. Until a key is configured, classification
falls back to rules. Set `PRESENTATION_USE_LLM=false` in this folder's `.env` to
disable the LLM requests. Summaries remain deterministic. No key is sent to the
browser, and the NL-to-SQL provider settings remain independent.
