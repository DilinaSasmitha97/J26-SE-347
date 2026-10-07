# Stage 6 Completion Report — Component 4 (Visualization & Prediction Layer)

5 October 2026 · Wijethunge W M V (IT23256750) · Project J26-SE-347

## Summary

Stage 6 was planned as integration with the other members' components. There is no shared database yet and no team service is running, so Stage 6 became an **integration rehearsal**. The whole chain ran on this machine:

- **Member 1:** stand-ins built to its contract.
- **Member 2:** stand-ins built to its real output format, including PII masking.
- **Member 3:** a stand-in security context.
- **This component:** called through its real HTTP API.

When the team is ready, connecting means replacing the stand-ins with the real services. The formats and behaviour on this side are already tested.

What the rehearsal showed:

- **The chain works end to end.**
  - All 77 integration questions ran through the real database path, the Member 2 stand-in and the API.
  - **0** contract fields were missing or mistyped.
  - **0** unmasked PII values appeared in any response, checked against all 7,647 names, emails and phone numbers in the database.
  - Denied tables were never bound, and no cached answer crossed a tenant boundary.
- **It found real bugs that the unit tests never could.** Fully passing questions went from **64 to 75 of 77** after the fixes.
  - Distribution and correlation questions could never get a chart.
  - A total per vendor for 15 vendors was treated as a list of keys.
  - "Without a forecast" *produced* a forecast.
  - With the LLM on, the LLM could switch a declined forecast back on.
- **Four fixes were carried over from earlier stages:**
  - the LLM is now off by default, matching the documented design
  - the LLM may only override a *weak* rule intent
  - "per" no longer matches "percent"
  - a caution for a possibly incomplete first or last period
- **Speed:** analysis takes a median of 10 ms; a full presentation takes a median of 16 ms (95th percentile 85 ms).

All Stage 6 work is in the working tree of branch `vonara-nl-to-sql-prototype-stage-6`, which contains Stages 1–5. Nothing has been committed or pushed, and `main` is untouched.

## Starting point

| What existed | State before Stage 6 |
| --- | --- |
| Test database harness (`test_db/`): schema, data generator with ground truth, Member 2 stand-in, 77 integration questions | Written in Stage 2, **never run**: it required a MySQL server and password |
| Member 2's format and masking | Unit-tested with hand-made payloads only |
| HTTP API | Never exercised end to end with realistic payloads |
| Known open bugs | "No forecast" read as a forecast request; LLM on by default despite the docs; LLM overriding confident rule intents; "per" matching "percent" |

## Work completed

1. **SQLite backend** (`test_db/db_config.py`, `test_db/sqlite_mysql.py`, `test_db/seed.py`).
   - **No database server needed.** SQLite is built into Python, so the harness runs with no server and no password. `DB_BACKEND=mysql` still selects MySQL.
   - **The MySQL fixture SQL runs unchanged.** MySQL's functions are registered in SQLite (`DATE_FORMAT`, `YEAR`, `QUARTER`, `WEEKDAY`, `CONCAT`, …) and `DATE_SUB(x, INTERVAL n UNIT)` is rewritten.
   - **PII masking keeps working.** Member 2's declared-PII masking needs each result column's source table and column, which MySQL's driver reports and SQLite's does not. These are worked out from the SQL instead: a plain column has a source, an expression does not, as in MySQL. Without this, nothing would have been masked, and every test would still have passed.
   - **Verified load.** 10,759 rows across 4 tenants. Every monthly total matches the ground truth to the cent, and the read-only connection refuses writes.
2. **End-to-end run of the 77 integration questions** (`run_fixtures.py`). This was its first run since it was written in Stage 2.
3. **HTTP rehearsal** (`test_db/run_api_rehearsal.py`). All 77 questions go through `/api/v4/analyze` and `/api/v4/present`, with `/api/v4/simulate` for the what-if cases. It checks:
   - **Contract:** every field `team_interface_contract.md` promises a consumer is present, with the right type and an allowed value.
   - **Privacy:** no unmasked PII value appears anywhere in the returned JSON.
   - **Denylist:** a denied table is never bound.
   - **Tenant isolation:** the same question and rows for another tenant get no cache hit.
   - **Latency.**
4. **Fixes found by the run:**

   | Problem | Cause | Fix |
   | --- | --- | --- |
   | Distribution and correlation questions always became tables (D01–D03, K01) | Guardrail G2 demanded a time or category axis; a histogram needs one measure and a scatter plot two | G2 accepts both; the chart builder already drew them |
   | A total per vendor for 15 vendors had no axis to chart (P04) | A text column unique on every row counted as a key once there were more than 12 groups, although GROUP BY makes it unique by construction | A result of exactly one text column beside measures is a grouping, up to 30 categories, unless the name looks like a key |
   | "Show yearly expenses", "List revenue by month" got no trend (T05, T07) | "yearly", "by month" and similar were not trend words | Added |
   | "The monthly count of …" became a table via a single answer (T09) | "monthly" was not a series cue | Weak chart cue, plus a single-answer veto unless something asks for an extreme ("the all-time high for daily signups", "the average monthly spend" stay one figure) |
   | "Briefly summarise … and forecast …" became a full report (F10) | "briefly" was not a brevity word, and a Stage 5 change made "forecast" a second format | "briefly" recognised; a brevity word keeps the mixed report below the summary |
   | "What percentage of spend goes to each vendor" | "percentage of" had no chart cue | Added |
   | Two forecast expectations failed (F07, F16) | The readiness gate refused them: expected error 23% and 41% of level, limit 20% | Expectations corrected with the evidence written into the fixture. The gate is right; see point 6 for F07 |

