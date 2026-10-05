# Synthetic integration tests (SQLite by default, MySQL optional)

Component 4 never writes SQL. It starts when Member 2 hands over masked result
rows. This folder produces realistic rows without waiting on the other
components:

```
fixtures.json (question + hand-written SQL, standing in for Member 1)
      │
      ▼
SQLite / MySQL      ──► member2_stub.py ──► pipeline.run() or ──► checks on what the user sees
c4_synthetic            (read-only, masked,  the HTTP API
                         Member 2's exact format)
```

Since Stage 6 the database is a **SQLite file** by default
(`output/c4_synthetic.sqlite`): built into Python, no server, no password.
The fixture SQL stays in MySQL, the dialect Member 2's executor runs:
`sqlite_mysql.py` registers MySQL's functions (`DATE_FORMAT`, `YEAR`,
`QUARTER`, `WEEKDAY`, `CONCAT`, ...) and rewrites `DATE_SUB(x, INTERVAL n
UNIT)`. Because SQLite's driver does not report a result column's source table
and column (MySQL's does, and Member 2's declared-PII masking depends on it),
`sqlite_mysql.column_sources` works them out from the SQL: a plain column has
a source, an expression does not, exactly as in MySQL. Set `DB_BACKEND=mysql`
in `.env` to use MySQL instead.

| File | Purpose |
|---|---|
| `schema.sql` | Four tenant-scoped tables of individual transactions |
| `seed.py` | Generates the data from known processes, loads it, writes `output/ground_truth.json` |
| `pii_columns.json` | Declared PII, in Member 2's config format |
| `member2_stub.py` | Runs SQL read-only and returns Member 2's `/api/query` shape |
| `fixtures.json` | 77 cases: question, SQL, expected intent / shape / forecast outcome |
| `run_fixtures.py` | Runs every case end to end through `pipeline.run` and reports per check |
| `run_api_rehearsal.py` | Runs every case through the HTTP API and checks the contract, PII leakage, the table denylist, tenant cache isolation and latency |
| `db_config.py`, `sqlite_mysql.py` | Backend selection (`DB_BACKEND`), SQLite connection with MySQL compatibility |

## Tenants

| Tenant | History | Tests |
|---|---|---|
| `tenant_a` | 36 months, trend + seasonality, 2 expense anomalies | SARIMA, seasonal anomalies |
| `tenant_b` | 5 months | readiness gate, short-series forecasting |
| `tenant_c` | 24 months, heavy noise, injected spikes | anomaly detection, volatile data |
| `tenant_d` | 24 months, clean linear growth | linear regression, what-if |

## Running

SQLite (default, nothing to install):

1. `python test_db/seed.py`: builds `output/c4_synthetic.sqlite` and verifies
   every monthly total against the ground truth through a read-only connection
   (and that the connection cannot write).
2. `python test_db/run_fixtures.py` (add `--only F01 C05`, `--group what-if`
   or `--verbose` to narrow the run). Results: `output/fixture_results.json`.
3. `python test_db/run_api_rehearsal.py`: the same cases over HTTP. Results:
   `data_and_reports/integration_rehearsal.md`.

MySQL (optional): add `DB_BACKEND=mysql`, `MYSQL_ADMIN_USER` and
`MYSQL_ADMIN_PASSWORD` to the component's `.env` (git-ignored); `seed.py` then
creates `c4_synthetic`, the SELECT-only `c4_reader` account, and verifies
through it. `python test_db/seed.py --check` builds and verifies in memory
only.

## What a pass means

The forecast check is about **delivery**. `SHOWN` passes only if the forecast
reaches a rendered block (a chart layer, a table row, a summary sentence or
the answer). `REFUSED` passes only if the user can read the reason. A forecast
that is computed and then dropped by the renderer counts as a failure.

Accuracy metrics (forecast RMSE/MAE, anomaly precision/recall) do not come
from here. Four tenants are far too few series; those come from the large
synthetic and public benchmark sets.
