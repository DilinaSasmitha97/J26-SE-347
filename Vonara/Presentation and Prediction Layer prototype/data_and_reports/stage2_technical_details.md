# Stage 2 — Technical Details: Data Readiness and Trustworthy Forecasting

**Component 4 · Presentation & Prediction Layer · Wijethunge W M V (IT23256750) · J26-SE-347**
Branch `vonara-nl-to-sql-prototype-stage-2`, commit `3afbffc`. Full results: `stage2_completion_report.md`.

---

## 1. Purpose

Stage 1 produced a working forecast for every time series it received. Stage 2 makes that forecast defensible:

1. **Decide whether a forecast should be made at all** (data readiness classifier).
2. **Choose a model that is never worse than a trivial forecast** on the series' own history (benchmark guard).
3. **Make the 95% ranges honest** (calibrated intervals).
4. **Deliver a requested forecast in every response shape**, with a stated outcome (`forecast_notice`).
5. **Accept Member 2's real output format** (input adapter).
6. **Execute the three prediction strategies** that were only labels in Stage 1.
7. **Prove all of it** on held-out real data (M4) and labelled cases.

---

## 2. Where Stage 2 sits in the pipeline

Within the prediction part of the pipeline (`pipeline.py`), Stage 2 work touches every step marked ★:

```
Member 2 payload
   │
   ▼
★ input_adapter.adapt_result()        columnar → row dicts, masking, truncation
   │
   ▼
  query_analyzer  →  result_profiler ★ (layouts, DECIMAL conversion, granularity)
   │
   ▼
  prediction.map_intent_to_strategy()        pipeline step "Stage 1 Intent Mapping"
   │
   ▼
★ prediction.assess_readiness()              pipeline step "Stage 2 Readiness"
   │        READY / READY_WITH_WARNING / NOT_READY
   ▼
★ prediction.select_model()                  pipeline step "Stage 3 Model Selection"
   │        rules → benchmark guard
   ▼
★ prediction.generate_forecast()             pipeline step "Stage 4 Forecast"
   │        → project_series(): fit + calibrated bands
   ▼
  anomaly.detect_anomalies()                 (Stage 3 of development)
   │
   ▼
★ strategies.execute_strategy()              category / distribution / persistence
   │
   ▼
★ response_renderer.render()                 forecast in every shape + forecast_notice
```

The "Stage N" names inside `pipeline.py` are pipeline steps, not development stages.

---

## 3. Step 1 — Input adapter (`input_adapter.py`, new)

**Problem.** The Stage 1 contract assumed Member 2 sends a list of row dictionaries. Member 2's code actually sends:

```json
{ "columns": [{"name": "month", "type": "DATE"}, {"name": "total", "type": "DECIMAL"}],
  "rows": [["2024-01-01", "48250.50"], ...],
  "rowCount": 24, "truncated": false,
  "masking": {"columns": [{"name": "email", "piiType": "EMAIL"}]} }
```

Without conversion, every chart and forecast would have degraded to a table.

**Processing steps (`adapt_result`):**

1. Detect the format: Member 2 columnar, legacy list of dicts, or a `{"raw_results": [...]}` envelope.
2. **Reserve all original column names**, then rename duplicates (`total`, `total_2`). Reserving first prevents a rename from overwriting a real column.
3. Zip each array row with the column names into a dict.
4. Normalise in-process driver types (`Decimal`, `date`) to the same string representation as the wire format, so both paths profile identically.
5. Map masked columns **by position**, so masking survives a rename. Recorded as `masked_columns` (`{column: piiType}`).
6. Set `truncated` when `truncated: true` or `rowCount > rows received`, and add the warning `INPUT_TRUNCATED`.

**Output.** An `AdaptedResult` with `rows`, `columns`, `row_count`, `rows_received`, `truncated`, `masked_columns`, `renamed_columns`, `warnings`. It appears in the API envelope under `input`.

**Related fix (`result_profiler.py`).** DECIMAL values arrive as strings ("48250.50"). Measure columns are converted to numbers after profiling, so totals show with labels and formatting.

---

## 4. Step 2 — Result layouts (`result_profiler.py`)

A forecast is only meaningful for one value per period. The profiler now classifies every result:

| Layout | Meaning | Forecast handling |
| --- | --- | --- |
| `SINGLE` | One row per period (e.g. monthly totals) | One series forecast |
| `GROUPED` | One row per period **per category** (month × region) | Each category forecast separately |
| `CROSS_SECTIONAL` | No time axis; one row per category | No time forecast; category strategies |
| `EVENTS` | Several unaggregated rows per period | Refused: "ask for a total per period" |

