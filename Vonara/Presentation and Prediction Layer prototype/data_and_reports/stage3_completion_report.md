# Stage 3 Completion Report — Component 4 (Visualization & Prediction Layer)

5 October 2026 · Wijethunge W M V (IT23256750) · Project J26-SE-347

## Summary

Stage 3 covers the anomaly engine (Prediction Stage 5) and the anomaly-persistence strategy that depends on it. Three things were missing at the end of Stage 2:

- Seasonal anomalies were never detected (recall 0 on the seasonal case).
- One-off spikes and lasting level shifts were treated the same, so spikes were wrongly called persistent.
- No labelled benchmark compared the detection rules, as proposal §3.7 and §3.11 require.

All three are now built, tested and measured on a held-out seed.

Headline results on the held-out TEST split:

- **Seasonal detection:**
  - Seasonal series: F1 **0.231 → 0.382**.
  - Trend + seasonal series: F1 **0.197 → 0.396**.
  - Overall: F1 0.545 → 0.576, recall 0.409 → 0.504.
  - **Precision fell from 0.817 to 0.671**, and more clean series raise a false alarm (14 of 33 vs 6 of 33).
- **Predictive warnings:**
  - F1 0.457 → 0.487, recall 0.358 → 0.420.
  - Normal series given a false warning: 1.9% → 6.5%.
- **Detection rules (§3.7):** the IQR fence does most of the work.
  - IQR alone has the best F1 (0.584); combined is level with it (0.576).
  - Z-score alone is the weakest (0.490).
  - Combining the two adds recall but not F1.
- **Anomaly persistence:** on Stage 2's benchmark (one-off spikes plus two-period shifts), accuracy is **71.6% → 88.8%**.
  - Spikes: 59.8% → 95.4%.
  - Shifts: 84.1% → 81.7%.
  - The cost: a shift that starts in the very last period is now called recovering (right 2.2% of the time).

All Stage 3 work is on branch `vonara-nl-to-sql-prototype-stage-3` in three local commits. Nothing has been pushed and `main` is untouched.

## Starting point

| What was measured | Stage 2 result | What it actually meant |
| --- | --- | --- |
| Anomaly detection | Precision 1.00, recall 0.50, F1 0.67 | 6 synthetic series, 12 anomalies; both misses on the seasonal case were structural |
| Seasonal anomalies | Recall 0 | Linear detrending cannot remove a periodic pattern, so seasonal peaks set the fence |
| Rule comparison (§3.7) | Not done | Only adaptive-combined vs static was ever measured |
| Historical vs predictive scoring (§3.11) | Not done | Predictive warnings were never scored against a truth |
| Anomaly persistence | 71.6% (spikes 59.8%, shifts 84.1%) | A naive forecast carried a last-period spike forward, so it was called persistent |

## Work completed

1. **Detection-rule option.** `detect_anomalies(method=...)` takes `COMBINED`, `IQR` or `ZSCORE`, so each rule can be measured on its own. The report names the rule applied, and every flag records which rule raised it.
2. **Labelled anomaly benchmark** (`evaluate_anomalies.py`).
   - **Historical:** 144 series per split, from a factorial grid:
     - length 24 / 36 / 48
     - shape flat / trend / seasonal / trend + seasonal
     - noise 3 / 8 / 15% of level
     - 4 repetitions
   - Each series carries 0–3 injected spikes or dips of 3, 4 or 6σ; a quarter of the series are clean.
   - **Predictive:** 324 series per split with three futures: normal, a level shift lasting through the future, or a one-off spike in the last period. The forecast comes from the production selector.
   - **Truth** does not depend on any detector: a point is anomalous only if an injected event covers it.
   - **Scoring:** precision, recall, F1 and false-positive rate are reported separately for the two dimensions, with recall broken down by magnitude and shape.
   - **Splits:** DEV (seed 2026) for design choices; TEST (seed 2027) reported once with frozen code.
