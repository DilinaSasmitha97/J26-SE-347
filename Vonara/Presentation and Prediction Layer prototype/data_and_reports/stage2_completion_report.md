# Stage 2 Completion Report — Component 4 (Visualization & Prediction Layer)

4 October 2026 · Wijethunge W M V (IT23256750) · Project J26-SE-347

## Summary

Stage 2 is complete. Every prediction-core item is built, tested and measured on a held-out sample of real data. The forecasts are now calibrated, and the readiness check refuses mainly the forecasts that would have been wrong.

Stage 2 set out to turn the Stage 1 prototype's prediction layer into something that can be defended with evidence. The single 3-month holdout on 12 synthetic series was replaced by a rolling-origin benchmark on 266 series. The final test is 100 monthly series from the M4 forecasting competition that no design decision was ever checked against.

Headline results on the held-out M4 sample:

- **Confidence bands:** nominal 95% bands contain **94.5%** of real outcomes (95% / 95% / 94% at 1, 2 and 3 steps ahead).
- **Readiness gate:** refuses 5.0% of forecasts. **90% of its refusals are correct** (target 80%), and the refused forecasts would have been 53.7% wrong on average, against 7.1% for the accepted ones. The old gate refused none.
- **Model selection:** the guarded selector is the most accurate approach on every summary measure (MASE 1.443 vs naive 1.491), but it is **not significantly better than naive** (p = 0.81). It is significantly better than the unguarded rules (p < 0.0001), which on their own are significantly worse than naive (p = 0.001).
- **Strategies:** the three predictive strategies that existed only as labels now run, and each beats or matches the naive answer on its own question.

All Stage 2 changes are in the working tree of branch `vonara-nl-to-sql-prototype-stage-2` and are not committed.

## Starting point

The Stage 1 prototype was a real working system, not a mock, but several of its strongest numbers were not earned:

| What was measured | Stage 1 result | What it actually meant |
| --- | --- | --- |
| Intent accuracy | 100% on 38 cases | Test cases written by the same author as the rules |
| Response-shape accuracy, stress set | 57.8% (26 of 45) | The realistic level on messy input |
| Forecasting | Adaptive selector lost to a fixed weighted moving average on mean RMSE (3,881 vs 3,459) | One 3-month holdout on 12 synthetic series; no naive baseline |
| Readiness gate | Let through a series later forecast with 154% error | The noise rule almost never fired |
| Summary grounding | 100% of 465 numbers traceable | True by construction in deterministic mode |
| Strategies | 4 strategies in the intent-to-prediction map | Only the time-series forecast was ever executed |

The prototype also assumed Member 2 would send a list of row dicts. Member 2's actual code sends rows as arrays with a separate column list, with DECIMAL and DATE values as strings.

## Work completed

1. **Member 2 input adapter** (`input_adapter.py`). Accepts Member 2's real columnar output and the old list-of-dicts format. It renames duplicate columns, records masked columns, flags truncated results, and converts DECIMAL strings to numbers.
2. **Synthetic MySQL test harness** (`test_db/`). A four-tenant transaction schema with ground truth, a stand-in for Member 2 that reproduces its output format and masking, and 77 end-to-end test cases. Written but not yet run against MySQL.
3. **Forecast delivery in every response shape.** A requested forecast reaches the user as a chart, table, summary or single answer, with a `forecast_notice` on every response saying whether it was shown or refused, and why.
4. **Rolling-origin forecasting benchmark** (`evaluate_forecasting.py`). Compares 8 approaches using naive and seasonal-naive baselines, MASE, sMAPE, MAE, RMSE (overall and per step ahead), relative RMSE, Wilcoxon tests, 95% band coverage, and results per data regime. It records the software versions used.
5. **Readiness classifier** (`assess_readiness`):
    1. A three-level decision: READY, READY_WITH_WARNING or NOT_READY, with reason codes.
    2. ADF and KPSS stationarity tests read together.
    3. Unreadable values: more than 20% refuses the forecast.
    4. Empty periods: up to 25% are filled by linear interpolation and disclosed; more refuses. Business-day calendars are recognised, so weekends don't count as gaps.
    5. Near-constant and constant series.
    6. A forecastability test on the series' own history.
