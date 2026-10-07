# Stage 8 (part 1) Report — Production Hardening of the Forecasting Layer

7 October 2026 · Wijethunge W M V (IT23256750) · Project J26-SE-347
Branch `vonara-nl-to-sql-prototype-stage-8` (from Stage 7, `1c6a55d`). Nothing committed or pushed.

## Summary

This part of Stage 8 takes the forecasting layer built in Stage 2 (readiness, model choice, forecast ranges, strategies) from a working prototype to something that can run in production. It also re-tests it on a much larger held-out sample.

**What changed for users:**
- A result cut at the security layer's row limit is no longer forecast as if it were complete.
- Ranges never go below zero for a measure that cannot be negative.
- A slow model can no longer block a response.
- The forecast notice says where the horizon came from, and what was adjusted.

**What changed in the forecasts:**
- SARIMA must now beat the simple benchmarks on the series' own history, like every other model. This removes rare but severe failures; on one series SARIMA was 57 times worse than the naive forecast.
- Long histories (48+ points) use fitted smoothing constants.
- An extra refusal applies when a series looks unstable.

**Headline held-out result** (1,000 unseen M4 monthly series, 4,000 forecasts):

| Measure | Result |
| --- | --- |
| 95% range coverage | **94.6%**, the best calibrated of all methods compared (Theta 89.8%, automatic ETS 87.1%) |
| Accuracy vs the naive forecast | MASE 1.458 vs 1.498, sMAPE 9.8% vs 10.4%: better on average, **not significantly** (p = 0.16) |
| Accuracy vs Theta and automatic ETS | **Both are significantly more accurate** (MASE 1.399 and 1.358) |
| Readiness refusals that were right | **0.72** (95% CI 0.67–0.77), recall 0.43. Stage 2's "0.90" was measured on only 20 refusals. |
| Unreliable forecasts shown to users | 8.9% with the gate, against 14.2% without it |

The honest reading: the layer's strengths are **knowing when not to forecast** and **ranges that mean what they say**. Its point forecasts are no better than naive. Standard methods (Theta, ETS) forecast more accurately, though with over-confident ranges. That is the clearest next step (section 7).

## 1. What was done

The work followed the list in the Stage 2 improvement review, limited to the Stage 2 layer.

### 1.1 Production fixes (correctness; no evaluation needed to justify them)

| Fix | Where | Before | After |
| --- | --- | --- | --- |
| **Truncated input** | `prediction.assess_readiness` (new gate 0), `pipeline.py` | Member 2's `truncated: true` was recorded but ignored; a cut-off history could be forecast as READY | Verdict `TRUNCATED` (reason `INPUT_TRUNCATED`): no forecast and no category strategy; the notice asks for a coarser period or shorter range. Configurable. |
| **Input validation** | `input_adapter.py`, `api.py` | Rows without columns became empty rows; a non-numeric `rowCount` crashed; masking naming a missing column passed silently | `INPUT_FORMAT_ERROR` from the API; warnings `INVALID_ROW_COUNT`, `MASKED_COLUMN_NOT_FOUND` |
| **Non-negative ranges** | `prediction.project_series` | A falling count could get "-120 to 900 tickets", or a negative forecast | Clipped at zero when the history is never negative; counted, and disclosed as a notice note |
| **SARIMA time limit** | `prediction._fit_sarima` | A slow fit blocked the response | Fit runs with a time budget (5 s); over it, damped Holt is used and the notice says so |
| **Holiday-aware calendars** | `prediction.prepare_series` | A public holiday counted as a missing trading day | Configured holidays are skipped |
| **Business-day forecast dates** *(bug found)* | `prediction._next_timestamp` | Forecast dates for business-day data could fall on a Saturday or Sunday | Future dates skip weekends and holidays |
| **More than 12 categories** *(bug found)* | `strategies.py` | Categories beyond the top 12 were dropped, so **every share was a share of the wrong total** | The rest are summed into "Other (N more)", which counts in totals but is never named as a leader or mover |
| **Filled-in months in ranges** *(found by the analysis in 3.4)* | `prediction.project_series` | Interpolated months counted as residuals, narrowing the range | Left out of the range's residuals |
| **Forecast notice** | `response_renderer.py`, UI | Did not say where the horizon came from or what was adjusted | `horizon_source`, `horizon_requested` and `notes` (`HORIZON_SHORTENED`, `MODEL_FALLBACK`, `RANGE_CLIPPED_AT_ZERO`), shown in the UI |
| **Policy as configuration** | `forecast_config.json` | Thresholds were constants in code | One versioned file (override with `C4_FORECAST_CONFIG`); every readiness decision records `policy_version` and the `noise_limit` applied; per-granularity noise limits possible |
| **Pinned versions** | `requirements.txt` | No versions at all | Exact versions the numbers were produced with; unused `scikit-learn` removed; missing `httpx` and `openpyxl` added |

