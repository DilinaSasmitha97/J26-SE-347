# Component 4 — Delivery Roadmap

**Member:** Wijethunge W M V (IT23256750) · **Project:** J26-SE-347
**Sub-objective (TAF §9):** engineer an intent-driven adaptive visualization,
presentation and prediction layer that classifies query semantic intent and
result cardinality to generate structured visualizations, confidence-bounded
temporal forecasts, grounded unified analytical summaries, and interactive
what-if scenario simulations.

---

## Research contributions and their status

| # | Contribution (TAF) | Implemented in | Status | Validated by |
|---|---|---|---|---|
| 1 | Semantic intent classification for visualization driving | `query_analyzer.py` | ✅ working | intent accuracy suite |
| 2 | Vega-Lite grammar extension for predictive overlays | `visualization.py` | ✅ working | 4 rules, layer audit |
| 3 | Mathematical claim verification pipeline | `summarization.py` | ✅ Stage 4: precision-aware verifier; live LLM narration measured | fault injection: 96.7–100 % of corrupted numbers rejected, 0 % of correct rewrites; live 12/12 verified |
| 4 | Intent-to-prediction mapping algorithm | `INTENT_STRATEGY_MAP` + `strategies.py` | ✅ Stage 2: all four strategies executed | strategy benchmark |
| 5 | Data readiness feasibility classifier | `assess_readiness` | ✅ Stage 2: three-level decision, ADF + KPSS, completeness, forecastability | held-out M4 precision 0.90 (target 0.80); 85/85 labelled cases |
| 6 | Dual-signal model selection algorithm | `select_model` + benchmark guard | ⚠️ best on held-out M4 but not significantly better than naive (p = 0.81); rules alone worse (p = 0.001) | rolling-origin benchmark |
| 7 | Lightweight confidence-bounded forecasting | `project_series` | ✅ 94.5 % coverage of nominal 95 % on held-out M4 | rolling-origin benchmark |
| 8 | Dual-dimension adaptive anomaly detection | `anomaly.py` | ⚠️ Stage 3: STL seasonal space, spike/shift patterns; precision falls 0.82 → 0.67 | held-out labelled benchmark: F1 0.545 → 0.576, seasonal F1 0.23 → 0.38; persistence 71.6 % → 88.8 % |
| 9 | NL-driven what-if simulation engine | `whatif.py` + `scenario_language.py` | ⚠️ Stage 4: one shared parser; refuses what it cannot read | 94 labelled phrasings: ~50 % → 100 % correct, 0 wrong simulations (author-written set) |
| 10 | Unified temporal summarization framework | `summarization.py` | ✅ working | 100 % grounded |

Legend: ✅ implemented and validated · ⚠️ implemented, known limitation documented

---

## Phase plan

### Phase 1 — Prototype ✅ COMPLETE (this submission)

- [x] Closed intent taxonomy (9 labels) and marker lexicon
- [x] Hybrid rule + LLM query understanding with explicit arbitration
- [x] Schema binding with fuzzy matching and hallucination stripping
- [x] Result-set profiler: column roles, temporal inference, granularity
- [x] Adaptive encoding selection with cardinality overrides
- [x] Vega-Lite v5 emission + 4 predictive extension rules
- [x] Prediction Stages 1–6
- [x] Claim ledger, verifier, unified temporal summary (Stage 7)
- [x] FastAPI gateway (3 endpoints) + intent-informed cache
- [x] Synthetic generators with ground-truth labels
- [x] Evaluation harness: 4 metric families

### Phase 2 — Stage 2: prediction core (branch `vonara-nl-to-sql-prototype-stage-2`)

- [x] Member 2 input adapter (real columnar format) + synthetic MySQL fixture harness
      *(written; not yet run against MySQL — needs `MYSQL_ADMIN_PASSWORD`)*
- [x] Requested forecasts delivered in every response shape (`forecast_notice`)
- [x] **#1** Forecastability gate replaces the CV/R² rule
- [x] Rolling-origin backtesting, naive + seasonal-naive baselines, MASE, sMAPE,
      relative RMSE, Wilcoxon tests, 95 % coverage per horizon
- [x] Benchmark: 66 synthetic + 100 M4 monthly (seed 2026) as development data,
      100 more M4 monthly (seed 2027, disjoint) as the held-out test
- [x] Benchmark guard on model selection; damped-trend Holt; SARIMA identifiability
- [x] Three missing strategies implemented and benchmarked; result layouts
      (grouped results are no longer analysed as one mixed series)

- [x] Three-level readiness decision with reason codes; ADF + KPSS evidence;
      unreadable-value and empty-period checks with disclosed interpolation;
      business-day calendars; readiness benchmark on 85 labelled cases