5. **Pending fixes from earlier stages:**
   - **Forecast opt-out.**
     - "Without a forecast" and "no predictions please" now set the trigger to `DECLINED`.
     - No forecast is produced, including the automatic one for trend questions.
     - The LLM cannot switch it back on. The first version of this fix still let the merge step OR the LLM's forecast flag back in; the new offline test caught that, and it was fixed.
   - **LLM off by default.** `use_llm` now defaults to false in `pipeline.run`, `analyze_only`, `query_analyzer.analyze` and both API request models, as the roadmap always said. Before, a configured key sent every question and the schema to the provider.
   - **LLM intent override.** The LLM may override the rules' analytical intent only when the rule verdict is weak (confidence below 0.55, or UNKNOWN). The response shape already worked this way.
   - **"per".** It no longer matches inside "percent" or "period". The Stage 5 version was undone by a `strip()` in the marker matcher.
6. **Partial first or last period** (`PARTIAL_EDGE_PERIOD`). F07's first "week" held 3 tickets against a typical 31, because the data starts mid-week; its last week was partial too. With live data, "this month so far" is always partial. An edge period below 40% of the median now adds a readiness caution. Nothing is dropped, because a genuine collapse looks the same. On 200 complete real M4 series it fires on 6 (3%).
7. **Tests.** `test_integration.py` has 29 checks covering MySQL compatibility, the Member 2 stand-in, the forecast opt-out, LLM defaults and policy, charts and profiling, and the shape fixes.

## Results

### Integration questions (`test_db/run_fixtures.py`, 77 cases)

| Check | First run | After fixes |
| --- | --- | --- |
| Ran without error | 77 / 77 | 77 / 77 |
| Analytical intent | 73 / 77 | 75 / 77 |
| Response shape | 65 / 73 | **73 / 73** |
| Forecast delivered as expected | 57 / 59 | **59 / 59** |
| Warnings, what-if | 9 / 9, 3 / 3 | 9 / 9, 3 / 3 |
| **Fully passing questions** | **64 / 77** | **75 / 77** |

The two remaining intent disagreements have the right answer shape:
- "the 10 most recent expenses": a ranking, or a lookup?
- "how sales did this year": a trend, or a lookup?

**Anomalies against injected ground truth** (data aggregated back from individual transactions): 3 of 6 injected anomalies found, with 3 false alarms. That's consistent with the precision cost reported in Stage 3.

### HTTP rehearsal (`integration_rehearsal.md`)

| Check | Result |
| --- | --- |
| HTTP calls failing | 0 |
| Contract fields missing or mistyped (77 analyze + 77 present) | **0** |
| Unmasked PII values in any response (7,647 distinct values checked) | **0** |
| Denied table bound in the analysis | never |
| Cache hit across tenants (A, A, B) | False, True, False — isolated |

**Latency:**

| Endpoint | Median | 95th percentile | Max |
| --- | --- | --- | --- |
| `/api/v4/analyze` | 10 ms | 16 ms | 31 ms |
| `/api/v4/present` | 16 ms | 85 ms | 135 ms |
| `/api/v4/simulate` | 29 ms | 70 ms | 70 ms |

These were measured in-process with the LLM off. They exclude network time and the other members' components.

### LLM intent override policy (60 Spider TEST questions, Groq)

The same 60 questions as the Stage 5 comparison, re-run with the Stage 6 code:

| Path | Stage 5 shape / intent | Stage 6 shape / intent |
| --- | --- | --- |
| Rules only | 93.3% / 91.7% | **95.0% / 93.3%** |
| Rules + LLM | 98.3% / 81.7% | 95.0% / 88.3% |

- **The new policy halves the damage the LLM did to intent.** It is now 5.0 points below the rules instead of 10.0, because the LLM may no longer override a confident rule verdict.
- **The LLM's earlier gain on shape is gone.** In Stage 5 the LLM's intent fed the shape decision when the shape rules were unsure; it no longer does.
- **The LLM does not beat the rules on either measure**, so keeping it off by default is supported by the evidence.
- **Caveats:**
  - 60 questions, so a 3-question difference is 5 points; none of these differences is significant.
  - About 4 of the 60 LLM calls failed with connection errors and fell back to the rules (2 in Stage 5).
  - These 60 questions were also used in Stage 5, so this is a before/after comparison, not a held-out result.

