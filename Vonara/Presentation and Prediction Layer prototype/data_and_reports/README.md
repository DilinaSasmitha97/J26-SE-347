# Component 4 — Presentation & Prediction Layer

**Project:** J26-SE-347 — Secure Multi-Tenant Natural Language Interface for Database Querying
**Member:** Wijethunge W M V (IT23256750)
**Research group:** CoEAI — Centre of Excellence for AI, SLIIT

The final layer of the middleware. It receives a PII-masked result set from
Member 2's AST security gate and turns it into an intent-appropriate
visualization, a confidence-bounded forecast, dual-dimension anomaly warnings,
and a mathematically verified narrative summary.

---

## The four parts

```
   NL query + schema (+ tenant context)
              │
              ▼
   ┌──────────────────────────────────┐
   │ PART 1  Query Understanding      │  query_analyzer.py
   │  intent · prediction demand ·    │  → the comprehensive JSON contract
   │  schema binding · semantic roles │
   └──────────────┬───────────────────┘
                  │  (masked rows arrive from Member 2)
                  ▼
   ┌──────────────────────────────────┐
   │ PART 2  Adaptive Visualization   │  visualization.py
   │  intent × result shape → chart   │
   └──────────────┬───────────────────┘
                  ▼
   ┌──────────────────────────────────┐
   │ PART 4  Prediction (Stages 1-6)  │  prediction.py · anomaly.py · whatif.py
   │  1 intent→strategy  2 readiness  │
   │  3 model selection  4 forecast   │
   │  5 anomalies        6 what-if    │
   └──────────────┬───────────────────┘
                  ▼
   ┌──────────────────────────────────┐
   │ PART 3  Unified Summarization    │  summarization.py   (Stage 7)
   │  verified claims → narrative     │
   └──────────────┬───────────────────┘
                  ▼
   ┌──────────────────────────────────┐
   │ PART 5  Response Shaping         │  response_intent.py
   │  which SHAPE the reply takes ·   │  response_renderer.py
   │  result guardrails · blocks      │
   └──────────────┬───────────────────┘
                  ▼
      comprehensive JSON envelope → React client
```

Prediction runs **before** summarization: Stage 7 must narrate forecast and
anomaly claims alongside historical ones, which is what makes the summary
*unified* across both temporal dimensions.

Response shaping runs **last**, because it is the only stage that sees
everything at once — the pre-execution verdict, the real result set, and the
blocks the other parts produced.

---

## Quick start

```bash
pip install -r requirements.txt          # pandas, numpy, statsmodels, ...
cp .env.example .env                     # optional — only needed for LLM mode

python main.py analyze "Show my monthly software expenses and predict the next 3 months"
python main.py demo finance_seasonal     # full pipeline over a synthetic scenario
python main.py showcase                  # four contrasting cases side by side
python main.py scenarios                 # list the 12 benchmark scenarios
python evaluate.py                       # all research metrics
```

**No API key is required.** With `LLM_PROVIDER` unset the layer runs in
deterministic mode and every evaluation number reproduces exactly. An API key
only enables the hybrid path described below.

---

## Part 1 — the comprehensive JSON contract

`query_analyzer.analyze()` is the headline deliverable. Given a question, a
schema, and optional tenant context, it returns a single machine-checkable
object that every downstream stage consumes:

```jsonc
{
  "intent": {
    "primary_intent": "TREND_ANALYSIS",     // one of 9 closed labels
    "secondary_intents": ["KPI_SINGLE_VALUE"],
    "confidence": 0.75,
    "intent_source": "HYBRID",              // LLM | RULE | HYBRID
    "rationale": "Matched 'total' ... Promoted from KPI_SINGLE_VALUE ..."
  },
  "prediction_request": {
    "prediction_required": true,
    "prediction_trigger": "EXPLICIT",       // EXPLICIT | IMPLICIT | NONE
    "horizon": {"value": 3, "unit": "MONTH", "source": "EXPLICIT"},
    "what_if": {"present": false, "direction": "", "magnitude_pct": 0}
  },
  "schema_binding": {
    "affected_tables":  [{"table": "expenses", "role": "FACT", "confidence": 0.95}],
    "affected_columns": [{"table": "expenses", "column": "amount", "role": "MEASURE"}],
    "unresolved_terms": ["software"]
  },
  "semantic_roles": {
    "metrics": [{"column": "amount", "aggregation": "SUM"}],
    "dimensions": [], "temporal_field": "invoice_date",
    "temporal_granularity": "MONTH", "limit": 0
  },
  "visualization_hint": {"recommended_chart": "line", "alternatives": ["area", "bar"]},
  "governance": {"pii_columns_referenced": [], "read_only": true},
  "warnings": ["UNRESOLVED_TERMS"],
  "metadata": {"mode": "RULE_ONLY", "total_tokens": 0, "execution_time_ms": 3.96}
}
```