- [x] SARIMA airline order and residual-based bands (held-out coverage 94.5 %)
- [x] Gate threshold chosen on development data; held-out precision 0.90
- [x] Per-horizon MAE / RMSE / MASE, per-regime results, software versions
- [x] Fresh held-out M4 sample (seed 2027, disjoint from development)

Carried to later stages:

- [ ] Selection that beats naive significantly (Stage 2 shows "matches and is
      calibrated"); in-history validation over all candidates is the candidate
- [x] Spike vs level-shift distinction in anomaly persistence (Stage 3)

### Phase 2c — Stage 3: anomaly engine (branch `vonara-nl-to-sql-prototype-stage-3`)

- [x] Labelled anomaly benchmark (`evaluate_anomalies.py`): DEV / TEST seeds,
      historical and predictive dimensions scored separately (§3.11)
- [x] IQR alone vs Z-score alone vs combined vs static (§3.7)
- [x] **#2** STL seasonal detection space (robust location, plain-fit spread,
      degrees-of-freedom correction; ≥ 3 cycles, strength ≥ 0.40 chosen on DEV)
- [x] Forecast points screened in the space their model produced them in
- [x] SPIKE / SUSTAINED / UNCONFIRMED patterns; persistence uses them

Carried to later stages:

- [ ] Anomaly precision on seasonal series (0.40 held out) and the higher
      false-alarm rate on clean series (14/33 vs 6/33)
- [ ] A shift that starts in the latest period is called recovering (2.2 %);
      needs real-data base rates to choose the trade-off
- [ ] Validation of the anomaly engine on real (non-synthetic) labelled data

### Phase 2d — Stage 4: what-if parser and summary verifier (branch `vonara-nl-to-sql-prototype-stage-4`)

- [x] One scenario parser for both routes (`scenario_language.py`): whole-word
      directions ("unless" is no longer "less"), refusals for negated,
      multi-change, ranged and absolute scenarios; targets ("to 80%"),
      multipliers, signs; ramp wording kept on the question route
- [x] A magnitude with no direction is refused, no longer simulated as a cut
- [x] Labelled what-if benchmark (`evaluate_whatif.py`, 94 phrasings, DEV/TEST)
- [x] Precision-aware summary verifier: scale words, ranges, dates, numbers
      written as words; fault-injection benchmark (`evaluate_verifier.py`)
- [x] Live LLM narration measured (Groq, 12 scenarios)

Carried to later stages:

- [ ] What-if phrasings written by someone other than the author
- [ ] Verifier blind spots: two correct numbers swapped, a direction word
      reversed ("increased" → "decreased")
- [ ] Live narration on more scenarios and a second model; no rejection was
      observed in 12, so the rejection path is evidenced by fault injection only

### Phase 2b — remaining hardening

- [ ] **#3** Independent/blind intent test split + relabelled Spider/BIRD subset

### Phase 3 — Integration

- [ ] Consume Member 2's real masked result sets (replace synthetic rows)
- [ ] Consume Member 1's `predicted_sql` to sharpen semantic-role extraction
- [ ] Honour Member 3's `denied_tables` and role scoping end to end *(already
      wired; needs testing against the real access-control service)*
- [ ] End-to-end latency budget across all four components

### Phase 4 — Client & evaluation

- [ ] React renderer for the emitted Vega-Lite grammar
- [ ] Interactive what-if control bound to `/api/v4/simulate`
- [ ] Usability evaluation on the adaptive-vs-static presentation question
- [ ] Final results chapter

---

## Dependencies on other components

| Need | From | Current substitute | Blocking? |
|---|---|---|---|
| Masked result rows | Member 2 | `synthetic_data.py` | No — contract is agreed |
| `query_intent` hint | Member 1 | derived independently in Part 1 | No |
| Tenant/role context | Member 3 | `security_context` stub | No — denylist already enforced |
| Schema metadata | Member 1 | `SCHEMA_DDL` constant | No |

The layer is deliberately runnable in isolation: nothing in Phase 1 or 2 is
gated on another member's delivery.

---

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Intent accuracy collapses on an independent test set | Headline claim weakens | Expected; already flagged. Hybrid LLM path exists as the remedy |
| Forecasting never beats naive baselines on small data | Contribution #7 weakens | Reframe around *calibration* and *refusal* rather than raw accuracy — knowing when not to forecast is itself the contribution |
| Real tenant result sets are shorter than 12 points | Most forecasts refused | Already handled by the readiness gate; measure the refusal rate as a result |
| LLM cost/latency in hybrid mode | Slower responses | Deterministic mode is the default; LLM is opt-in per request |