6. **Model selection and forecasting fixes:**
    - A benchmark guard: the chosen model must beat naive or seasonal naive on the series' own history, or the baseline is used.
    - Damped-trend Holt smoothing.
    - SARIMA with the airline order, requiring two full seasonal cycles, with residual-based bands.
7. **The three missing strategies** (`strategies.py`): category trajectory, distribution shift and anomaly persistence. This item also added result layouts, so grouped results are forecast per category instead of as one mixed series.
8. **Readiness-correctness benchmark** (`evaluate_readiness.py`): 85 labelled result sets with known correct decisions.

## Problems solved

Thirteen defects were fixed, five of them found only because Stage 2 tested with realistic data shapes.

| Problem | Cause | Fix | Evidence |
| --- | --- | --- | --- |
| Integration with Member 2 would have turned every chart and forecast into a plain table | Member 2 sends array rows; the contract assumed dicts | Input adapter accepting both formats | Identical forecast and summary from both formats |
| A total like 48,250.50 shown as raw text "48250.50" without its "Sum of" label | DECIMAL arrives as a string | Measure columns converted to numbers after profiling | Regression test on the answer block |
| The adapter's own first draft could overwrite a real column when renaming duplicates | Rename did not reserve existing names | All original names reserved first | Caught by the adapter test, then fixed |
| Requested forecasts silently dropped in table, summary and single-answer responses | Only the chart could display a forecast | Forecast rows, forecast-first summaries, forecast answers, `forecast_notice` | Every shape × shown / refused / not asked |
| Readiness gate refused 0 of 1,064 forecasts, including ones later 154% wrong | Coefficient-of-variation rule almost never fired | Forecastability test on the series' own history | Held-out refusals 90% correct |
| Rule-based selection worse than naive on real data | Rules defaulted to undamped Holt, which projects noise as trend | Benchmark guard + damped-trend Holt | Guarded significantly better than unguarded (p < 0.0001) |
| SARIMA forecasts exploded (mean MASE 7.04; hundreds of millions on short history) | A four-parameter seasonal order on 24–36 points | Airline order, two full cycles required | SARIMA MASE 1.52 on held-out M4 |
| SARIMA's 95% bands held only 67% of outcomes | statsmodels intervals treat estimated parameters as exact | Residual-based bands like every other model | 95.0% on held-out M4 |
| "Revenue by month and region" analysed as one interleaved series | No notion of grouped results | Result layouts; one forecast and summary per category | Pipeline tests on grouped data |
| Summary sentences said "per period" and "changed from X to Y" for non-time data, and read rows in query order | Claims assumed one row per period in date order | Layout-aware, chronological claims | No mixed-series sentences in the grouped test |
| Sparse monthly data read as quarterly | Granularity taken from the median gap | Granularity from the shorter gaps | Sparse monthly case refused with the correct reason |
| Gaps and missing values ignored by readiness | Detected but never used | Completeness checks with disclosed interpolation | 85/85 labelled readiness cases |
| Three strategies existed only as labels | Never implemented | `strategies.py` | Strategy benchmark against naive answers |

## Evaluation method

The forecasting models were evaluated on 266 time series:

| Group | Series | Role |
| --- | --- | --- |
| Synthetic | 66: factorial grid of 2 lengths × 5 noise levels × seasonal or not × 3 trends, plus 6 near-constant | Development |
| M4_DEV | 100 monthly series randomly sampled (seed 2026) from the M4 competition dataset (100,000 series in total; 48,000 monthly) | Development |
| M4_TEST | 100 further monthly series (seed 2027) drawn from the 47,900 not in M4_DEV | Held-out test, evaluated once |