3. **STL seasonal detection space.**
   - **When it applies:** the series has at least three full cycles and an STL seasonal strength of at least 0.40 (Wang, Smith & Hyndman, 2006). Points are then judged against the expected value, trend plus same-phase season.
   - **Design decisions,** each measured on DEV:
     - *Periodic season* (one constant per phase). STL's default 7-point seasonal smoother fitted each phase's 3–4 points almost exactly and absorbed the outliers. With it, 37 of 40 clean series raised a false alarm.
     - *Three cycles, not two.* With two, a spike splits evenly between itself and its partner a cycle away.
     - *Robust location, plain spread.*
       - The robust fit keeps a spike in the remainder (4σ recall 0.83 vs 0.23 for a plain fit).
       - But its remainder is peaked, and its IQR understated the noise (5% of clean points flagged).
       - So the expected value comes from the robust fit and the fence from the plain fit's remainder, widened by √(n / (n − df)).
     - *Strength threshold 0.40:* the best historical F1 on DEV among 0.40, 0.50 and 0.60.
     - *Dropped:* judging the volatility regime on the remainder. It lowered DEV F1.
4. **Forecast screening space.** A non-seasonal forecast (naive, Holt, linear) has no seasonal shape. Comparing it with the seasonal expectation flagged 18% of normal series on DEV, so these forecasts are screened in the level space instead. `predictive_space` records which space was used.
5. **Spike, sustained, unconfirmed.** Each historical anomaly is labelled from its neighbours:
   - `SPIKE`: isolated, and the next period is back in range.
   - `SUSTAINED`: two or more consecutive same-direction anomalies.
   - `UNCONFIRMED`: isolated, in the latest period.
6. **Persistence uses the pattern.**
   - A spike already followed by a normal period is `RECOVERING` (basis `OBSERVED_RETURN`).
   - A sustained run is judged on the forecast (basis `FORECAST`).
   - A single latest anomaly is projected with the same model fitted *without* it (basis `FORECAST_WITHOUT_LATEST_POINT`), and the summary says the verdict is provisional.
   - The benchmark gained a `SHIFT_LAST` case so this trade-off is measured, not hidden.
7. **Wiring.** The pipeline and the what-if engine pass the seasonal period derived from the result's granularity. The what-if re-screen keeps the forecast model, so it is screened in the same space.
8. **Tests.** `test_anomaly.py` has 19 checks covering rules, the seasonal space, the screening space, patterns and persistence.

## Results

### Historical anomalies (TEST, 144 series, 230 injected anomalies)

| Detector | Precision | Recall | F1 | Clean series with a false alarm |
| --- | --- | --- | --- | --- |
| Static (textbook 1.5·IQR / z = 3) | 0.768 | 0.330 | 0.462 | 4 / 33 |
| Stage 2 rule (combined, no STL) | 0.817 | 0.409 | 0.545 | 6 / 33 |
| IQR alone + STL | 0.701 | 0.500 | **0.584** | 11 / 33 |
| Z-score alone + STL | 0.711 | 0.374 | 0.490 | 13 / 33 |
| **Combined + STL (production)** | 0.671 | **0.504** | 0.576 | 14 / 33 |

| F1 by shape (TEST) | Flat | Trend | Seasonal | Trend + seasonal |
| --- | --- | --- | --- | --- |
| Stage 2 rule | 0.828 | 0.596 | 0.231 | 0.197 |
| Combined + STL | 0.822 | 0.596 | **0.382** | **0.396** |

Recall on 6σ anomalies rises from 62.5% to 70.3%, and on 4σ anomalies from 49.4% to 60.5%. Flat and trending series are unchanged: the seasonal space only switches on when a seasonal pattern is present.

### Predictive warnings (TEST, 324 series, horizon 3)