### Hybrid architecture, deterministic-first

Two analysers run independently and are merged under an explicit policy:

| | Rule engine | LLM engine |
|---|---|---|
| Method | weighted marker lexicon + fuzzy schema binding | structured JSON extraction |
| Cost | 0 tokens, ~4 ms | 1 call, ~300–400 tokens |
| Strength | reproducible, auditable, offline | paraphrase, ellipsis, multi-clause |

Arbitration rules (`query_analyzer._merge`):

- **Intent** — the LLM wins only when confident (≥ 0.60) *and* in-vocabulary.
- **Schema binding** — union, but every LLM-supplied table/column is checked
  against the real schema first; invented ones are stripped and reported as
  `LLM_HALLUCINATED_BINDINGS_STRIPPED`.
- **Prediction flag** — logical OR (missing a wanted forecast is the worse error;
  an unwanted one is discarded by the readiness gate anyway).
- **Security fields** — rule engine only. PII flags and injection markers are
  never delegated to a model.

The result is that the LLM can improve the answer but cannot corrupt it, and
the component still works with no network access at all.

---

## Part 2 — adaptive visualization

`select_encoding()` resolves the chart from **intent × realised result shape**,
not intent alone. The same `TREND_ANALYSIS` becomes:

| result shape | chart | why |
|---|---|---|
| 24 monthly points | `line` | ordered periods |
| 3 periods | `bar` | too few points to read as a line |
| 1 row | `kpi_card` | no axis exists |
| 12 categories, PROPORTION | `bar` | beyond 8 slices a donut is unreadable |

Every override is recorded in `_meta.adapted_from_intent_default`, so
adaptation frequency is auditable rather than asserted.

### Predictive Visualization Grammar Extension

`extend_with_forecast()` layers prediction onto **any** base chart through four
composable rules over the same Vega-Lite grammar:

| rule | mark | carries |
|---|---|---|
| `R1_FORECAST_MEAN` | dashed line | point forecasts |
| `R2_CONFIDENCE_BAND` | area | lower/upper bounds |
| `R3_ANOMALY_MARKERS` | point + rule | historical and predicted breaches |
| `R4_SCENARIO_OVERLAY` | dashed line | what-if path |

Because each rule emits an independent layer keyed to the same x/y fields, the
base chart never needs to know prediction exists. Charts with no continuous
axis (pie, scatter) declare the extension undefined rather than emitting a
nonsensical layer.

---

## Part 4 — the prediction stages

| Stage | Module | Contribution |
|---|---|---|
| 1 Intent → strategy | `prediction.INTENT_STRATEGY_MAP` | model family becomes a function of query semantics, not a default |
| 1 Strategy execution | `strategies.py` | each strategy answered for real: per-category **trajectory** (who leads next), **distribution shift** (shares / quartiles / percentile position), **anomaly persistence** (recovering / persisting / worsening) |
| 2 Data readiness | `assess_readiness` | **READY / READY_WITH_WARNING / NOT_READY** with reason codes: temporal validity, unreadable values (> 20 % refuses), empty periods (≤ 25 % interpolated and disclosed, more refuses), sufficiency, near-constant and constant series, ADF + KPSS stationarity evidence, and a **forecastability test** on the series' own history (best one-step error ≤ 20 % of level) replacing the CV/R² rule that refused nothing |
| 3 Model selection | `select_model` | **dual-signal** rules (intent × ADF, seasonal ACF, trend R², CV), then a **benchmark guard**: the choice must beat naive / seasonal naive on the series' own history or the benchmark is used |
| 4 Forecasting | `project_series` / `generate_forecast` | one code path for live requests and backtests; residual-based intervals widening as `z·σ·√h·small_sample_penalty` for every model (94.5 % coverage on held-out M4); damped-trend Holt; airline-order SARIMA, only with two full cycles |