- **Truncation:** every M4 series is its official train and test values joined, then cut to the last 36 observations, to match the 12–36 month histories of small business data.
- **Rolling origin:** 4 forecast origins per series, 3 months apart, each forecasting 3 months ahead. Every forecast uses only data before its origin.
- **Approaches:** six fixed models (naive, seasonal naive, weighted moving average, linear regression, damped Holt, SARIMA), plus the adaptive selector with and without the benchmark guard. All use the same code path as live requests.
- **Metrics:** MASE (errors scaled by the in-sample one-step naive error), sMAPE, MAE, RMSE, relative RMSE against naive, overall and per step ahead; share of outcomes inside the 95% band; results per data regime; Wilcoxon signed-rank tests on per-series MASE.
- **Gate threshold:** a forecast window counts as unreliable when its sMAPE exceeds 20%. The threshold is chosen on development data as the best F1 among thresholds whose refusals are right at least 80% of the time. It came out at 20% of the series level.
- **Held-out discipline:** M4_DEV was the held-out test of the first Stage 2 run. Once seen, it became development data, and the SARIMA order, the band method and the gate threshold were all checked against it. M4_TEST was drawn afterwards, disjoint from M4_DEV, and evaluated once with the frozen code.
- **Readiness correctness:** 85 result sets (17 case types × 5 seeds), each with a correct decision fixed by how it was generated.
- **Environment:** Python 3.13.14, NumPy 2.5.1, SciPy 1.18.0, statsmodels 0.14.6.

## Results

**Forecast accuracy on held-out M4_TEST:**

| Approach | MASE mean / median | sMAPE | rel. RMSE vs naive | 95% coverage (h = 1 / 2 / 3) |
| --- | --- | --- | --- | --- |
| Naive | 1.491 / 1.231 | 10.8% | 1.000 | 95.0% (96 / 95 / 94) |
| SARIMA (airline) | 1.521 / 1.295 | 11.1% | 0.965 | 95.0% (95 / 95 / 95) |
| Adaptive, no guard | 1.897 / 1.356 | 11.2% | 1.070 | 92.7% (90 / 94 / 94) |
| **Adaptive + guard** | **1.443 / 1.234** | **9.5%** | **0.938** | **94.5%** (95 / 95 / 94) |

**Per step ahead (held-out M4_TEST, adaptive + guard against naive):**

| Step ahead | MASE (guard / naive) | MAE vs naive | RMSE vs naive |
| --- | --- | --- | --- |
| 1 | 1.049 / 1.065 | 0.928 | 0.915 |
| 2 | 1.466 / 1.520 | 0.927 | 0.923 |
| 3 | 1.815 / 1.887 | 0.920 | 0.912 |

The guarded selector's errors are 7–9% lower than naive at every horizon. The Wilcoxon test on per-series MASE still finds no significant difference (p = 0.81), because the gain is spread unevenly across series.

**Per data regime (synthetic, mean MASE):** the guarded selector beats naive in 7 of 8 regimes (long, short, low noise, medium noise, seasonal, trend-dominant, volatile). It loses on near-constant series (1.045 vs 1.002), where there's nothing to forecast. On M4_TEST it beats naive on Industry and Macro series and is within 0.06 on the rest.

**SARIMA order choice (development data):** airline (0,1,1)(0,1,1) mean MASE 1.69; per-series AICc selection 2.03; the Stage 1 order (1,1,1)(1,1,1) 7.04 with 12 forecast blow-ups.

**Readiness:**

| Measure | Result |
| --- | --- |
| Gate refusals on held-out M4_TEST | 5.0%; precision 0.90; recall 0.35 |
| sMAPE of accepted vs refused forecasts (M4_TEST) | 7.1% vs 53.7% |
| Old CV/R² rule, all groups | 0 refusals |
| Labelled readiness cases (17 types × 5 seeds) | 85/85 correct; 0 false-ready; 0 false refusals; correct reason code 100% |
| Unreliable forecasts when ADF and KPSS disagree (M4_TEST) | 29.0%, against 7.5–15.5% for the other verdicts |

The labelled cases are clear-cut by construction, so 85/85 shows the policy is implemented correctly. The gate's precision on M4 is the evidence on borderline data.

**Strategies (synthetic data, known truth):**

| Question | Strategy | Naive answer |
| --- | --- | --- |
| Leader next period (200 sets of 4 categories) | 90.0% | 88.0% (current leader stays) |
| Leader next period, the 24 sets where it changes | 29.2% | 0% |
| Leader, when the strategy calls the lead clear (88 sets) | 100% | — |
| Share error next period | 1.62 pp (p = 0.003) | 1.74 pp (shares persist) |
| Anomaly persistence verdict (169 detected events) | 71.6% | 52.7% (best constant answer) |
| Anomaly persistence: one-off spikes / level shifts | 59.8% / 84.1% | — |

