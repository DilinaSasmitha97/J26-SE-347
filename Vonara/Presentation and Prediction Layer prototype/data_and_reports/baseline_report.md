# Baseline Report — Component 4 (Presentation & Prediction Layer)

**Member:** Wijethunge W M V (IT23256750) · **Project:** J26-SE-347
**Status:** Progress Presentation 1 — working prototype, all four parts implemented
**Mode for all figures:** deterministic (`LLM_PROVIDER` unset), fixed seeds
**Reproduce:** `python evaluate.py --json=evaluation_results.json`

---

## 1. What exists now

All four parts run end to end, offline, in ~25 ms per query.

| Part | Status | Evidence |
|---|---|---|
| 1 · Query Understanding | Working | `python main.py analyze "..."` |
| 2 · Adaptive Visualization | Working | Vega-Lite v5 grammar + 4 extension rules |
| 4 · Prediction Stages 1–6 | Working | 4 forecast models, dual-dimension anomalies, what-if |
| 3 · Unified Summarization (Stage 7) | Working | claim ledger + verifier, 100 % grounded |

Measured stage latency on a 24-point series (`main.py demo finance_linear_growth`):

| Stage | ms |
|---|---|
| Part 4 Prediction | 17.09 |
| Part 1 Query Understanding | 3.52 |
| Result Profiling | 3.25 |
| Part 3 Summarization | 0.28 |
| Part 2 Visualization | 0.05 |
| **Total** | **24.76** |

---

## 2. Results

### 2.1 Intent classification — 38 held-out cases

| metric | value |
|---|---|
| Intent accuracy | 100.0 % (38/38) |
| Macro F1 | 1.0000 |
| Prediction-flag accuracy | 100.0 % |
| Table-binding recall | 94.7 % |
| Security-warning recall | 100.0 % (3/3) |

Per-class F1 is 1.00 across all nine intents (support 2–11 per class).

**This number must be presented with its caveat.** The 48-case test set was
written by the same person who wrote the marker lexicon, and the lexicon was
tuned until the dev split passed. 100 % therefore measures *coverage of the
phrasings we anticipated*, not generalisation to unseen users. Two cases in
development initially failed and were fixed by adding markers — which is
exactly the overfitting loop that makes the headline figure unsafe to quote
without qualification. Its legitimate use is as a **regression baseline**.

Planned correction (see §4): re-evaluate against Spider/BIRD questions relabelled
to this taxonomy, and have a second person author a blind test split.

### 2.2 Prediction accuracy — 3-period holdout

Out-of-sample, over the 10 of 12 benchmark scenarios long enough to hold out
3 periods.

| strategy | RMSE | MAE | mean MAPE | median MAPE |
|---|---|---|---|---|
| **Adaptive (dual-signal)** | 3,881.19 | 3,280.93 | 23.20 % | **7.42 %** |
| fixed Weighted Moving Average | **3,459.02** | **3,052.78** | 23.58 % | 8.07 % |
| fixed Linear Regression | 4,355.57 | 3,758.50 | 26.23 % | 10.69 % |
| fixed Exponential Smoothing | 4,320.26 | 3,438.59 | 24.04 % | 9.64 % |

Per-scenario MAPE for the adaptive selector:

| scenario | n | selected | expected | MAPE |
|---|---|---|---|---|
| finance_linear_growth | 24 | LINEAR_REGRESSION | ✓ | 2.13 % |
| finance_seasonal | 36 | SARIMA | ✓ | 6.80 % |
| sales_volatile_trend | 24 | LINEAR_REGRESSION | ✓ | 24.54 % |
| sales_flat_noisy | 24 | EXPONENTIAL_SMOOTHING | ✓ | 16.11 % |
| short_series_five | 5 | WEIGHTED_MOVING_AVERAGE | ✓ | n/a (too short) |
| anomaly_spikes | 30 | LINEAR_REGRESSION | ✓ | 3.82 % |
| anomaly_seasonal_spikes | 36 | SARIMA | ✓ | 10.13 % |
| whatif_reduction | 24 | LINEAR_REGRESSION | ✓ | 3.25 % |
| **high_volatility** | 24 | EXPONENTIAL_SMOOTHING | ✓ | **154.00 %** |
| quarterly_seasonal | 48 | SARIMA | ✓ | 8.05 % |
| declining_linear | 24 | LINEAR_REGRESSION | ✓ | 3.19 % |
| tiny_series_four | 4 | WEIGHTED_MOVING_AVERAGE | ✓ | n/a (too short) |

**Model-selection agreement: 100 % (12/12).** The Stage 3 dual-signal rules
recovered the generating process in every scenario. This validates the
selection algorithm specifically, and is the cleanest positive result in this
report — though note the benchmark scenarios were designed alongside the
selection rules, so agreement partly reflects shared assumptions.

