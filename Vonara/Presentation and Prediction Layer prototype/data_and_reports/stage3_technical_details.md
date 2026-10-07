# Stage 3 — Technical Details: Dual-Dimension Anomaly Engine

**Component 4 · Presentation & Prediction Layer · Wijethunge W M V (IT23256750) · J26-SE-347**
Branch `vonara-nl-to-sql-prototype-stage-3`, commits `5f3b58f`, `cac1e64`, `e23b92d`. Full results: `stage3_completion_report.md`.

---

## 1. Purpose

The anomaly engine (`anomaly.py`, pipeline step "Stage 5 Anomaly Detection") flags unusual values in two dimensions:

- **Historical (retrospective):** observations already in the result set.
- **Predictive (prospective):** forecast points projected to breach the same normal range.

At the end of Stage 2 it had three gaps. Stage 3 closes them:

1. **Seasonal anomalies were never detected.** Recall was 0 on the seasonal case: a seasonal series swings by its own pattern, so the seasonal peaks set the fence and a real outlier sat inside it.
2. **A one-off spike and a lasting shift were treated the same.** The persistence strategy carried last-period spikes forward and called them persistent (59.8% correct on spikes).
3. **No labelled benchmark** compared the detection rules (proposal §3.7) or scored the two dimensions separately (§3.11).

---

## 2. Where Stage 3 sits in the pipeline

```
  prediction.generate_forecast()         (Stage 2 of development)
          │  ForecastResult
          ▼
★ anomaly.detect_anomalies(values, labels, forecast, method, period)
          │  AnomalyReport: thresholds, historical_anomalies, predictive_warnings
          ▼
★ anomaly.classify_patterns()            SPIKE / SUSTAINED / UNCONFIRMED
          ▼
★ strategies.ANOMALY_PERSISTENCE         RECOVERING / PERSISTING / WORSENING
          ▼
  whatif ★ (re-screens scenario values in the same space)
          ▼
  visualization (R3 markers ▲ past, ◆ projected)  →  summarization (A-claims)
```

`pipeline.py` and the what-if engine now pass the **seasonal period** derived from the result's granularity (12 for months, 4 for quarters…).

---

## 3. The detection algorithm (`detect_anomalies`)

### Step 1 — Minimum data

Fewer than **5** observations (`MIN_POINTS_FOR_ANOMALY`) → skipped, with `skipped_reason`.

### Step 2 — Choose the detection space

The engine decides in which space "unusual" really means unusual:

```
                ┌───────────────────────────────────────────────┐
                │ period > 1 and n ≥ 3 × period ?               │
                │ and STL seasonal strength ≥ 0.40 ?            │
                └──────────────┬───────────────────────┬────────┘
                           yes │                       │ no
                               ▼                       ▼
                  SEASONAL space (STL)       linear trend R² ≥ 0.50 ?
                  ADAPTIVE_IQR_ZSCORE_STL      yes │           │ no
                                                   ▼           ▼
                                      DETRENDED space     RAW space
                                      ..._DETRENDED       ADAPTIVE_IQR_ZSCORE
```

| Space | Each value is judged as | Constant |
| --- | --- | --- |
| **Seasonal** *(new)* | value − (STL trend + same-phase seasonal) | `MIN_CYCLES_FOR_STL = 3`, `SEASONAL_STRENGTH_THRESHOLD = 0.40` |
| **Detrended** | value − linear trend | `DETREND_R2_THRESHOLD = 0.50` |
| **Raw** | the value itself | — |

The reported anomaly value is always the **raw observation** the user recognises; only the decision is made in the chosen space. The space is recorded as `method`, `seasonal`, `detrended`, `seasonal_strength` and `period`.

**Seasonal strength** follows Wang, Smith & Hyndman (2006):

```
strength = max(0, 1 − Var(remainder) / Var(seasonal + remainder))
```

### Step 3 — STL decomposition, with design decisions measured on DEV data (`_stl_components`)

STL (statsmodels `STL`) splits the series into trend + seasonal + remainder. Four choices were tested on the development split:

