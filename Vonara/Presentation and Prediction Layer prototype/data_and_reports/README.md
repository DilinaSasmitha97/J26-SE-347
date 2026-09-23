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
| 2 Data readiness | `assess_readiness` | three gates — temporal validity, statistical sufficiency, signal quality |
| 3 Model selection | `select_model` | **dual-signal**: semantic intent × statistical structure (ADF, seasonal ACF, trend R², CV) |
| 4 Forecasting | `generate_forecast` | intervals widen as `z·σ·√h·small_sample_penalty` |
| 5 Anomaly detection | `anomaly.detect_anomalies` | adaptive IQR/Z thresholds, applied to past **and** forecast |
| 6 What-if | `whatif.simulate` | NL scenario → bounded parametric perturbation, all outputs regenerate |

Two design decisions worth defending in the report:

**Horizon clamping.** The forecast never projects further than half the
observed span. Extrapolating 12 periods from 8 observations is not a forecast.

**Detrended anomaly detection.** On a growing series the raw IQR fence spans the
entire growth range, so real local spikes sit comfortably inside it. When trend
R² ≥ 0.50 the detector measures dispersion on residuals instead. This is the
single change that took anomaly recall from 0.25 to 0.50 (see below), and it is
why the threshold is genuinely *adaptive* rather than merely rescaled.

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

Both runs write `<dataset>_predictions.csv` — every input with its expected
label, the engine's actual verdict, `CORRECT`/`WRONG`, confidence and rationale.
That file is the record of the current state; diff it after any lexicon change.

**2. Prediction accuracy** — 3-period holdout, 10 backtestable scenarios

| strategy | RMSE | MAE | mean MAPE | median MAPE |
|---|---|---|---|---|
| **Adaptive (dual-signal)** | 3,881 | 3,281 | 23.20 % | **7.42 %** |
| fixed Weighted MA | **3,459** | **3,053** | 23.58 % | 8.07 % |
| fixed Linear Regression | 4,356 | 3,759 | 26.23 % | 10.69 % |
| fixed Exp. Smoothing | 4,320 | 3,439 | 24.04 % | 9.64 % |

Model-selection agreement with the generating process: **100 % (12/12)**.

> The adaptive selector wins on median MAPE but **loses to fixed WMA on mean
> RMSE**. This is a real, unresolved finding, not a presentation artefact — one
> near-unforecastable series (154 % MAPE) that the readiness gate should have
> rejected dominates the mean. Documented as open issue #1.

**3. Anomaly detection** — 6 labelled processes, 12 injected anomalies

| method | precision | recall | F1 | FPR |
|---|---|---|---|---|
| **Adaptive (detrended IQR/Z)** | 1.00 | **0.50** | **0.67** | 0.000 |
| Static (textbook 1.5·IQR) | 1.00 | 0.25 | 0.40 | 0.000 |

The adaptive method **doubles recall at zero false positives**. Remaining
misses are all on seasonal series, where linear detrending cannot remove a
periodic component — open issue #2.

**4. Summary grounding** — 465 numbers across 12 summaries: **100 % traceable**.

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
| `evaluate.py` | research metrics |
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