Single-series stages run only when the result is one row per period. The
profiler classifies every result's **layout** — `SINGLE`, `GROUPED` (month ×
region: one series per category, forecast separately), `EVENTS` (raw rows) or
`CROSS_SECTIONAL` — because treating a grouped result as one series
interleaves the categories and every per-period statistic computed on it is
wrong.
| 5 Anomaly detection | `anomaly.detect_anomalies` | adaptive IQR/Z thresholds, applied to past **and** forecast, in the raw, detrended or **STL seasonal** space; each historical anomaly labelled **SPIKE / SUSTAINED / UNCONFIRMED** |
| 6 What-if | `whatif.simulate` + `scenario_language.parse` | NL scenario → bounded parametric perturbation, all outputs regenerate; one parser for the question and the simulate box, refusing negated, ranged, absolute or multi-change scenarios with a reason code |

Two design decisions worth defending in the report:

**Horizon clamping.** The forecast never projects further than half the
observed span. Extrapolating 12 periods from 8 observations is not a forecast.

**Detrended anomaly detection.** On a growing series the raw IQR fence spans the
entire growth range, so real local spikes sit comfortably inside it. When trend
R² ≥ 0.50 the detector measures dispersion on residuals instead. This is the
single change that took anomaly recall from 0.25 to 0.50 (see below), and it is
why the threshold is genuinely *adaptive* rather than merely rescaled.

**Seasonal anomaly detection (Stage 3).** Linear detrending cannot remove a
periodic pattern, so on seasonal series the seasonal peaks set the fence. With
at least three full cycles and an STL seasonal strength ≥ 0.40, points are
judged against a robust periodic STL expectation (trend + same-phase season)
and the fence is built from the plain STL remainder, widened by
√(n / (n − df)). Forecasts from non-seasonal models are screened in the level
space, so a naive forecast is not flagged for lacking a seasonal shape.

**Spike vs level shift (Stage 3).** A spike and the start of a shift look the
same when they happen. Each anomaly is labelled from its neighbours — SPIKE,
SUSTAINED, or UNCONFIRMED when it is isolated in the latest period — and
anomaly persistence uses the label: an observed return is RECOVERING, a
sustained run is judged on the forecast, and a single latest anomaly is
projected without itself (stated as provisional in the summary).

---

## Part 3 / Stage 7 — grounded summarization

The pipeline never asks a model "what does this data say". It computes every
statement first as a `Claim` carrying its value, source and derivation:

```
[H3    ] HISTORICAL PEAK       value=6,350.63   <- max of the series
[F2.1  ] PREDICTIVE FORECAST   value=6,454.33   <- point forecast h=1, half-width 414.20
[A1.2  ] ANOMALY    HISTORICAL value=14,581.65  <- z=2.33, detected by IQR
```

Claims are then either rendered deterministically (default) or narrated by an
LLM under `verify_summary()`, which rejects the narration entirely if any number
in it fails to trace back to a claim. There is no partial acceptance: a summary
with one invented figure is not 90 % trustworthy.

---

## Part 5 — response shaping

Part 1 classifies *what the user is asking about*. Part 5 classifies *what shape
the reply takes*, which is a genuinely independent question: "what was our
highest invoice" (`RANKING`) and "how many customers" (`KPI_SINGLE_VALUE`) are
different analytical intents that both want one number, while "revenue by month"
(`TREND_ANALYSIS`) and "revenue by region" (`COMPARISON`) both want a chart.

Five shapes, closed set, each defined *as* its block list:

| Response intent | Fires when | Blocks |
|---|---|---|
| `SINGLE_ANSWER` | one value or one record — highest, total, "how many", "who is the top" | `ANSWER` |
| `SHORT_SUMMARY` | a few sentences — "summarise", "briefly", "how did X do" | `SUMMARY` |
| `TABLE_CONTENT` | the dataset itself — "list all", "every record", "export" | `TABLE` |
| `CHART` | a visual reading — "chart/graph/plot", or a trend, comparison, share, distribution | `CHART` |
| `MIXED_SUMMARY` | a full report — "deep dive", "dashboard", or two formats named at once | `SUMMARY` + `TABLE` + `CHART` |

There is deliberately **no `UNKNOWN`**: a presentation layer must always render
something, so low confidence is carried in the score and a warning, never in an
unrenderable label. The renderer emits exactly the blocks the intent declares
and nothing else, which is what makes the taxonomy testable end to end.