### 1.2 Candidate improvements (decided on development data only)

Each candidate was measured on development data (`evaluate_stage8_candidates.py`), with the adoption rule written into the script before the run. The held-out samples were not read. Results: `stage8_candidates.md`.

| Candidate | Development result | Decision |
| --- | --- | --- |
| **E1** SARIMA must also beat naive / seasonal naive (it was exempt "for speed"; a refit actually takes 0.05 s, not 0.3 s) | 36-month: mean MASE 1.329 → 1.323, median 1.210 → 1.211. 72-month: mean 2.073 → 1.425 | **Adopted as a safety fix, overriding its own rule** (see below) |
| **E2** Fitted damped-Holt constants from 48 points | 72-month: mean 2.073 → 1.988, median 1.232 → 1.202 | Adopted |
| **E3** Empirical (quantile) ranges instead of normal | M4 coverage 93.0% → 91.3%: further from 95% | **Rejected** |
| **E4** Also refuse when ADF/KPSS conflict and in-history error > 8% | F1 0.667 → 0.695, precision 0.82, recall 0.55 → 0.61 | Adopted at 0.08 |

**E1 overrode its pre-set rule, and this is stated plainly.** It missed the rule by 0.001 median MASE on 36-month series. But the run showed SARIMA failing catastrophically on 72-month series: MASE 57 on series M36475, and 5–7 on three others. All were caught by the guard. A forecaster that is occasionally 57 times worse than "next month = this month" is a correctness problem, not a tuning trade-off. The override was made before the held-out sample was drawn, so the held-out result tests it independently. E1 and E2 together on 72-month series: mean MASE 2.073 → 1.341, median 1.232 → 1.185.

## 2. Evaluation method

- **New held-out sample, `M4_TEST_LARGE`.** 1,000 monthly M4 series (seed 2028), drawn from the 47,800 not in either earlier sample, with 0 overlap verified. Same 36-month truncation. Drawn **after** every design decision was frozen, and evaluated once.
- **Earlier samples re-run:** SYNTHETIC (66), M4_DEV (100) and M4_TEST (100). M4_TEST was held out in Stage 2 and is no longer unseen.
- **Protocol** as in Stage 2: 4 origins, 3 months apart, 3 months ahead, only past data at each origin; 5,064 windows in total (264 synthetic, 400 M4_DEV, 400 M4_TEST, 4,000 M4_TEST_LARGE).
- **New baselines.** Theta (the M3 winner and an M4 benchmark) and automatic ETS (additive error, trend / damping / seasonality chosen by AICc). Both are from statsmodels with their own 95% intervals, clipped at zero like the deployed layer. Both fitted every window (no fallbacks).
- **Gate ablation:** no gate / Stage 1 rule / Stage 2 noise gate / deployed (noise + conflict), with Wilson 95% CIs on precision.
- **Sensitivity:** noise and conflict limits swept on the held-out data, after the fact; nothing was chosen from it.
- **Missing data** (`evaluate_missing_data.py`, development only): delete 0–50% of history months at random (5 draws per series), refill with the live interpolation, forecast with the deployed selector.

Full tables: `forecast_benchmark.md`.

## 3. Results

### 3.1 Accuracy and calibration, M4_TEST_LARGE (1,000 series)