Granularity (day / week / month / quarter / year) is taken from the **shorter gaps** between dates, not the median gap. This stops sparse monthly data being read as quarterly.

---

## 5. Step 3 — Data readiness classifier (`prediction.assess_readiness`)

### 5.1 Output

`prediction.stage_2_readiness` in the API envelope (`ReadinessReport`):

| Field | Meaning |
| --- | --- |
| `decision` | `READY`, `READY_WITH_WARNING` or `NOT_READY` |
| `verdict` | Internal verdict: `READY`, `NOT_TEMPORAL`, `MULTI_SERIES`, `NOT_AGGREGATED`, `INCOMPLETE`, `INSUFFICIENT_POINTS`, `DEGENERATE`, `LOW_SIGNAL` |
| `reason_codes` | Machine-readable reasons, e.g. `TOO_MANY_MISSING_VALUES`, `IRREGULAR_INTERVALS`, `STATIONARITY_STATIONARY` |
| `warnings` | `[{code, message}]` cautions that travel with a shown forecast |
| `reason` | One plain-English sentence |
| `checks` | Audit trail, e.g. `"sufficiency: PASS (36 observations)"` |
| `n_points`, `dropped_rows`, `filled_periods`, `missing_value_ratio`, `missing_period_ratio` | Data-quality measurements |
| `coefficient_of_variation`, `trend_r2`, `stationarity`, `signal_test`, `expected_relative_error`, `skill_vs_naive` | Statistical evidence |

### 5.2 The gates, in order

The first failing gate stops evaluation and sets the reason. A caution never blocks the forecast.

**Gate 1 — Temporal validity**
- No date column, or no numeric measure → `NOT_READY` (`NOT_TEMPORAL`).
- `GROUPED` layout → `MULTI_SERIES` (forecast per category by the strategy layer).
- `EVENTS` layout → `NOT_READY` (`NOT_AGGREGATED`).

**Gate 1b — Completeness** (`prepare_series`, unreadable values)
- Rows whose date or value cannot be parsed are dropped and counted.
- More than **20%** dropped (`MAX_MISSING_VALUE_RATIO`) → `NOT_READY` (`TOO_MANY_MISSING_VALUES`).
- Fewer → caution `MISSING_VALUES_DROPPED`.

**Gate 1c — Regularity** (`prepare_series`, missing periods)
1. Observations are placed on the calendar grid of the granularity (`_period_index`).
2. Daily data with no weekend dates uses a **business-day calendar**, so weekends are not gaps.
3. Empty grid positions are filled by **linear interpolation** between neighbours. The filled points exist only for the model; anomaly detection and summaries never report them as observations.
4. More than **25%** empty periods (`MAX_MISSING_PERIOD_RATIO`) → `NOT_READY` (`IRREGULAR_INTERVALS`). Fewer → caution `MISSING_PERIODS_INTERPOLATED`.
5. Two observations in one period → `NOT_READY`: the dates are not on a regular calendar.

**Gate 2 — Statistical sufficiency**
- Fewer than **4** usable points (`MIN_POINTS_ANY`) → `NOT_READY` (`INSUFFICIENT_POINTS`).

**Gate 3 — Signal quality**
1. **Constant series** → `NOT_READY` (`DEGENERATE`).
2. **Near-constant** (coefficient of variation < 1%, `NEAR_CONSTANT_CV`) → caution `NEAR_CONSTANT`.
3. **Stationarity evidence** (`stationarity_evidence`, 12+ points): ADF and KPSS are run together. Their null hypotheses are opposite, so their combination is read as one verdict:

   | ADF (H0: unit root) | KPSS (H0: stationary) | Verdict |
   | --- | --- | --- |
   | rejects (p < 0.05) | does not reject | `STATIONARY` |
   | does not reject | rejects | `NON_STATIONARY` (handled by trend models / differencing) |
   | rejects | rejects | `CONFLICT` → caution `STATIONARITY_CONFLICT` (typical of a level shift) |
   | does not reject | does not reject | `INCONCLUSIVE` (expected on short series) |

   Evidence: on held-out M4, 29.0% of forecasts were unreliable when the tests conflicted, against 7.5–15.5% for the other verdicts.