## Open issues and limitations

Stage 2 is complete. These limits are documented and carried forward:

1. **Selection matches naive but doesn't beat it significantly** (p = 0.81 on held-out data). In-history validation over all candidate models is the natural next design to test.
2. **Gate recall is modest:** it catches 35% of unreliable forecasts. The threshold deliberately favours precision, because a refusal withholds an answer from the user.
3. **Anomaly persistence on one-off spikes:** 59.8% correct. This belongs to Stage 3 (anomaly engine).
4. **Not yet integrated:** the MySQL test harness has never run against MySQL, and response-shape classification still answers "How much will I spend next month?" with a table rather than a single value. These belong to later stages.

**Limits of the evidence:**
- The strategy results come from synthetic data only.
- The M4 samples are 100 series each, truncated to 36 months.
- The stationarity caution is supported on M4_TEST but not on the synthetic data, where disagreement predicted nothing.

## Files, tests and reproduction

All changes are in `Vonara/Presentation and Prediction Layer prototype/` and are uncommitted.

| File | Change |
| --- | --- |
| `input_adapter.py` | New: Member 2 columnar result → row dicts |
| `strategies.py` | New: Stage 1 strategy execution |
| `evaluate_forecasting.py` | New: rolling-origin benchmark, gate evaluation, per-horizon and per-regime results |
| `evaluate_strategies.py` | New: strategy benchmark against naive answers |
| `evaluate_readiness.py` | New: readiness-decision benchmark on labelled cases |
| `benchmark_data/` | New: M4 development and held-out samples, rebuild script, provenance note |
| `test_db/` | New: synthetic MySQL schema, seeder, Member 2 stand-in, 77 fixtures, runner |
| `prediction.py` | Shared `project_series`, naive models, three-level readiness, ADF + KPSS, series preparation, forecastability gate, benchmark guard, damped Holt, airline SARIMA with residual bands |
| `result_profiler.py` | Result layouts, grouped series, DECIMAL conversion, robust granularity |
| `summarization.py` | Layout-aware claims, strategy claims, condensed forecast claim, readiness caution claim |
| `response_renderer.py` | Forecast, strategy and caution delivery in every response shape |
| `visualization.py` | Chart rule R5: per-category forecast lines and bands |
| `pipeline.py`, `api.py`, `schemas.py` | Wiring, `member2_result` API field, new verdicts and models |
| `evaluate.py`, `test_component.py`, `test_*.py` | Updated and new tests |
| `data_and_reports/` | README, roadmap, team contract and this report; generated benchmark reports |

**Test status:** all seven suites pass:
- `test_component.py`
- `test_input_adapter.py`
- `test_forecast_delivery.py`
- `test_strategies.py`
- `test_readiness.py` (23 checks)
- `test_response_intent.py` (93 checks)
- the in-memory check of `test_db/seed.py`

**To reproduce every number** (deterministic, fixed seeds, `LLM_PROVIDER=none`):

1. `python evaluate_forecasting.py` writes `forecast_benchmark.md` and its JSON (about 1 minute).
2. `python evaluate_readiness.py` writes `readiness_benchmark.md` and its JSON.
3. `python evaluate_strategies.py` writes `strategy_benchmark.md` and its JSON.
4. To rebuild the M4 samples from the official files (download them into `benchmark_data/m4_raw/` first):
   - `python benchmark_data/prepare_m4_sample.py` (development, seed 2026)
   - `python benchmark_data/prepare_m4_sample.py --seed 2027 --exclude benchmark_data/m4_monthly_sample.csv --out benchmark_data/m4_monthly_test_seed2027.csv` (held-out test)

## Next steps

- [ ] Stage 3: anomaly engine. Seasonal detection with STL (current seasonal recall is 0) and separating one-off spikes from level shifts.
- [ ] Stage 4: what-if parser fix ("unless" read as a decrease) and LLM narration under the verifier, measuring how often invented numbers are rejected.
- [ ] Stage 5: intent classification on a blind test set labelled by someone else.
- [ ] Stage 6: integration. Run the MySQL harness, then connect to Members 1–3.
- [ ] Stage 7: React interface for charts, what-if and the claim trace.
- [ ] Stage 8: final evaluation and results chapter.