| Method | MASE mean | MASE median | sMAPE | rel. RMSE vs naive | 95% coverage |
| --- | --- | --- | --- | --- | --- |
| Naive | 1.498 | 1.345 | 10.4% | 1.000 | 95.5% |
| SARIMA (always) | 1.549 | 1.360 | 11.8% | 0.965 | 95.1% |
| Theta | 1.399 | 1.228 | 9.4% | 0.915 | 89.8% |
| Automatic ETS | **1.358** | **1.189** | **9.3%** | **0.900** | 87.1% |
| Adaptive rules, no guard | 1.787 | 1.428 | 12.0% | 1.060 | 93.8% |
| **Deployed (adaptive + guard)** | 1.458 | 1.294 | 9.8% | 0.945 | **94.6%** |

| Paired test (per-series MASE, Wilcoxon) | Deployed better in | p |
| --- | --- | --- |
| vs naive | 360 / 1,000 | 0.16, not significant |
| vs adaptive without guard | 563 / 1,000 | < 0.0001 |
| vs SARIMA always | 559 / 1,000 | < 0.0001 |
| vs Theta | 405 / 1,000 | < 0.0001, **Theta better** |
| vs automatic ETS | 432 / 1,000 | < 0.0001, **ETS better** |

Errors are 2–6% lower than naive at every horizon (MAE ratio 0.98 / 0.94 / 0.94). Per M4 category, the deployed layer beats naive in Demographic, Industry and Macro, and matches it in Finance and Micro.

### 3.2 The readiness gate (ablation)

| Rule | M4_TEST_LARGE refused | Right refusals (95% CI) | Recall | Unreliable among shown |
| --- | --- | --- | --- | --- |
| No gate | 0% | – | 0 | 14.2% |
| Stage 1 CV/R² rule | 0% | – | 0 | 14.2% |
| Noise gate (Stage 2) | 7.4% | 0.76 (0.70–0.80) | 0.40 | 9.3% |
| **Deployed: noise + conflict** | 8.3% | 0.72 (0.67–0.77) | 0.43 | **8.9%** |

- **The gate works:** it cuts the unreliable forecasts users see from 14.2% to 8.9%. The refused forecasts average 37.8% sMAPE, against 7.3% for those shown.
- **Its precision is lower than Stage 2 reported.** Stage 2's 0.90 rested on 20 refusals; on 333 refusals it is 0.72, below the 0.80 the threshold was chosen to meet. The larger sample gives the honest figure.
- **The conflict rule (E4) adds a little:** F1 0.519 → 0.536 and recall 0.40 → 0.43, at a cost in precision (0.76 → 0.72). On the 100-series M4_TEST the same trade is sharper: F1 0.479 → 0.524, precision 0.85 → 0.67. Its benefit is marginal; it stays, because it was chosen on development data, but it is not a strong result.
- **Sensitivity (after the fact):** on M4_TEST_LARGE the F1-best noise limit would have been 0.10 (F1 0.625, refusing 18.6%), not 0.20. The development choice is not optimal for F1 on new data, but it refuses less often, which was the intent.

### 3.3 Readiness correctness (labelled cases)

`evaluate_readiness.py`: **90 / 90** (18 case types × 5 seeds), including the new truncated-result type. 0 false-ready, 0 false refusals, correct reason code 100%.

### 3.4 Missing data (development)

| Months missing | sMAPE change vs complete | 95% coverage before fix | after fix |
| --- | --- | --- | --- |
| 10% | −0.01 pp | 94.3% | 94.2% |
| 25% (current limit) | −0.04 pp | 91.8% | 93.2% |
| 40% | +0.41 pp | 90.5% | 92.7% |
| 50% | +0.68 pp | 87.4% | 90.5% |

- **Accuracy is unaffected up to about 30% missing months.** The 25% refusal limit is therefore safe and slightly cautious.
- **The cost was in the ranges:** filled-in months lie on straight lines and made the range too narrow. That is the fix in 1.1.
- **After the fix, coverage still falls below 95% beyond 25%,** which supports keeping the limit there.

### 3.5 Effect on the rest of the component

| Check | Result |
| --- | --- |
| Python suites (11, including the new `test_production_hardening.py`, 30 checks) | All pass |
| UI tests | 15 / 15 (one new) |
| Integration fixtures (77 questions) | 75 / 77, unchanged (the same two intent disagreements) |
| HTTP rehearsal | 0 contract problems, 0 PII values leaked (7,647 checked) |
| Summary grounding | 100% (415 / 415) |
| Anomaly benchmark, predictive warnings (TEST) | F1 0.487 → 0.492, precision 0.581 → 0.653, normal series falsely warned 6.5% → 2.8%: the guarded forecasts are less erratic |
| Anomaly persistence | shift 81.7% → 82.9%; spikes unchanged |