4. **Forecastability test** (`forecastability`, 8+ points). This is the key new gate:
   1. For each of the last **6** positions *t* (`SIGNAL_TEST_ORIGINS`), fit each simple candidate on `values[:t]` only and forecast `values[t]`. Candidates: naive, linear regression, damped Holt, and seasonal naive when a full cycle exists.
   2. Take each candidate's mean absolute error (`in_history_errors`).
   3. `expected_relative_error` = best candidate's MAE ÷ mean absolute level of the series.
   4. Above **20%** (`MAX_EXPECTED_ERROR`) → `NOT_READY` (`LOW_SIGNAL`): "Series is dominated by noise".
   5. With fewer than 8 points the test cannot run → caution `SIGNAL_NOT_ASSESSED`, and the selector uses the conservative moving average.

   **How 20% was chosen:** on development data only (66 synthetic + 100 M4_DEV series), as the best F1 at refusing unreliable forecasts among thresholds whose refusals are right at least 80% of the time. A forecast window counts as unreliable when its sMAPE exceeds 20%.

**Decision.** All gates passed → `READY`, or `READY_WITH_WARNING` if any caution was raised. Otherwise `NOT_READY` with the verdict's reason code first.

---

## 6. Step 4 — Model selection with a benchmark guard (`prediction.select_model`)

### 6.1 Rule selection (`_rule_selection`)

Two signal families are combined: the **semantic** intent of the question and **statistical** signals of the data (n, trend R², coefficient of variation, seasonal autocorrelation at the period lag, ADF). Rules, most specific first:

| # | Condition | Model |
| --- | --- | --- |
| 1 | fewer than 6 points (`MIN_POINTS_TREND`) | Weighted moving average (window 3) |
| 2 | trend or anomaly intent, **and** seasonal-ready* | SARIMA |
| 3 | trend intent and trend R² ≥ 0.55 (`STRONG_TREND_R2`) | Linear regression |
| 4 | comparison / ranking / proportion intent and CV > 0.45 (`VOLATILITY_THRESHOLD`) | Damped Holt |
| 5 | seasonal-ready* (any intent) | SARIMA |
| 6 | R² ≥ 0.55 | Linear regression |
| 7 | otherwise | Damped Holt |

\* Seasonal-ready = statsmodels available, period > 1, at least **24** points (`MIN_POINTS_SEASONAL`, two monthly cycles) and seasonal ACF ≥ **0.35** (`SEASONAL_ACF_THRESHOLD`).

### 6.2 Benchmark guard

**Problem found:** the unguarded rules were significantly *worse* than the naive forecast on real data (p = 0.001), mostly because undamped Holt projected noise as trend.

**Steps:**
1. Take the rule's choice (SARIMA is exempt; see below).
2. Benchmarks: naive (next = last), plus seasonal naive (next = same period last cycle) when a full cycle exists.
3. Compute the one-step-ahead MAE of the choice and of each benchmark over the same 6 in-history origins as the forecastability gate.
4. If the choice's MAE is higher than the best benchmark's, **the benchmark is used instead**, and the reason says so.
5. The comparison is recorded under `signals.guard` (`rule_choice`, `rule_choice_mae`, `best_baseline`, `best_baseline_mae`, `overridden`).

SARIMA is exempt because the check would need one SARIMA refit per origin (~0.3 s each) on every request, and SARIMA is only chosen after an explicit seasonality test.

### 6.3 Model changes

| Model | Stage 2 change | Why |
| --- | --- | --- |
| **Damped Holt** (`_fit_holt`) | Trend multiplied by φ = 0.9 each step; α = 0.5, β = 0.3 fixed | Undamped Holt extrapolated short-run noise indefinitely. Optimising α/β on 12–36 points over-fits. |
| **SARIMA** (`_fit_sarima`) | Airline order (0,1,1)(0,1,1)ₘ; requires 2 full cycles, else falls back to damped Holt | The Stage 1 order (1,1,1)(1,1,1)₁₂ had mean MASE 7.04 with 12 blow-ups. Airline: 1.69; per-series AICc selection: 2.03. |
| **Naive / seasonal naive** (`_fit_naive`, `_fit_seasonal_naive`) | New | Benchmarks for the guard and the evaluation |
| Linear regression, weighted moving average | Unchanged | — |

---

## 7. Step 5 — Calibrated forecast intervals (`prediction.project_series`)

`project_series` is the **single forecasting code path**: live requests and the benchmark both call it, so the evaluation measures exactly what users receive.

**Band construction (every model, including SARIMA):**

```
half_width(h) = z × residual_std × widening(h) × small_sample_penalty

z                     1.96 for 95% (also 0.80 / 0.90 / 0.99)
residual_std          std of in-sample residuals, start-up values excluded
                      (SARIMA: first cycle + 1; naive: first value)
widening(h)           √h ; seasonal naive: √(⌊(h−1)/m⌋ + 1)
small_sample_penalty  1 + 3 / max(n, 4)   (+50% at n = 6, negligible past 30)
floor                 at least 2% of the forecast × √h (never a zero-width band)
```