Three stages. A and B run **before** SQL, so the client knows what surface to
prepare; C runs after, and repairs the verdict against the rows that actually
came back:

```
"What was our highest monthly revenue?"
  Stage A  SINGLE_ANSWER (0.97, decisive superlative marker)
  ...SQL returns 6 monthly rows, not one maximum...
  Stage C  G1 scalar contradicted: result is 6x2, not one value -> TABLE_CONTENT
```

Presenting one of those six rows as *the* answer would be a lie about the data.
Guardrails fire only on a contradiction the result set proves — never on a
second guess at the language — and every repair is recorded in
`guardrails_applied` alongside the intent it replaced.

Full rule set, the lexical-repair design, and the evaluation method are in
`response_intent_design.md`.

---

## Measured results

Reproduce with `python evaluate.py` (deterministic mode, fixed seeds).

**1. Intent classification** — 38 held-out cases

| metric | value |
|---|---|
| Intent accuracy | **100.0 %** |
| Macro F1 | 1.0000 |
| Prediction-flag accuracy | 100.0 % |
| Table-binding recall | 94.7 % |
| Security-warning recall | 100.0 % |

> ⚠️ **Read this number carefully.** The test set was authored by the same
> person who wrote the marker lexicon, so 100 % measures *coverage of the cases
> we thought of*, not generalisation. It is a regression baseline, not evidence
> of real-world accuracy. See `baseline_report.md` for the plan to fix this.

**1b. Response-intent classification** — 125 development + 50 hold-out inputs

Reproduce with `python evaluate_response_intent.py` and
`python evaluate_response_intent.py --dataset response_intent_holdout.csv`.

| corpus | accuracy | well-formed | degraded | macro F1 |
|---|---|---|---|---|
| Development (tuned on) | 100.0 % | 100.0 % (77/77) | 100.0 % (48/48) | 1.00 |
| Hold-out (not tuned on) | 100.0 % | 100.0 % (32/32) | 100.0 % (18/18) | 1.00 |

> ⚠️ Same caveat as above, twice over. The development figure is a *fit*
> statistic — the rules were iterated against that corpus until it passed, and
> it started at 80.8 %. The hold-out corpus was written by the same author, so
> it shares phrasing priors real users will not have. Read 100 % as "no known
> failure mode across 175 inputs", not as an expected field accuracy.
> Full method and limits: `response_intent_design.md`.

The stress corpus (`response_intent_stress.csv`, 45 deliberately hard
inputs) scores **57.8 %** (26/45) — the realistic floor until a blind test set
exists.

Both runs write `<dataset>_predictions.csv` — every input with its expected
label, the engine's actual verdict, `CORRECT`/`WRONG`, confidence and rationale.
That file is the record of the current state; diff it after any lexicon change.

**2. Prediction accuracy** — rolling origin, `python evaluate_forecasting.py`

266 series. Development: 66 synthetic series (factorial grid of length × noise ×
seasonality × trend, plus 6 near-constant) and **M4_DEV, 100 monthly series
randomly sampled (seed 2026) from the M4 competition dataset** (100,000 series
in total, 48,000 monthly). Held-out test: **M4_TEST, 100 further monthly series
(seed 2027) drawn from the 47,900 not in M4_DEV**. All truncated to their last
36 observations; 4 origins × 3-step horizon per series; every forecast uses only
data before its origin. Design changes were checked on development data only;
M4_TEST was evaluated once with the frozen code. Full tables, per horizon and
per data regime: `forecast_benchmark.md`.

| | MASE (mean / median) | sMAPE | rel. RMSE vs naive | 95 % coverage |
|---|---|---|---|---|
| M4_TEST — naive | 1.491 / 1.231 | 10.8 % | 1.000 | 95.0 % |
| M4_TEST — SARIMA (airline) | 1.521 / 1.295 | 11.1 % | 0.965 | 95.0 % |
| M4_TEST — adaptive, unguarded | 1.897 / 1.356 | 11.2 % | 1.070 | 92.7 % |
| M4_TEST — **adaptive + guard** | **1.443 / 1.234** | **9.5 %** | **0.938** | **94.5 %** |