1. **Periodic season** (`seasonal = 2n + 1`, `seasonal_deg = 0`, one constant per phase). STL's default 7-point seasonal smoother, on 3–4 points per phase, fitted each phase almost exactly and absorbed the outliers: 37 of 40 clean series raised a false alarm.
2. **Three cycles, not two.** With two cycles, a spike is split evenly between itself and its partner one cycle away, so it cannot be told apart from the season.
3. **Two fits, each used for what it does well:**
   - The **robust** fit (`robust=True`) gives the expected value. Its iterations down-weight outliers, so a spike stays in the remainder (4σ recall 0.83 vs 0.23 with a plain fit).
   - Its remainder is too peaked, though: its IQR understated the noise (5% of clean points flagged). So the **spread** comes from the **plain** fit's remainder.
   - That remainder is widened by √(n / (n − df)), where df = (period − 1) + 2n / trend_window: the same correction as a regression's n − p divisor.
4. **Threshold 0.40** gave the best historical F1 on DEV among 0.40, 0.50 and 0.60. Judging the volatility regime on the remainder was tried and **dropped** (it lowered DEV F1).

Beyond the history (for forecast points), the expected value is the STL trend extended linearly from its last cycle, plus the same phase of the last seasonal cycle.

### Step 4 — Adaptive thresholds (volatility regimes)

The regime is judged on the **raw** series' coefficient of variation (CV):

| Regime | CV | IQR multiplier *k* | Z threshold |
| --- | --- | --- | --- |
| STABLE | < 0.20 | 1.5 | 2.5 |
| MODERATE | 0.20 – 0.60 | 2.0 | 3.0 |
| VOLATILE | ≥ 0.60 | 2.5 | 3.5 |

In the working space (raw, detrended or seasonal remainder):

```
Q1, Q3, IQR = quartiles of the working values
lower_threshold = Q1 − k × IQR
upper_threshold = Q3 + k × IQR
z = |working value − mean| / std
```

If the IQR is zero (heavily tied data), the standard deviation is used instead. If there is no dispersion at all, detection is refused rather than dividing by zero.

### Step 5 — Detection rule (`method`, new option)

| `method` | A point is flagged when |
| --- | --- |
| `COMBINED` (production) | it breaches the IQR fence **or** the Z threshold |
| `IQR` | it breaches the IQR fence |
| `ZSCORE` | it breaches the Z threshold |

Each flag records which rule raised it (`detected_by: ["IQR", "ZSCORE"]`). The single-rule modes exist so the benchmark can measure each rule's contribution (§3.7).

### Step 6 — Score each flagged point

| Field | Meaning |
| --- | --- |
| `direction` | `HIGH` or `LOW` |
| `z_score` | Standard deviations from the working mean |
| `iqr_distance` | How far beyond the fence, in IQRs |
| `severity` | `SEVERE` if z > threshold + 1 **or** distance > 1.5, else `MODERATE` |
| `deviation_pct` | Distance from the raw mean, as a percentage |
| `label`, `value`, `index` | Which observation, as the user sees it |

### Step 7 — Predictive dimension and screening space (new)

1. Each forecast point is projected into the same working space and judged against the **same** thresholds.
2. **Problem found:** a non-seasonal forecast (naive, Holt, linear) has no seasonal shape. Comparing it with the seasonal expectation flagged **18%** of normal series on DEV.
3. **Fix:** only forecasts from seasonal models (`SEASONAL_NAIVE`, `SARIMA`) are screened in the seasonal space. Others are re-screened in the level space (raw or detrended).
4. `predictive_space` records which space was used: `SEASONAL`, `DETRENDED` or `RAW`.

---

## 4. Spike, sustained, unconfirmed (`classify_patterns`, new)

A spike and the start of a level shift look identical when they happen; only the next observations tell them apart. Each historical anomaly is labelled from its neighbours:

| Pattern | Rule | Shown in the UI as |
| --- | --- | --- |
| `SUSTAINED` | A neighbour (previous or next) is an anomaly in the **same direction** | "lasting shift" |
| `SPIKE` | Isolated, and the next observation is back in range | "one-off spike" |
| `UNCONFIRMED` | Isolated, and it is the **latest** observation | "latest period, too early to tell" |

---

## 5. Anomaly persistence uses the pattern (`strategies.py`)

The persistence strategy answers: "will this recent anomaly continue?" It considers anomalies in the last 3 periods (`RECENT_WINDOW`); the most recent one is judged.