**Why not statsmodels' own SARIMA intervals:** they treat the estimated parameters as exact and covered only about 67–75% of outcomes for a nominal 95% on short series. Residual-based bands give 95.0% for SARIMA on held-out M4.

Output per forecast point: `predicted`, `lower_bound`, `upper_bound`, `label`, `timestamp`. The fit quality is reported as `in_sample_rmse`, `in_sample_mae` and `in_sample_mape`.

---

## 8. Step 6 — Prediction strategies (`strategies.py`, new)

Stage 1's intent-to-strategy map (`INTENT_STRATEGY_MAP`) named four strategies, but only the time-series forecast ever ran. Stage 2 implements the other three. All forecasts inside them use `project_series` with the guarded selector.

| Strategy | Triggered by | What it computes |
| --- | --- | --- |
| `TEMPORAL_FORECAST` | trend | One series forecast (or one per category for a `GROUPED` result) |
| `CATEGORY_TRAJECTORY` | comparison, ranking | Forecasts every category (max 12) and projects **which leads next period** and whether the ranking changes |
| `DISTRIBUTION_SHIFT` | distribution, proportion | Projects **category shares** (grouped), **per-period quartiles** (raw rows) or the forecast's position in the historical distribution (single series) |
| `ANOMALY_PERSISTENCE` | anomaly | For an anomaly in the last 3 periods: does the forecast stay beyond the threshold (persisting / worsening) or return inside it (recovering)? |

Each strategy runs only on layouts where its question is meaningful; otherwise it returns a specific `skipped_reason`.

---

## 9. Step 7 — Forecast delivery in every response shape (`response_renderer.py`, `summarization.py`, `visualization.py`)

**Problem:** a requested forecast was only drawn on charts. In table, summary and single-answer responses it was silently dropped.

| Shape | How the forecast is delivered |
| --- | --- |
| `CHART` | Forecast line and range band (rules R1, R2); for grouped results, per-category lines and bands (new rule **R5**) |
| `TABLE_CONTENT` | Forecast rows appended, `row_type: "FORECAST"`, with lower and upper bounds |
| `SHORT_SUMMARY` / `MIXED_SUMMARY` | Forecast-first summary using a condensed forecast claim (`FORECAST_PATH`) |
| `SINGLE_ANSWER` | The forecast value itself, with its range and model |

**`forecast_notice`** is added whenever the user explicitly asked for a forecast:

| Field | Meaning |
| --- | --- |
| `requested` | True |
| `status` | `SHOWN` or `REFUSED` |
| `readiness_decision`, `reason_codes`, `warnings` | From the readiness report |
| `message` / `reason` | What was shown, or why it was refused |
| `model`, `horizon`, `strategy` | What produced it |
| `shown_in` | Which blocks carry it, e.g. `["CHART"]` |

Summaries also gained a readiness caution claim and **layout-aware** wording: no "per period" or "changed from X to Y" for non-time data, and claims read in chronological order whatever the query's `ORDER BY`.

---

## 10. Step 8 — Evaluation

### 10.1 Data

| Group | Series | Source | Role |
| --- | --- | --- | --- |
| Synthetic | 66 | `synthetic_data.py`: 2 lengths × 5 noise levels × seasonal or not × 3 trends, plus 6 near-constant | Development |
| M4_DEV | 100 | M4 competition, monthly series, random sample (seed 2026) | Development |
| M4_TEST | 100 | M4 monthly, seed 2027, disjoint from M4_DEV | **Held-out**, evaluated once with frozen code |

Every M4 series is its official train and test values joined, then cut to the **last 36 observations** to match small business histories. The samples are in `benchmark_data/`, rebuilt by `prepare_m4_sample.py`.

### 10.2 Method (`evaluate_forecasting.py`)

1. **Rolling origin:** 4 forecast origins per series, 3 months apart, each forecasting 3 months ahead using only data before the origin.
2. **Approaches:** naive, seasonal naive, weighted moving average, linear regression, damped Holt, SARIMA, adaptive without guard, adaptive with guard.
3. **Metrics:**
   - MASE (scaled by the in-sample one-step naive error), sMAPE, MAE, RMSE, relative RMSE against naive;
   - overall, per step ahead and per data regime;
   - 95% band coverage.
4. **Significance:** Wilcoxon signed-rank test on per-series MASE (SciPy).
5. **Gate evaluation:** refusal rate, precision and recall against the 20% sMAPE definition of an unreliable forecast.

### 10.3 Readiness correctness (`evaluate_readiness.py`)