> On held-out data the guarded selector is the most accurate approach on every
> summary measure and its 95 % bands hold 94.5 % of outcomes (95 / 95 / 94 % at
> h = 1 / 2 / 3). It is significantly better than the unguarded rules
> (Wilcoxon p < 0.0001) but **not significantly better than naive** (p = 0.81):
> the honest claim is "matches the benchmark and is calibrated", not "beats it".
> The unguarded dual-signal rules are significantly *worse* than naive
> (p = 0.001), which is why the guard is part of the method.

SARIMA now uses the airline order (0,1,1)(0,1,1)₁₂ — chosen over per-series AICc
selection (mean MASE 2.03) and the Stage 1 order (1,1,1)(1,1,1)₁₂ (7.04, 12
blow-ups) by backtest on development data — and residual-based bands instead of
statsmodels' parameter-exact intervals (which covered 67–75 %).

**2b. Readiness** — `python evaluate_forecasting.py`, `python evaluate_readiness.py`

| Gate 3 (UNRELIABLE = window sMAPE > 20 %) | Refusal rate | sMAPE accepted | sMAPE refused | Precision | Recall |
|---|---|---|---|---|---|
| Old CV/R² rule (all groups) | 0 % | — | — | — | 0.00 |
| Forecastability, M4_DEV | 6.2 % | 8.4 % | 40.9 % | 0.68 | 0.29 |
| Forecastability, **M4_TEST (held out)** | 5.0 % | 7.1 % | 53.7 % | **0.90** | 0.35 |

The threshold (20 % of level) is chosen on development data as the best F1 among
thresholds whose refusals are right ≥ 80 % of the time; on the held-out sample
90 % of refusals were right. The full decision is three-level — READY,
READY_WITH_WARNING, NOT_READY — with reason codes, ADF + KPSS stationarity
evidence, unreadable-value and empty-period checks (gaps ≤ 25 % are filled by
linear interpolation and disclosed; business-day calendars are recognised). On
85 labelled result sets (17 case types × 5 seeds) it gives the defined decision
in 85/85 cases with 0 false-ready decisions (`readiness_benchmark.md`); the cases
are clear-cut by construction, so this checks the policy is implemented, while
the gate's precision on M4 is the evidence on borderline data. When ADF and KPSS
disagree on M4_TEST, 29.0 % of forecasts are unreliable against 7.5–15.5 % for
the other verdicts, which is why disagreement is shown as a caution.

**2c. Strategies** — `python evaluate_strategies.py` (synthetic, known truth)

| Strategy question | Result | Naive answer |
|---|---|---|
| Leader next period (200 sets × 4 categories) | 90.0 % | 88.0 % (current leader stays) |
| …in the 24 sets where the leader changes | 29.2 % | 0 % |
| …when the strategy calls the lead "clear" (88 sets) | **100 %** | — |
| Share error next period | **1.62 pp** (p = 0.003) | 1.74 pp (shares persist) |
| Anomaly persistence, spike + shift (169 events, Stage 2 → Stage 3) | 71.6 % → **88.8 %** | — |
| …one-off spikes | 59.8 % → **95.4 %** | — |
| …level shifts over the last two periods | 84.1 % → 81.7 % | — |
| …shift starting in the very last period (new case, 92 events) | **2.2 %** | — |

Stage 3 stops a latest-period spike being carried forward by a naive model.
The cost is the new SHIFT_LAST case: a shift that has lasted one period is the
same single point as a spike, and is now called recovering. Which error is
cheaper depends on how often one-off spikes outnumber fresh shifts in real
data — unknown until Member 2's real result sets are available.

**3. Anomaly detection** — `python evaluate_anomalies.py` (Stage 3 benchmark)

144 labelled series per split (length 24/36/48 × flat/trend/seasonal/
trend+seasonal × noise 3/8/15 % × 4), 0–3 injected spikes or dips of 3/4/6 σ;
324 predictive series (normal / shift / last-period spike). Designed on DEV
(seed 2026); TEST (seed 2027) reported with frozen code. Full tables:
`anomaly_benchmark.md`.

| TEST, historical | Precision | Recall | F1 | Seasonal F1 | Trend+seasonal F1 |
|---|---|---|---|---|---|
| Static (textbook) | 0.768 | 0.330 | 0.462 | 0.381 | 0.192 |
| Stage 2 rule (no STL) | 0.817 | 0.409 | 0.545 | 0.231 | 0.197 |
| IQR alone (+ STL) | 0.701 | 0.500 | **0.584** | 0.400 | 0.409 |
| Z-score alone (+ STL) | 0.711 | 0.374 | 0.490 | 0.375 | 0.345 |
| **Combined (+ STL)** | 0.671 | **0.504** | 0.576 | 0.382 | 0.396 |