| Detector | Precision | Recall | F1 | Normal / shift / last-spike series warned |
| --- | --- | --- | --- | --- |
| Stage 2 rule | 0.630 | 0.358 | 0.457 | 1.9% / 38.0% / 22.2% |
| **Combined + STL** | 0.581 | **0.420** | **0.487** | 6.5% / 45.4% / 29.6% |

Predictive recall is limited by the forecasts themselves: a warning can only fire if the forecast leaves the normal range. The guarded selector often chooses naive or smoothing models, which project the shifted level only partly.

### Anomaly persistence (`evaluate_strategies.py`, seed 2026)

| Event | Detected | Stage 2 | Stage 3 |
| --- | --- | --- | --- |
| One-off spike in the last period | 87 | 59.8% | **95.4%** |
| Shift over the last two periods | 82 | 84.1% | 81.7% |
| Spike + shift (Stage 2's benchmark) | 169 | 71.6% | **88.8%** |
| Shift starting in the last period (new) | 92 | — | 2.2% |

Across all three event types together, accuracy is 58.2%, below the 65.9% of always answering "persists". That figure reflects the benchmark's mix, not real data: two of the three event types persist by construction.

### Stage 1 anomaly set (`python evaluate.py anomaly`)

The seasonal case goes from recall 0 to 0.50, at the price of 2 false positives. Overall: precision 0.78, recall 0.58 (was 0.50), F1 0.67 (unchanged).

### Regression

All seven test suites pass:

| Suite | Checks |
| --- | --- |
| test_anomaly | 19 |
| test_component | 61 |
| test_strategies | 24 |
| test_forecast_delivery | 42 |
| test_readiness | 23 |
| test_input_adapter | 27 |
| test_response_intent | passes |

The readiness benchmark still gives 85/85.

## What this means for the research claims

- **The proposal's seasonal claim now holds with evidence.** The detector finds anomalies on seasonal series, where Stage 2 could not, on a held-out seed.
- **The adaptive claim needs a precision caveat.** The seasonal space trades precision for recall: 14 of 33 clean held-out series now raise a false alarm, against 6 before. The honest framing is "finds roughly twice as many seasonal anomalies, at the cost of more false alarms", not a free improvement.
- **§3.7 answer:** the IQR fence is the effective rule. The Z-score adds a little recall and no F1, which is consistent with the Z-score being distorted by the outliers it is trying to find. The combination is kept for its recall, and the evidence for it is weak.
- **Spike vs shift:** the gain on spikes is real. The SHIFT_LAST result shows the limit: one observation cannot separate a spike from a fresh shift, and Stage 3 resolves that ambiguity towards "one-off". Which way is cheaper is a property of the real data.

## Limitations and open issues

1. **Synthetic data only.** All anomaly results are on generated series with injected anomalies. There is no real labelled anomaly set; M4 has no anomaly labels.
2. **Precision on seasonal series** is 0.40 held out, and clean-series false alarms rose. A tighter fence in the seasonal space is the obvious next step and would trade some of the recall back.
3. **No significance test** was run on the anomaly comparisons. The DEV and TEST splits agree in direction, but per-series paired tests have not been done.
4. **Short seasonal series** (fewer than three cycles, e.g. 24 months) still use the Stage 2 rule. This is deliberate, since two cycles cannot separate a spike from the season, but it means 24-month seasonal results are unchanged.
5. **The latest-period trade-off** (SHIFT_LAST 2.2%) needs real base rates to settle.
6. **Not run:** the MySQL harness (still needs `MYSQL_ADMIN_PASSWORD`), and the M4 forecasting benchmark. The forecasting code was not changed in Stage 3, so its numbers stand from Stage 2.

## Commits on `vonara-nl-to-sql-prototype-stage-3` (local, not pushed)

1. `5f3b58f` — labelled anomaly benchmark and detection-rule option (baseline numbers)
2. `cac1e64` — STL seasonal detection space and spike/shift patterns
3. benchmark re-runs, documentation and this report

## Next stage

Stage 4: the what-if parser (the "unless" bug) and measuring the LLM-narration verifier.