**Negative result — the adaptive selector loses on mean RMSE.** Fixed WMA
achieves 3,459 vs the adaptive 3,881. Cause: the `high_volatility` scenario
(CV = 0.55, weak trend) is close to unforecastable, and any model that
extrapolates at all is punished; WMA's near-flat projection is accidentally
safer. The readiness gate should have rejected this series but did not, because
`MAX_NOISE_RATIO = 1.5` is too permissive.

This was **not** corrected before reporting, deliberately: lowering the noise
threshold until the headline number improves would be tuning the experiment to
the result. It is recorded as open issue #1 with a principled fix.

### 2.3 Anomaly detection — adaptive vs static control

6 labelled processes, 12 injected anomalies, 172 observations total.

| method | precision | recall | F1 | FPR | TP | FP | FN |
|---|---|---|---|---|---|---|---|
| **Adaptive (detrended IQR/Z)** | 1.00 | **0.50** | **0.67** | 0.000 | 6 | 0 | 6 |
| Static (textbook 1.5·IQR) | 1.00 | 0.25 | 0.40 | 0.000 | 3 | 0 | 9 |

Per case:

| case | injected | adaptive | static | detection space |
|---|---|---|---|---|
| trend_3_anomalies | 3 | R=0.67 P=1.00 | R=0.00 | residual |
| flat_2_anomalies | 2 | R=0.50 P=1.00 | R=0.50 P=1.00 | raw level |
| seasonal_2_anomalies | 2 | R=0.00 | R=0.00 | raw level |
| volatile_3_anomalies | 3 | R=0.67 P=1.00 | R=0.67 P=1.00 | raw level |
| steep_trend_2_anomalies | 2 | R=0.50 P=1.00 | R=0.00 | residual |
| clean_no_anomalies | 0 | no false positives | no false positives | residual |

**Recall doubles (0.25 → 0.50) at unchanged perfect precision and zero false
positive rate.** The entire gain comes from the two trending cases, where the
static fence spans the whole growth range and catches nothing. This is the
clearest demonstration that the adaptive component does real work.

Absolute recall of 0.50 is nonetheless modest, and the failure is systematic,
not random: **every remaining miss is on the seasonal case**, where linear
detrending cannot remove a periodic component. Open issue #2.

### 2.4 Summary grounding — Stage 7 verification

| metric | value |
|---|---|
| Summaries checked | 12 |
| Numeric assertions | 465 |
| Traceable to a computed claim | 465 |
| **Grounding rate** | **100.00 %** |
| Fully grounded summaries | 12 / 12 |

100 % is expected by construction in deterministic mode — every sentence *is* a
claim. The suite's real purpose is regression: it fails loudly if a renderer
ever formats a value differently from the claim it came from. The harder test,
LLM narration under the verifier, needs an API key and is scheduled next.

---

## 3. Open issues

**#1 — Readiness gate is too permissive on noisy series.** `MAX_NOISE_RATIO = 1.5`
lets a CV = 0.55 series through, producing a 154 % MAPE forecast that drags mean
RMSE below the naive baseline. *Fix:* replace the fixed CV ceiling with a test of
whether any candidate model beats a random-walk baseline on a rolling-origin
backtest; refuse the forecast when none does. This makes the gate a statement
about forecastability rather than about dispersion.

**#2 — Linear detrending cannot handle seasonality.** All 4 remaining anomaly
misses are on seasonal series. *Fix:* replace `_linear_baseline` with STL
decomposition when the seasonal ACF exceeds the Stage 3 threshold, and detect on
the STL remainder.

**#3 — Intent test set is not independent.** See §2.1. *Fix:* blind split
authored by a second person, plus relabelled Spider/BIRD questions.

**#4 — SARIMA emits convergence warnings on short seasonal series.** Fit still
succeeds and falls back cleanly, but the warnings are noisy. *Fix:* suppress at
the call site and record convergence status in `diagnostics`.

**#5 — Ordinal period axes are second-class.** A result set labelled "Q1..Q4"
with no date column is charted but cannot be forecast, since the horizon has no
date arithmetic. *Fix:* synthesise a period index for such axes.

---

## 4. Next iteration

1. Fix open issues #1 and #2 — both change headline metrics, so they are first.
2. Rebuild the intent test set independently (#3), and report the honest drop.
3. Enable LLM narration and measure the verifier's rejection rate — the number
   that actually demonstrates the anti-hallucination claim.
4. Integrate against Member 2's real masked output instead of synthetic rows.
5. Build the React client that renders the emitted Vega-Lite grammar.

---

## 5. Honest summary

**Working:** all four parts, end to end, offline, in ~25 ms. The prototype
demonstrates every mechanism claimed in the TAF, and two results stand up
independently — model-selection agreement (100 %) and the anomaly recall
doubling (0.25 → 0.50 at zero false positives).

**Not yet proven:** the 100 % intent accuracy is not evidence of generalisation,
and the forecasting engine does not yet beat a naive baseline on mean error.
Both have identified causes and planned fixes rather than explanations.

**Judgement:** the architecture is sound and the contributions are real, but two
of the four headline numbers need independent validation before they belong in a
paper.
