# Integrated Secure NL-to-SQL Demo

This application combines the policy backend, NL-to-SQL service, SQLGlot
inspection service, Navodya's JavaScript security-validation package, PII NER,
and the React demonstration UI.

## Request flow

`frontend -> backend -> NL-to-SQL -> Navodya validation -> SQLGlot policy checks -> read-only database -> PII masking -> frontend`

The frontend calls only the Node backend. The backend reloads the selected demo
user and policy; role, tenant and policy values supplied by the browser are not
trusted by the secure-query endpoint. Tenant AST rewriting is intentionally not
part of this version. Queries missing required tenant/user filters are rejected.

In the pipeline UI, click **Generate SQL** to create a draft, then review or edit
the SQL in step 2. Click **Validate & execute** to run security and policy checks
on that edited SQL before read-only execution and masking. Generation does not
execute the query, and editing SQL clears results from the previous version.

## Start the services

Open four terminals from `demo-application`:

```powershell
# 1. SQLGlot inspection
.\sqlglot-service\.venv\Scripts\python.exe -m uvicorn app:app --app-dir .\sqlglot-service --host 127.0.0.1 --port 8001

# 2. NL-to-SQL (requires an API key in nl-to-sql-service/.env)
.\nl-to-sql-service\.venv\Scripts\python.exe .\nl-to-sql-service\run_server.py

# 3. Navodya PII NER sidecar
.\.ner-venv\Scripts\python.exe .\packages\security-validation-layer\pii_service\ner_service.py

# 4. Node backend
npm start --prefix .\backend
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

- `POST /api/generate-sql`: generate a SQL draft from a question and trusted demo
  user policy for review, without running security inspection or execution.
- `POST /api/secure-query`: authoritative generation, validation, policy check,
  optional read-only execution, classification and masking.
- `GET /api/security-health`: database, NER and in-process validation health.
- `POST /api/verify-sql`: compatibility validation endpoint.

The secure response never includes unmasked database rows.