A visible change in the demo: on "Monthly expenses", SARIMA no longer beats seasonal naive on the series' own history (one-step MAE 2,624 vs 1,676), so the guard now uses seasonal naive.

## 4. Independent labels (prepared, not yet done)

All readiness labels so far were written by the rule author. `independent_labels.py build` produced a kit in `data_and_reports/independent_labelling/`:
- 34 new cases, shuffled, with no answers;
- a blank `labels.csv`;
- plain-language instructions, with no thresholds given.

**A teammate or the supervisor needs to fill it in.** Then `python independent_labels.py score` reports agreement and Cohen's kappa against the classifier.

## 5. Files

| File | Change |
| --- | --- |
| `forecast_config.json` | **New**: readiness and forecasting policy (version `2026-10-07.1`) |
| `prediction.py` | Config loading; truncation gate; per-granularity noise limit; conflict rule; holiday and business-day calendar; non-negative clipping; SARIMA time limit; SARIMA guard; fitted smoothing; filled months out of range residuals; horizon source |
| `input_adapter.py`, `api.py` | Payload validation; `INPUT_FORMAT_ERROR` |
| `pipeline.py` | Passes truncation to readiness; stops strategies on truncated input |
| `strategies.py` | "Other" group; correct shares; per-granularity limit |
| `response_renderer.py` | Notice: `horizon_source`, `horizon_requested`, `notes` |
| `schemas.py` | Readiness verdict `TRUNCATED` |
| `requirements.txt` | Pinned |
| `frontend/src/components/blocks.jsx`, `ui.test.jsx` | Notes and default horizon in the notice; one new test |
| `evaluate_forecasting.py` | Theta and automatic ETS; M4_TEST_LARGE; gate ablation; Wilson CIs; sensitivity; parallel run |
| `evaluate_stage8_candidates.py`, `evaluate_missing_data.py`, `independent_labels.py` | **New** |
| `evaluate_readiness.py` | Truncated-result case type |
| `benchmark_data/prepare_m4_sample.py` | Several `--exclude`, `--ids-from`, `--truncate` |
| `benchmark_data/m4_monthly_test_seed2028_n1000.csv`, `m4_monthly_dev_long72.csv` | **New** samples |
| `test_production_hardening.py` | **New**: 30 checks |
| `data_and_reports/` | This report; `stage8_candidates.md`; `missing_data_sensitivity.md` (+ before-fix copy); re-generated forecast, readiness, anomaly and strategy benchmarks; team contract; labelling kit |

**To reproduce** (deterministic, `LLM_PROVIDER=none`):
- `python evaluate_stage8_candidates.py` (about 3 min)
- `python evaluate_forecasting.py` (about 17 min on 10 cores; `--skip-large` without the 1,000 series)
- `python evaluate_missing_data.py`
- `python evaluate_readiness.py`

## 6. Limitations

1. **Point accuracy is not better than naive** (p = 0.16), and Theta and automatic ETS are significantly more accurate.
2. **Gate precision on new data is 0.72**, below the 0.80 target. The conflict rule's benefit is marginal.
3. **Per-granularity noise limits exist but are all 0.20:** there is no daily or weekly evidence to set them. M4 data here is monthly only.
4. **Still no real business data.** M4 is real but not tenant ERP data, and the readiness labels are not yet independent.
5. **A timed-out SARIMA fit still finishes in a background thread** (Python cannot stop it); only its result is discarded.
6. **Ranges with many filled months** are still slightly narrow (93.2% at 25%).

## 7. Recommended next step

**Add Theta and automatic ETS to the deployed model pool, behind the same guard.** They are the most accurate methods measured here, and the guard keeps them honest. Combined with the layer's range construction, which is better calibrated than theirs, this is the most direct route to accuracy that beats naive. It must be designed on development data and tested on a fresh sample; over 46,800 unused M4 monthly series remain.

The rest of Stage 8 is unchanged:
- intent-informed caching;
- Vega-Lite schema validation;
- the formal intent-to-prediction write-up;
- the final results chapter.