| Pattern | Basis | How it is judged |
| --- | --- | --- |
| `SPIKE` | `OBSERVED_RETURN` | The data already shows the return to normal → `RECOVERING`. No projection needed. |
| `SUSTAINED` | `FORECAST` | The forecast's predictive warnings are used |
| `UNCONFIRMED` | `FORECAST_WITHOUT_LATEST_POINT` | The same model is refitted **without** the latest point, and that forecast is screened. The summary says the verdict is provisional. |

**Verdict:**
- No predictive warning on the same side as the anomaly → `RECOVERING`.
- Otherwise `PERSISTING`, or `WORSENING` when every forecast step is warned and the distance beyond the fence grows each step.
- With no anomaly in the window → `NO_RECENT_ANOMALY`.

**Why refit without the latest point:** a naive model copies the last value forward, so a last-period spike always looked persistent. That was the cause of Stage 2's 59.8% on spikes.

The summary (`summarization.py`) states which basis was used.

---

## 6. What-if wiring (`whatif.py`)

When a scenario changes the forecast ("cut spending by 20%"), the scenario values are re-screened for anomalies. The re-screen keeps the **forecast model**, so scenario values are judged in the same space as the original forecast.

---

## 7. Output (`prediction.stage_5_anomaly` in the API envelope)

| Field | Meaning |
| --- | --- |
| `evaluated`, `skipped_reason` | Whether detection ran, and why not |
| `method` | e.g. `ADAPTIVE_IQR_ZSCORE_STL`, `ADAPTIVE_IQR_ZSCORE_DETRENDED` |
| `seasonal`, `seasonal_strength`, `period` | Seasonal space details *(new)* |
| `detrended`, `trend_r2` | Detrended space details |
| `predictive_space` | Where forecast points were screened *(new)* |
| `volatility_regime`, `iqr_multiplier`, `z_threshold` | The adaptive parameters |
| `lower_threshold`, `upper_threshold`, `q1`, `q3`, `iqr`, `median`, `mean`, `std` | The normal range, **in the working space** |
| `historical_anomalies[]` | Past outliers, each with `pattern` *(new)* and `detected_by` *(new)* |
| `predictive_warnings[]` | Forecast points projected to breach the range |

For a seasonal or detrended series, the thresholds describe a **deviation** from the expected value, not a level. The UI must not draw them as horizontal lines on the value axis; Stage 7 fixed exactly that.

---

## 8. Evaluation (`evaluate_anomalies.py`, new)

### 8.1 Labelled benchmark

| Part | Design |
| --- | --- |
| **Historical** | 144 series per split. Factorial grid: length 24 / 36 / 48 × shape flat / trend / seasonal / trend + seasonal × noise 3 / 8 / 15% of level × 4 repetitions. Each carries 0–3 injected spikes or dips of 3, 4 or 6σ; a quarter are clean. |
| **Predictive** | 324 series per split, three futures each: normal, a level shift lasting through the future, or a one-off spike in the last period. The forecast comes from the production selector. |
| **Truth** | Independent of any detector: a point is anomalous only if an injected event covers it. |
| **Splits** | DEV (seed 2026) for every design choice; TEST (seed 2027) reported once with frozen code. |
| **Metrics** | Precision, recall, F1, false-positive rate, clean series with a false alarm; reported separately per dimension; recall by magnitude and shape |
| **Detectors compared** | Static textbook (1.5·IQR / z = 3), the Stage 2 rule (combined, no STL), IQR alone + STL, Z-score alone + STL, combined + STL (production) |

### 8.2 Persistence benchmark (`evaluate_strategies.py`)

Stage 2's events (one-off spike in the last period; shift over the last two periods), plus a new `SHIFT_LAST` case (a shift starting in the very last period), so the trade-off is measured, not hidden.

---

## 9. Results (held-out TEST)

**Historical anomalies (144 series, 230 injected anomalies):**

| Detector | Precision | Recall | F1 | Clean series with a false alarm |
| --- | --- | --- | --- | --- |
| Static textbook | 0.768 | 0.330 | 0.462 | 4 / 33 |
| Stage 2 rule | **0.817** | 0.409 | 0.545 | 6 / 33 |
| IQR alone + STL | 0.701 | 0.500 | **0.584** | 11 / 33 |
| Z-score alone + STL | 0.711 | 0.374 | 0.490 | 13 / 33 |
| **Combined + STL (production)** | 0.671 | **0.504** | 0.576 | 14 / 33 |