| TEST, predictive | Precision | Recall | F1 | Normal series warned |
|---|---|---|---|---|
| Stage 2 rule (no STL) | 0.630 | 0.358 | 0.457 | 1.9 % |
| **Combined (+ STL)** | 0.581 | 0.420 | **0.487** | 6.5 % |

The STL space roughly doubles F1 on seasonal and trend+seasonal series and
raises recall overall, at a cost in precision (0.82 → 0.67). Of the two rules,
the IQR fence carries the detection: Z-score alone is weakest, and combining
the two adds recall but not F1 on held-out data. On the 6-case Stage 1 set
(`python evaluate.py anomaly`) the seasonal case goes from recall 0 to 0.50.

**4. Summary grounding** — 415 numbers across 12 summaries: **100 % traceable**
(465 before Stage 4, when each ISO date was read as three numbers).

**5. What-if parsing (Stage 4)** — `python evaluate_whatif.py`, 94 labelled
phrasings (64 DEV, 30 TEST) including substring traps, negations, two changes,
ranges, absolute amounts, targets and multipliers. Full table:
`whatif_benchmark.md`.

| Route | Stage 3 correct | Stage 3 wrong simulations | Stage 4 correct | Stage 4 wrong simulations |
|---|---|---|---|---|
| Question, TEST | 15/30 | 12 | **30/30** | **0** |
| Simulate box, TEST | 14/30 | 7 | **30/30** | **0** |
| Question, DEV | 29/59 | 22 | 59/59 | 0 |
| Simulate box, DEV | 33/64 | 18 | 64/64 | 0 |

The cases and the parser's word lists are by the same author, so 100 % shows
the known phrasing types are covered, not that real users' wording is.

**6. Summary verifier (Stage 4)** — `python evaluate_verifier.py`, fault
injection on the 12 scenarios' claims. Full table: `verifier_benchmark.md`.

| | Stage 3 (within 2 % of any claim number) | Stage 4 (precision-aware) |
|---|---|---|
| Correct rewrites wrongly rejected: "48.3k" / "6,040-6,869" / reworded dates | 92 % / 100 % / 75 % | **0 % / 0 % / 0 %** |
| Corrupted numbers caught: off by 5 % / 10 % / 25 % | 48 % / 67 % / 68 % | **98 % / 100 % / 100 %** |
| Digits transposed / invented value / invented word number | 58 % / 97 % / 0 % | **100 % / 97 % / 98 %** |
| Blind spots: two numbers swapped / "increased" → "decreased" | 8 % / 0 % | 8 % / 0 % |

Live narration (`--live 12`, Groq `openai/gpt-oss-120b`): 12 of 12 verified and
shown; none rejected. The rejection path is therefore evidenced by fault
injection, not by an observed LLM error.

**7. Intent classification on questions the author did not write (Stage 5)**
— `python evaluate_spider_intent.py`. The 1,032 Spider dev questions (Yu et
al., 2018), labelled from their gold SQL by fixed rules frozen before the
classifier ran, split by database: DEV (531) for changes, TEST (501) reported
once. Full tables: `spider_intent_benchmark.md`.

| Spider TEST (held out) | Stage 4 | Stage 5 |
|---|---|---|
| Analytical intent | 45.1 % (28 % no intent at all) | **88.2 %** (p < 10⁻⁵⁰) |
| Response shape | 85.6 % | **89.0 %** (p = 0.012) |
| Multi-row questions read as one value | 16.7 % | 11.2 % |
| ...with `LIMIT 1` requested, so rows would be lost | 16.7 % | **5.8 %** |