On all 501 TEST questions (rules only), Stage 6 moves the Stage 5 figures slightly:
- **Shape:** 89.0% → 89.8%.
- **Intent:** 88.2% → 88.6%.
- **Rows lost to `LIMIT 1`:** 5.8% → 5.4%.

TEST was seen in Stage 5, so these are regression figures, not new held-out results.

### Regression

- **Test suites:** all 10 pass.

  | Suite | Checks |
  | --- | --- |
  | test_integration | 29 |
  | test_intent | 21 |
  | test_whatif | 30 |
  | test_anomaly | 19 |
  | test_component | 61 |
  | test_strategies | 24 |
  | test_forecast_delivery | 42 |
  | test_readiness | 23 |
  | test_input_adapter | 27 |
  | test_response_intent | passes |
- **Author-written sets:** intent 48/48, response shape 125/125 and 50/50, stress 42/45.
- **Spider DEV:** shape 90.0%, intent 92.8% (from 92.3%, because of the "per" fix).
- **Other stages unchanged:** readiness 85/85, what-if 94/94, summary grounding 100%.

## What this means for the component

- **The component is integration-ready on its side.** Its input handling, its output contract, PII safety, tenant isolation and the denylist were all checked at the API boundary, with formats taken from the teammates' real code. What remains is the other side: the real services and a shared database.
- **Running the real chain was worth it.**
  - The end-to-end run found **seven defects** that the existing unit tests had missed: histograms and scatter plots blocked, wide grouped results read as keys, missing trend words, monthly series, "briefly", "percentage of", and partial edge periods.
  - The new offline test found an eighth defect, in the Stage 6 fix itself: the LLM could re-enable a declined forecast.
- **Privacy:** the zero-leak result depends on Member 2 masking correctly. This component never sees unmasked values, so it can't leak them. The check proves it doesn't *re-introduce* any, through summaries, labels, caching or errors.

## Limitations and open issues

1. **Stand-ins, not teammates.**
   - The SQL is hand-written, not generated by Member 1.
   - Masking is the declared-PII path of Member 2's design only. Their NER-based detection is not reproduced, so an expression such as `CONCAT(full_name, …)` is not masked here, exactly as in Member 2's declared path.
   - The security context is a fixture.
2. **Undecided database.** Member 2's executor uses MySQL, while Member 1's schema cache is SQL Server (NemsuERPNew, 421 tables). The team needs to settle this. The harness runs either SQLite or MySQL.
3. **Small, synthetic data.** Four tenants and 77 questions test delivery and contracts, not accuracy. Accuracy comes from the Stage 2–5 benchmarks.
4. **The partial-period caution is a heuristic.** It flags 3% of complete real series, and it cannot tell a partial period from a genuine collapse, so it only warns.
5. **`normalized_query`** (the LLM's cleaned-up question) is still not offered to Member 1. Agree that with them before building it.
6. **Not run:** the forecasting and anomaly benchmarks. Their models were not changed. The readiness gate gained a caution only, and the readiness benchmark was re-run.

## Files

| File | Change |
| --- | --- |
| `test_db/sqlite_mysql.py` | New: MySQL compatibility, column sources, mysql2 value format |
| `test_db/db_config.py` | `DB_BACKEND` (SQLite default), read-only SQLite connection |
| `test_db/member2_stub.py` | SQLite execution path, same output shape |
| `test_db/seed.py` | SQLite loader and read-only verification |
| `test_db/run_api_rehearsal.py` | New: HTTP rehearsal (contract, privacy, denylist, tenant, latency) |
| `test_db/fixtures.json` | F07 and F16 expectations corrected, with the evidence |
| `test_db/README.md` | SQLite instructions |
| `query_analyzer.py` | Trend words, `per`, `DECLINED` opt-out, LLM override policy, LLM default off |
| `response_intent.py` | G2 histogram / scatter, period-word cue, `briefly`, `percentage of` |
| `result_profiler.py` | Wide grouped results recognised as categories |
| `prediction.py` | `PARTIAL_EDGE_PERIOD` caution |
| `pipeline.py`, `api.py`, `prompts.py` | Analytic intent passed to guardrails; LLM defaults off; `DECLINED` documented |
| `test_integration.py` | New: 29 checks |
| `data_and_reports/` | Rehearsal report, README, roadmap, team contract, this report |

**To reproduce** (nothing to install):
- `python test_db/seed.py`
- `python test_db/run_fixtures.py`
- `python test_db/run_api_rehearsal.py`
- `python test_integration.py`

## Next stage

Stage 7 is the React frontend, which renders the component's output:
- the Vega-Lite charts, forecast bands and anomaly markers
- the answer, table and summary blocks
- the what-if control
- the "show the working" claim trace

It needs no teammates. The live connection to the team (Phase 3 in the roadmap) can happen whenever their services are ready.