| F1 by shape | Flat | Trend | Seasonal | Trend + seasonal |
| --- | --- | --- | --- | --- |
| Stage 2 rule | 0.828 | 0.596 | 0.231 | 0.197 |
| Combined + STL | 0.822 | 0.596 | **0.382** | **0.396** |

Recall on 6σ anomalies: 62.5% → 70.3%; on 4σ anomalies: 49.4% → 60.5%. Flat and trending series are unchanged, because the seasonal space only switches on when a seasonal pattern is present.

**Predictive warnings (324 series, horizon 3):**

| Detector | Precision | Recall | F1 | Normal / shift / last-spike series warned |
| --- | --- | --- | --- | --- |
| Stage 2 rule | 0.630 | 0.358 | 0.457 | 1.9% / 38.0% / 22.2% |
| **Combined + STL** | 0.581 | **0.420** | **0.487** | 6.5% / 45.4% / 29.6% |

**Anomaly persistence:**

| Event | Stage 2 | Stage 3 |
| --- | --- | --- |
| One-off spike in the last period (87) | 59.8% | **95.4%** |
| Shift over the last two periods (82) | 84.1% | 81.7% |
| Spike + shift, Stage 2's benchmark (169) | 71.6% | **88.8%** |
| Shift starting in the last period (92, new) | — | 2.2% |

**Interpretation:**
- **Seasonal detection now works, at a cost.** About twice the F1 on seasonal shapes, but precision fell from 0.817 to 0.671, and clean series with a false alarm rose from 6 to 14 of 33.
- **§3.7, which rule:** the IQR fence does most of the work. Z-score alone is the weakest. Combining adds recall but no F1; it is kept for recall, and the evidence for it is weak.
- **Spike vs shift:** a single latest observation cannot separate a spike from a fresh shift. Stage 3 resolves that ambiguity towards "one-off" (`SHIFT_LAST` 2.2%). Which way is cheaper depends on real base rates.

---

## 10. Tests

`test_anomaly.py`, **19 checks**:
- the three detection methods;
- the seasonal space switching on and off;
- forecast screening space;
- spike / sustained / unconfirmed labelling;
- each persistence basis.

All other suites still pass, and the readiness benchmark still gives 85/85.

---

## 11. Files

| File | Change |
| --- | --- |
| `anomaly.py` | Detection-rule option; STL seasonal space (robust expectation, plain-fit spread with df correction); forecast screening space; `classify_patterns` |
| `evaluate_anomalies.py` | New labelled benchmark (historical + predictive, DEV / TEST) |
| `strategies.py` | Persistence uses the pattern: `OBSERVED_RETURN`, `FORECAST`, `FORECAST_WITHOUT_LATEST_POINT` |
| `summarization.py` | States the persistence basis; provisional wording for an unconfirmed latest anomaly |
| `pipeline.py`, `whatif.py` | Pass the seasonal period; the what-if re-screen keeps the forecast model |
| `evaluate_strategies.py` | `SHIFT_LAST` case; the no-STL comparison |
| `test_anomaly.py` | 19 checks |
| `data_and_reports/` | `anomaly_benchmark.md` and JSON, `stage3_completion_report.md`, README, roadmap, team contract |

**Reproduce** (deterministic):
- `python evaluate_anomalies.py`
- `python evaluate_strategies.py`
- `python evaluate.py anomaly`

---

## 12. Limitations carried forward

1. **Synthetic data only.** No real labelled anomaly set exists for business data, and M4 has no anomaly labels.
2. **Seasonal precision is 0.40** on held-out data. A tighter seasonal fence would trade back some recall.
3. **No significance tests** on the anomaly comparisons. DEV and TEST agree in direction only.
4. **Seasonal series shorter than 3 cycles** (e.g. 24 months) still use the Stage 2 rule, deliberately.
5. **The `SHIFT_LAST` trade-off** (2.2%) needs real base rates to settle.
6. **Later fixes, made in Stage 7:**
   - record lists (`DETAIL_LOOKUP`) no longer get anomaly bands;
   - normal-range lines are drawn only when the band is in the value's own space;
   - the ▲ / ◆ marker shapes now render correctly.