85 labelled result sets (17 case types × 5 seeds), each with the correct decision fixed by how it was generated. Examples: too short, 30% unreadable values, 40% missing months, constant, weekly with gaps, business-day calendar, grouped, events.

### 10.4 Strategies (`evaluate_strategies.py`)

Synthetic data with known truth, each strategy against a naive answer (the current leader stays, shares persist, always "persists").

---

## 11. Results (held-out M4_TEST unless stated)

| Measure | Result |
| --- | --- |
| 95% band coverage (adaptive + guard) | **94.5%** (95 / 95 / 94% at h = 1 / 2 / 3) |
| MASE mean / median, adaptive + guard | **1.443 / 1.234** (naive 1.491 / 1.231) |
| sMAPE | 9.5% (naive 10.8%) |
| Relative RMSE vs naive | 0.938 |
| Guard vs naive | best on every summary measure, **not significant** (p = 0.81) |
| Guard vs unguarded rules | significantly better (p < 0.0001) |
| Readiness refusals | 5.0% of forecasts; precision **0.90**; recall 0.35 |
| sMAPE of accepted vs refused forecasts | 7.1% vs 53.7% |
| Stage 1 gate (CV / R² rule) | refused 0 forecasts |
| Labelled readiness cases | **85 / 85**; 0 false-ready; 0 false refusals; correct reason code 100% |
| Category leader next period | 90.0% (naive 88.0%); where the leader changes: 29.2% vs 0% |
| Share error next period | 1.62 pp vs 1.74 pp (p = 0.003) |
| Anomaly persistence | 71.6% (best constant answer 52.7%) |

---

## 12. Tests

| Suite | Covers |
| --- | --- |
| `test_readiness.py` | Every gate, every decision level, reason codes (23 checks) |
| `test_input_adapter.py` | Columnar and legacy formats, duplicates, masking by position, DECIMAL, truncation |
| `test_forecast_delivery.py` | Every shape × shown / refused / not asked |
| `test_strategies.py` | The three strategies and their skip reasons |
| `test_component.py` | End-to-end pipeline regression |

The synthetic MySQL harness (`test_db/`: schema, seeder, Member 2 stand-in, 77 fixtures) was written in Stage 2 but first run in Stage 6, on SQLite.

---

## 13. Files

| File | Change |
| --- | --- |
| `prediction.py` | Readiness classifier, `prepare_series`, ADF + KPSS, forecastability gate, benchmark guard, damped Holt, airline SARIMA, naive models, shared `project_series` with calibrated bands |
| `input_adapter.py` | New |
| `strategies.py` | New |
| `result_profiler.py` | Layouts, grouped series, DECIMAL conversion, granularity from shorter gaps |
| `response_renderer.py` | Forecast in every shape, `forecast_notice` |
| `summarization.py` | Layout-aware and chronological claims, strategy claims, forecast-path claim, readiness caution claim |
| `visualization.py` | Rule R5: per-category forecast lines and bands |
| `pipeline.py`, `api.py`, `schemas.py` | Wiring; `member2_result` API field; new verdicts and models |
| `evaluate_forecasting.py`, `evaluate_readiness.py`, `evaluate_strategies.py` | New benchmarks |
| `benchmark_data/` | M4 samples and the sampling script |
| `test_*.py`, `test_db/` | New and updated tests; integration harness |

**Reproduce** (deterministic, `LLM_PROVIDER=none`):
- `python evaluate_forecasting.py` (about 1 minute)
- `python evaluate_readiness.py`
- `python evaluate_strategies.py`

---

## 14. Limitations carried forward

1. Model selection is not significantly better than naive (p = 0.81). Stage 2's value is knowing **when not to forecast** and giving honest ranges.
2. Gate recall is 35%. The threshold deliberately favours precision, because a refusal withholds an answer.
3. M4 samples are 100 series each, truncated to 36 months. "90% of refusals correct" rests on about 20 refusals.
4. `INPUT_TRUNCATED` is recorded by the adapter but not yet used by the readiness check.
5. Strategy results come from synthetic data only.
6. Seasonal anomalies were still missed (recall 0 on the seasonal case). This was addressed in Stage 3.

**Since Stage 2.** Stage 8 hardened this layer for production and re-tested it on 1,000 unseen M4 series. Changes:
- truncated input is refused (item 4 above);
- ranges never go below zero, and SARIMA has a time limit;
- SARIMA is now guarded, and fitted smoothing is used from 48 points;
- a stationarity-conflict refusal was added;
- policy now lives in `forecast_config.json`.

Item 3 is now measured properly: on 333 refusals, 72% are right (95% CI 67–77%), not 90%. See `stage8_completion_report.md`.
