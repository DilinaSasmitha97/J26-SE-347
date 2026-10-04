# Synthetic MySQL integration tests

Component 4 never writes SQL. It starts when Member 2 hands over masked result
rows. This folder produces realistic rows without waiting on the other
components:

```
fixtures.json (question + hand-written SQL, standing in for Member 1)
      │
      ▼
MySQL c4_synthetic ──► member2_stub.py ──► pipeline.run() ──► checks on what the user sees
                       (read-only, masked,
                        Member 2's exact format)
```

| File | Purpose |
|---|---|
| `schema.sql` | Four tenant-scoped tables of individual transactions |
| `seed.py` | Generates the data from known processes, loads it, writes `output/ground_truth.json` |
| `pii_columns.json` | Declared PII, in Member 2's config format |
| `member2_stub.py` | Runs SQL read-only and returns Member 2's `/api/query` shape |
| `fixtures.json` | 77 cases: question, SQL, expected intent / shape / forecast outcome |
| `run_fixtures.py` | Runs every case end to end and reports per check |

## Tenants

| Tenant | History | Tests |
|---|---|---|
| `tenant_a` | 36 months, trend + seasonality, 2 expense anomalies | SARIMA, seasonal anomalies |
| `tenant_b` | 5 months | readiness gate, short-series forecasting |
| `tenant_c` | 24 months, heavy noise, injected spikes | anomaly detection, volatile data |
| `tenant_d` | 24 months, clean linear growth | linear regression, what-if |

## Running

1. Add to the component's `.env` (git-ignored):
   ```
   MYSQL_ADMIN_USER=root
   MYSQL_ADMIN_PASSWORD=...
   ```
2. `python test_db/seed.py`: creates `c4_synthetic`, loads it, creates the
   SELECT-only `c4_reader` account and verifies the data through it.
   `python test_db/seed.py --check` builds and verifies in memory without MySQL.
3. `python test_db/run_fixtures.py` (add `--only F01 C05`, `--group what-if`
   or `--verbose` to narrow the run).

Results are written to `output/fixture_results.json`.

## What a pass means

The forecast check is about **delivery**. `SHOWN` passes only if the forecast
reaches a rendered block (a chart layer, a table row, a summary sentence or
the answer). `REFUSED` passes only if the user can read the reason. A forecast
that is computed and then dropped by the renderer counts as a failure.

Accuracy metrics (forecast RMSE/MAE, anomaly precision/recall) do not come
from here. Four tenants are far too few series; those come from the large
synthetic and public benchmark sets.
