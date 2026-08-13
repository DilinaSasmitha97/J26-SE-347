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
| 3 | Mathematical claim verification pipeline | `summarization.py` | ✅ working | grounding rate |
| 4 | Intent-to-prediction mapping algorithm | `prediction.INTENT_STRATEGY_MAP` | ✅ working | strategy trace |
| 5 | Data readiness feasibility classifier | `assess_readiness` | ⚠️ working, gate too loose | open issue #1 |
| 6 | Dual-signal model selection algorithm | `select_model` | ✅ working | 100 % agreement |
| 7 | Lightweight confidence-bounded forecasting | `generate_forecast` | ⚠️ working, below baseline on mean RMSE | open issue #1 |
| 8 | Dual-dimension adaptive anomaly detection | `anomaly.py` | ✅ working | recall 0.25 → 0.50 |
| 9 | NL-driven what-if simulation engine | `whatif.py` | ✅ working | scenario deltas |
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

### Phase 2 — Methodological hardening (next)

- [ ] **#1** Replace the CV noise gate with a rolling-origin random-walk test
- [ ] **#2** STL decomposition for seasonal anomaly detection
- [ ] **#3** Independent/blind intent test split + relabelled Spider/BIRD subset
- [ ] Enable LLM narration; measure verifier rejection rate
- [ ] Rolling-origin backtesting to replace the single 3-period holdout
- [ ] Interval calibration check: does the 95 % band actually contain 95 %?

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