McNemar exact tests on the same 501 questions. The author-written sets stay
at 100 % (intent 48/48, response shape 125/125 and 50/50); the response-shape
stress set rises from 26/45 to 42/45. A scalar forecast question ("how much
will I spend next month") is now answered by the projected figure and its
range instead of the history table.

SQL-derived labels cover only what Spider asks: there are no requests for
summaries, reports or forecasts in it, so those shapes are tested only by the
author-written sets.

---

## Integration

| Endpoint | When | Purpose |
|---|---|---|
| `POST /api/v4/analyze` | **before** SQL generation | intent, affected tables, prediction demand |
| `POST /api/v4/present` | **after** Member 2 masks rows | full pipeline |
| `POST /api/v4/simulate` | interactive | re-run a what-if without re-querying the DB |
| `GET /api/v4/health` | — | liveness + capability report |

```bash
uvicorn api:app --reload --port 8004
```

See `team_interface_contract.md` for full payloads and the upstream contract
this layer depends on.

---

## Files

| File | Role |
|---|---|
| `query_analyzer.py` | **Part 1** — hybrid intent + schema binding engine |
| `response_intent.py` | **Part 5** — response-shape classifier + result guardrails |
| `response_renderer.py` | **Part 5** — block assembly, enforces the intent↔blocks contract |
| `visualization.py` | **Part 2** — encoding selection + grammar extension |
| `prediction.py` | **Part 4** — Stages 1–4 |
| `anomaly.py` | **Part 4** — Stage 5 |
| `whatif.py` | **Part 4** — Stage 6 |
| `summarization.py` | **Part 3** — Stage 7, claims + verifier |
| `pipeline.py` | orchestrator, intent-informed cache |
| `schemas.py` | closed taxonomies + output contract |
| `result_profiler.py` | result-set typing and temporal inference |
| `prompts.py` | LLM prompt templates |
| `llm.py` | provider transport, JSON-mode + repair parsing |
| `api.py` | FastAPI gateway |
| `main.py` | CLI demo harness |
| `evaluate.py` | research metrics (intent, single-holdout forecast, anomaly, grounding) |
| `evaluate_forecasting.py` | rolling-origin forecasting benchmark, synthetic + M4, gate evaluation |
| `evaluate_strategies.py` | Stage 1 strategy benchmark vs naive answers |
| `evaluate_readiness.py` | readiness-decision benchmark on 85 labelled result sets |
| `test_readiness.py` | readiness decision, calendar handling, ADF + KPSS, SARIMA bands, caution delivery |
| `evaluate_anomalies.py` | Stage 3 labelled anomaly benchmark: rules compared, historical and predictive scored separately |
| `test_anomaly.py` | detection rules, STL seasonal space, forecast screening space, spike/shift patterns, persistence |
| `scenario_language.py` | **Part 4** — Stage 6 scenario parser shared by the analyzer and the what-if engine |
| `evaluate_whatif.py`, `whatif_testset.json` | Stage 4 what-if parser benchmark on 94 labelled phrasings |
| `evaluate_verifier.py` | Stage 4 summary-verifier benchmark: fault injection + optional live LLM run |
| `test_whatif.py` | scenario parser, route agreement, precision-aware verifier |
| `evaluate_spider_intent.py`, `benchmark_data/prepare_spider_intent.py`, `benchmark_data/spider_dev_intent.json` | Stage 5 independent intent benchmark on Spider dev |
| `test_intent.py` | thresholds and name columns, whole-word markers, LIMIT 1 only with order, negation / two questions, scalar forecast answers |
| `strategies.py` | **Part 4** — Stage 1 strategy execution |
| `input_adapter.py` | Member 2 columnar result → row dicts |
| `benchmark_data/` | M4 development sample (seed 2026), held-out test sample (seed 2027) + `prepare_m4_sample.py` |
| `test_db/` | synthetic MySQL database + 77 integration fixtures |
| `forecast_benchmark.md`, `strategy_benchmark.md`, `readiness_benchmark.md`, `anomaly_benchmark.md`, `whatif_benchmark.md`, `verifier_benchmark.md`, `spider_intent_benchmark.md` | generated benchmark reports |
| `stage2_completion_report.md`, `stage3_completion_report.md`, `stage4_completion_report.md`, `stage5_completion_report.md` | stage reports |
| `synthetic_data.py` | labelled generators + 12-scenario benchmark |
| `intent_testset.json` | 48 labelled intent cases |
| `response_intent_dataset.csv` | 125-input response-intent development corpus |
| `response_intent_holdout.csv` | 50-input response-intent hold-out corpus |
| `evaluate_response_intent.py` | response-intent benchmark; writes the predictions CSV |
| `test_response_intent.py` | 52 assertions over focus, chart suppression, guardrails + blocks |
| `response_intent_design.md` | **Part 5** design, rules, evaluation and known limits |
| `baseline_report.md` | measured results, limitations, open issues |
| `component_roadmap.md` | delivery plan |
| `research_protocol.md` | experimental method |
