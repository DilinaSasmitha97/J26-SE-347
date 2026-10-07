# Component 4 — Team Interface Contract

**Member 4:** Wijethunge W M V (IT23256750) — Presentation & Prediction Layer
**Project:** J26-SE-347

This document specifies what Component 4 **consumes** from Members 1–3 and what
it **produces** for the client. It extends the team contract in
`Dilina/NL TO SQL prototype/team_interface_contract.md`.

---

## 1. Position in the chain

```
Member 3 (Auth)  →  Member 1 (NL→SQL)  →  Member 2 (AST + PII)  →  Member 4 (THIS)
                          ▲                                              │
                          └──────── /api/v4/analyze (pre-generation) ────┘
```

Component 4 is called **twice** in the ideal flow:

1. **Before SQL generation** — `/api/v4/analyze` returns intent, affected
   tables and prediction demand. Member 1 can use `semantic_roles` to shape the
   query; Member 3 can pre-authorise the tables named in `affected_tables`.
2. **After masking** — `/api/v4/present` receives the masked rows and returns
   the full presentation envelope.

Call 1 is optional. Component 4 derives everything it needs independently, so
the chain works even if only call 2 is wired.

---

## 2. What Component 4 consumes

### 2.1 From Member 2 — masked result rows

Member 2's `/api/query` response is forwarded **unchanged** as `member2_result`.
This is the format `query-executor.js` + `pii-masker.js` actually produce
(mysql2 with `rowsAsArray` and `dateStrings: true`):

```json
{
  "user_query": "Show my monthly software expenses and predict the next 3 months",
  "member2_result": {
    "statementType": "SELECT",
    "columns": [
      {"name": "month", "sourceTable": null, "sourceColumn": null},
      {"name": "total_amount", "sourceTable": null, "sourceColumn": null}
    ],
    "rows": [["2024-01-01", "3419.57"], ["2024-02-01", "3502.11"]],
    "rowCount": 2,
    "truncated": false,
    "masking": {"mode": "partial", "columns": [], "maskedCells": 0}
  }
}
```

`input_adapter.py` converts this to row dicts before any other stage runs.
What it handles, so Member 2 does not have to change anything:

| Property of Member 2's output | Handling in Component 4 |
|---|---|
| Rows are arrays aligned to `columns` | Converted to dicts in column order |
| Duplicate names (`a.id`, `b.id` both arrive as `id`) | Second copy renamed (`id_3` if `id_2` exists), warning `DUPLICATE_COLUMN_NAMES_RENAMED` |
| DECIMAL (every `SUM`/`AVG` over money) arrives as a string | Measure columns converted to numbers after profiling |
| Dates arrive as `YYYY-MM-DD` strings | Parsed by the profiler as before |
| `truncated: true`, or `rowCount` larger than the rows sent (row cap hit) | Warning `INPUT_TRUNCATED`. Since Stage 8, **no forecast or category projection is made** (readiness verdict `TRUNCATED`): which rows were cut depends on the query's `ORDER BY`, so the latest periods may be missing. The user is asked for a coarser period or a shorter range. Configurable (`refuse_truncated_input` in `forecast_config.json`). |
| `masking.columns` | Recorded in the envelope's `input.masked_columns`, warning `MASKED_COLUMNS_PRESENT` |
| `masking.columns` names a column the result does not have | Warning `MASKED_COLUMN_NOT_FOUND` (Stage 8): the two layers disagree about the result's columns |
| `rows` present but `columns` empty | Rejected with `INPUT_FORMAT_ERROR` (Stage 8); before, every value was dropped silently |
| `rowCount` not a number | Warning `INVALID_ROW_COUNT`; the received row count is used (Stage 8) |

The legacy shape below is still accepted as `raw_results`, for tests and
callers that already hold row dicts:

```json
{
  "user_query": "Show my monthly software expenses and predict the next 3 months",
  "raw_results": [
    {"invoice_date": "2024-01-01", "amount": 3419.57},
    {"invoice_date": "2024-02-01", "amount": 3502.11}
  ],
  "schema_types": {"invoice_date": "DATE", "amount": "DECIMAL(12,2)"}
}
```

**Requirements on the rows (either format):**

| Requirement | Why | If violated |
|---|---|---|
| List of flat dicts, one per row | Profiler indexes by column name | `UNSUPPORTED_ROW_FORMAT` warning, table fallback |
| Consistent keys across rows | Column typing needs full columns | Ragged rows tolerated; missing values counted as null |
| Chronological order **not** required | Series are sorted internally | — |
| Dates as ISO strings, `date`/`datetime`, or `YYYY-Qn` | Temporal inference | Column treated as categorical; forecasting refused |
| Numbers as numeric or numeric-like strings | Measure detection | Column treated as categorical |
| **PII already masked** | Component 4 renders and narrates values verbatim | Masked values would be displayed — see §4 |

`schema_types` is optional; types are inferred from values when absent.

### 2.2 From Member 3 — security context

```json
{
  "security_context": {
    "tenant_id": "tenant_a_123",
    "user_role": "FINANCE_VIEWER",
    "prompt_grounding_rules": "STRICT CONSTRAINT: Filter by tenant_id = 'tenant_a_123'.",
    "denied_tables": ["employees", "payroll"]
  }
}
```

**Behaviour:**

- `denied_tables` are removed from the schema **before** any binding, so a
  denied table can never appear in `affected_tables` or a chart axis. Enforced
  in `query_analyzer.analyze`; echoed as `metadata.denied_tables_enforced`.
- `tenant_id` is part of the cache key, so a cached presentation can never be
  served across a tenant boundary.
- `prompt_grounding_rules` is injected into the analysis prompt in hybrid mode.

### 2.3 From Member 1 — schema metadata

Either the DDL string Member 1 already builds, or a dict:

```python
{"expenses": {"invoice_date": "DATE", "amount": "DECIMAL(12,2)"}}
```

---

## 3. What Component 4 produces

### 3.1 `POST /api/v4/analyze` — Part 1 only

Returns `{status, pipeline_version, analysis, profiling}` where `analysis` is
the comprehensive contract documented in `README.md` §"Part 1". The fields most
useful to other members:

| Field | Consumer | Use |
|---|---|---|
| `intent.primary_intent` | Member 1 | shape the SQL (aggregate vs row-level) |
| `response_intent.intent` | client | which UI surface to prepare *before* the rows arrive |
| `response_intent.blocks` | client | the ordered blocks the response will contain |
| `semantic_roles.metrics` / `.dimensions` / `.temporal_field` | Member 1 | GROUP BY and SELECT hints |
| `semantic_roles.limit` + `.limit_source` | Member 1 | LIMIT clause — see the note below |
| `semantic_roles.ordering` | Member 1 | ORDER BY; empty when direction is not inferable |
| `schema_binding.affected_tables` | Member 3 | pre-authorisation |
| `governance.pii_columns_referenced` | Member 2 | masking hint |
| `warnings` contains `PROMPT_INJECTION_SUSPECTED` | Member 2 | escalate screening |
| `prediction_request.prediction_required` | client | show/hide forecast controls |

**`limit_source` — read this before applying `limit`:**

| value | meaning | Member 1 should |
|---|---|---|
| `EXPLICIT` | the user stated the bound ("top 10") | apply it; it is a requirement |
| `INFERRED` | a superlative implied a bound but named no number | apply it as a **default**, overridable |
| `NONE` | genuinely unbounded ("list all departments") | apply no LIMIT |

An `INFERRED` limit is 5 for a plural superlative ("which departments spend the
most") and 1 for a singular one ("which department spends the most"). It always
comes with `IMPLICIT_LIMIT_APPLIED` in `warnings`, and the client is expected to
disclose it and offer to widen. Never present an inferred bound to the user as
something they asked for.

*Stage 5 correction:* before Stage 5 the code inferred `LIMIT 1` for **every**
single-answer question, including singular lookups with nothing to order by
("the name of the museum that had no visitor yet"), where `LIMIT 1` returns an
arbitrary row and hides the rest. The code now matches this note: `LIMIT 1` is
inferred only with a superlative or an explicit "single / top one". A singular
question without one comes with `limit_source: NONE`, and if several rows come
back the response is shown as a table (guardrail G1).

`ordering` is empty when the direction cannot be inferred — `best` and `worst`
depend on the metric's polarity, which this component does not know. That case
raises `ORDERING_DIRECTION_AMBIGUOUS`; resolve it with schema knowledge.

### 3.2 `POST /api/v4/present` — full envelope

```jsonc
{
  "status": "SUCCESS",
  "pipeline_version": "1.0",
  "analysis":       { /* as above */ },
  "result_profile": { "row_count": 24, "temporal_column": "invoice_date",
                      "granularity": "MONTH", "is_time_series": true, ... },
  "response": {
    // Part 5 - what SHAPE the reply takes. Read this FIRST when rendering.
    "response_intent": { "intent": "MIXED_SUMMARY", "confidence": 0.96,
                         "source": "RULE", "rationale": "...",
                         "blocks": ["SUMMARY", "TABLE", "CHART"],
                         "guardrails_applied": [],
                         "original_intent": "MIXED_SUMMARY", "warnings": [] },
    "blocks_emitted":  ["SUMMARY", "TABLE", "CHART"],
    "blocks_declared": ["SUMMARY", "TABLE", "CHART"],
    // Only the blocks in `blocks_emitted` are present. Absent, not empty.
    // `focus` says which half of the row answers the question:
    //   ENTITY -> "which department spends the most" -> "Engineering"
    //   VALUE  -> "how much did engineering spend"   -> "482,000"
    // The other half is always the qualifier, already rendered.
    "answer":  { "label": "Department", "value": "Engineering",
                 "display_value": "Engineering", "value_type": "text",
                 "focus": "ENTITY", "qualifier": "482,000",
                 "qualifier_label": "Total Spend",
                 "qualifier_column": "total_spend",
                 "source_column": "department",
                 "supporting_row": { "department": "Engineering",
                                     "total_spend": 482000 } },
    "summary": { "text": "...", "claim_count": 6, "verified": true },
    "table":   { "columns": [ { "name": "amount", "label": "Amount",
                                "type": "number", "align": "right" } ],
                 "rows": [ ... ], "row_count": 30, "rows_returned": 5,
                 "truncated": true,
                 // A superlative implied a top-5 and the result was provably
                 // sorted, so it was applied. When the result is NOT sorted,
                 // `implied_limit_applied` is false, the rows are left intact,
                 // and `limit_note` says why - an arbitrary five must never be
                 // presented as "the most".
                 "implied_limit": 5, "implied_limit_applied": true,
                 "limit_note": "Showing the top 5 by 'spend'. ..." },
    "chart":   { "chart_type": "line", "spec": { /* Vega-Lite */ } }
  },
  "visualization":  { "$schema": "...vega-lite/v5.json", "layer": [ ... ],
                      "_meta": { "chart_type": "line",
                                 "extension_rules_applied": ["R2_CONFIDENCE_BAND",
                                    "R1_FORECAST_MEAN", "R4_SCENARIO_OVERLAY"],
                                 "layer_count": 4 } },
  "prediction": {
    "stage_1_strategy":       { "strategy": "TEMPORAL_FORECAST", "rationale": "..." },
    "stage_2_readiness":      { "verdict": "READY", "checks": [ ... ] },
    "stage_3_model_selection":{ "model": "LINEAR_REGRESSION", "signals": { ... } },
    "stage_4_forecast":       { "generated": true, "points": [
        { "label": "Jan 2026", "predicted": 6454.33,
          "lower_bound": 6040.12, "upper_bound": 6868.53 } ] },
    "stage_5_anomaly":        { "historical_anomalies": [], "predictive_warnings": [] },
    "stage_6_scenario":       { "simulated": false, "skipped_reason": "..." }
  },
  "summary": { "text": "...", "mode": "DETERMINISTIC",
               "claims": [ { "claim_id": "H1", "value": 118734.53,
                             "derivation": "sum of 24 values" } ],
               "verification": { "passed": true, "unverified_values": [] } },
  "warnings": [], "cache": { "hit": false }, "profiling": { ... }
}
```

**Client rendering contract:**

- **Render from `response`, not from the individual parts.** `response.blocks_emitted`
  is the authoritative list of what to show, in order. A block key is present
  only when that block is emitted, so branch on key presence — never on a
  block's contents being non-empty.
- The five shapes and their blocks:
  `SINGLE_ANSWER` → `answer` · `SHORT_SUMMARY` → `summary` ·
  `TABLE_CONTENT` → `table` · `CHART` → `chart` ·
  `MIXED_SUMMARY` → `summary` + `table` + `chart`.
- `response_intent.original_intent` differing from `.intent` means a guardrail
  changed the shape after seeing the rows; `.guardrails_applied` says why.
  Surface it if you show a "why am I seeing this" affordance.
- `response_intent.warnings` containing `LOW_CONFIDENCE_RESPONSE_INTENT` is the
  signal to offer a "show this a different way" control.
- `response.table.truncated` is `true` when more rows exist than were returned;
  `row_count` is the true total. Page against that, not `rows.length`.
- `answer.focus` tells you which half of the row to headline. Render
  `display_value` large and `qualifier_label: qualifier` as supporting text —
  both are pre-rendered strings, so no client-side formatting is needed.
- **`visualization._meta.chart_type` is `"none"` when no chart was built.** The
  shapes that emit no `CHART` block skip chart construction entirely, and
  `_meta.skipped` is `true` with the reason in `selection_reason`. The key is
  always present, so the envelope never changes shape — but do not assume a
  spec is there. Check `chart_type != "none"` first.
- `analysis.visualization_hint.recommended_chart` follows the *response* intent,
  not the analytical one: `kpi_card` for `SINGLE_ANSWER`, `table` for
  `TABLE_CONTENT`, `none` for `SHORT_SUMMARY`. Asking "which department spends
  the most" will not hint at a bar chart.
- `visualization` is valid Vega-Lite v5 — pass it to `vega-embed` directly.
  `response.chart.spec` is the same object, already gated by intent.
- `_meta.render_as` is `"data_grid"` or `"kpi_card"` for the two non-chart
  outputs; otherwise render the spec as a chart.
- `summary.text` is display-ready. `summary.claims` backs a "show the working"
  panel — every number links to its derivation.
- **Stage 2 additions to the envelope:**
  - `result_profile.layout` is `SINGLE`, `GROUPED`, `EVENTS`,
    `CROSS_SECTIONAL` or `NONE`; `result_profile.group_column` names the
    category column of a `GROUPED` result.
  - `prediction.stage_1_strategy_result` holds the strategy-specific answer:
    `requested`, `executed_as` (`CATEGORY_TRAJECTORY`, `SHARE_SHIFT`,
    `QUARTILE_SHIFT`, `PERCENTILE_POSITION`, `ANOMALY_PERSISTENCE`),
    `executed`, `skipped_reason` and `details` (per-category forecasts,
    projected leader, shares, persistence verdict).
  - `stage_2_readiness.decision` is `READY`, `READY_WITH_WARNING`,
    `NOT_READY` or `NOT_EVALUATED` (no forecast requested), with
    `reason_codes` (e.g. `MISSING_PERIODS_INTERPOLATED`, `LOW_SIGNAL`,
    `STATIONARITY_CONFLICT`) and `warnings` (`[{code, message}]`, the
    human-readable cautions). `stationarity` holds the ADF and KPSS p-values
    and verdict; `missing_value_ratio`, `missing_period_ratio` and
    `filled_periods` report completeness.
  - `stage_2_readiness.verdict` can also be `MULTI_SERIES` (forecast per
    category instead), `NOT_AGGREGATED` (raw rows, no value per period),
    `INCOMPLETE` (too many unreadable values or empty periods) or, since
    Stage 8, `TRUNCATED` (reason code `INPUT_TRUNCATED`: the result was cut at
    the row limit); `expected_relative_error`, `skill_vs_naive` and
    `signal_test` report the forecastability test, and `noise_limit` the limit
    applied. `LOW_SIGNAL` is also given when the ADF and KPSS tests conflict
    and the in-history error exceeds 8% (Stage 8). `policy_version` names the
    `forecast_config.json` version that made the decision.
  - `stage_4_forecast.diagnostics.interpolated_periods` lists the history
    positions that were filled for the model; they are never shown as
    observations or flagged as anomalies.
  - `stage_3_model_selection.model` can also be `NAIVE` or `SEASONAL_NAIVE`
    when the benchmark guard overrides the rules; `signals.guard` says why.
  - A grouped chart gains rule `R5_CATEGORY_FORECASTS` (one dashed line and
    band per category); `_meta.category_forecasts_layered` reports it.
- **Stage 3 additions (anomaly engine), all additive:**
  - `stage_5_anomaly.method` can be `ADAPTIVE_IQR_ZSCORE_STL`: the series
    was screened in the STL seasonal space. `seasonal` (bool),
    `seasonal_strength` (0–1) and `period` say why; `predictive_space`
    (`SEASONAL`, `DETRENDED` or `RAW`) says which space the forecast points
    were screened in.
  - Each entry of `historical_anomalies` carries `pattern`: `SPIKE`
    (isolated, the next period is back in range), `SUSTAINED` (two or more
    consecutive same-direction anomalies: a level shift) or `UNCONFIRMED`
    (isolated, in the latest period). `predictive_warnings` entries have an
    empty `pattern`.
  - The `ANOMALY_PERSISTENCE` strategy result adds `details.pattern`,
    `details.run_length` and `details.basis` (`OBSERVED_RETURN`,
    `FORECAST_WITHOUT_LATEST_POINT` or `FORECAST`). The verdict set is
    unchanged. When `basis` is `FORECAST_WITHOUT_LATEST_POINT`, a
    `RECOVERING` verdict is provisional and the summary says so.
- **Stage 7 changes (user interface), no field added or removed:**
  - A reference client exists: `frontend/` (React) renders this contract
    exactly as described here. Use it to check how a response will look.
  - Anomaly markers in `visualization` now carry an explicit shape scale
    (triangle = past anomaly, diamond = projected breach).
  - "Normal range" rules are no longer drawn for seasonal (STL) series, whose
    band is a deviation rather than a level, and a lower bound below zero is
    not drawn for a measure that is never negative.
  - A plain list of records (`DETAIL_LOOKUP`) gets no anomaly bands:
    `stage_5_anomaly.evaluated` is false with a `skipped_reason`, and the
    summary has no outlier claims about individual records.
- **Stage 6 changes (integration rehearsal):**
  - `use_llm` now defaults to **false** on `/api/v4/analyze` and
    `/api/v4/present` (and in `pipeline.run`). Before, any deployment with an
    LLM key sent every question and the schema to the provider unless the
    caller opted out. Send `"use_llm": true` to opt in.
  - `prediction_request.prediction_trigger` can be **`DECLINED`**: the user
    turned the forecast down ("without a forecast", "no predictions please").
    `prediction_required` is then false, no forecast is produced, and the LLM
    cannot switch it back on. Treat it like `NONE` when deciding whether to
    show forecast controls.
  - `stage_2_readiness.reason_codes` / `warnings` can include
    **`PARTIAL_EDGE_PERIOD`**: the first or last period is under 40 % of the
    typical one and may be incomplete (e.g. "this month so far"). The forecast
    is still produced, with the caution.
  - Distribution and correlation questions now get a histogram or a scatter
    plot (`visualization._meta.chart_type` = `histogram` / `scatter`) instead
    of a table; a grouped result of up to 30 text categories (e.g. 15 vendors)
    is charted by category.
  - Verified end to end over HTTP with stand-ins for Members 1-3 (77 questions,
    `test_db/run_api_rehearsal.py`): no contract field missing or mistyped, no
    unmasked PII value in any response, denied tables never bound, no cache hit
    across tenants. See `integration_rehearsal.md`.
- **Stage 5 changes (intent classification):**
  - A scalar question about the future ("how much will I spend next month")
    now returns one `answer` block with `is_forecast: true`, the projected
    figure and its `interval`, instead of the history table. Guardrail G1 no
    longer overrides a single answer when a forecast was explicitly requested.
  - `limit` / `limit_source`: see the Stage 5 correction under `limit_source`.
  - `analysis.primary_intent` is UNKNOWN far less often (retrieval questions
    such as "what are the names of ..." are `DETAIL_LOOKUP`), and phrases such
    as "at least two", "more than the average" and "first name" no longer read
    as superlatives or KPIs. No field names or values were added or removed.
- **Stage 4 additions (what-if and summary verifier), all additive:**
  - `prediction.stage_6_scenario.spec.reason_code` says why a scenario was
    not simulated: `NO_MAGNITUDE`, `NO_DIRECTION`, `NEGATED`,
    `MULTIPLE_CHANGES`, `RANGE`, `ABSOLUTE_AMOUNT`, `NO_CHANGE` or `EMPTY`
    (empty when it was simulated). `skipped_reason` carries the readable
    message. A what-if in the question and the same text sent to
    `/api/v4/simulate` are now read identically.
  - Increases are bounded at 300 % (quadruple); decreases at 100 %.
  - `summary.verification.rule` is `PRECISION_AWARE`: a narrated number must
    agree with a claim number to the precision it is written at ("48.3k",
    "6,454", "three").
  - `summary.rejected_narration` holds an LLM narration the verifier refused,
    for audit only; `summary.text` is then the deterministic text. Do not
    display `rejected_narration` as the summary.
- **`response.forecast_notice` is present whenever the user explicitly asked for
  a prediction**, in every response shape, and absent otherwise:
  ```json
  "forecast_notice": {
    "requested": true,
    "status": "SHOWN",            // or "REFUSED"
    "message": "Amount is projected at 6,862, 7,003 and 7,143 for Jan 2026, Feb 2026 and Mar 2026 respectively.",
    "reason": "",                 // the readiness gate's reason when REFUSED
    "readiness_decision": "READY_WITH_WARNING",
    "warnings": [{"code": "MISSING_PERIODS_INTERPOLATED",
                  "message": "2 of 24 periods had no data and were filled ..."}],
    "reason_codes": ["MISSING_PERIODS_INTERPOLATED"],
    "model": "LINEAR_REGRESSION",
    "horizon": 3,
    "horizon_source": "DEFAULT",  // QUESTION, REQUEST_PARAMETER or DEFAULT (Stage 8)
    "horizon_requested": 3,       // before any shortening (Stage 8)
    "notes": [{"code": "RANGE_CLIPPED_AT_ZERO",
               "message": "This measure has never been negative, so ..."}],
    "shown_in": ["TABLE"]         // blocks that already display the forecast
  }
  ```
  Render `message` as a caption when `shown_in` is empty (a donut, a KPI card,
  or a refusal); it may be hidden when the chart or table already carries the
  forecast. `message` is a verified claim, never free text.
  `notes` (Stage 8, SHOWN only) are facts about how the forecast was made,
  separate from the readiness `warnings`: `HORIZON_SHORTENED` (never longer
  than half the history), `MODEL_FALLBACK` (e.g. SARIMA over its time limit)
  and `RANGE_CLIPPED_AT_ZERO` (a never-negative measure's range is cut at 0).
  Show them with the notice.
- When a forecast was requested, the blocks carry it themselves:
  `table.rows` gain rows with `row_type: "FORECAST"` plus `lower_bound` /
  `upper_bound` columns (historical rows are `row_type: "ACTUAL"`;
  `table.forecast_rows` counts them, `row_count` still counts real rows only);
  a `SINGLE_ANSWER` answers with the forecast (`answer.is_forecast: true`,
  `answer.interval` for a single period, the projected total for an explicit
  multi-period horizon); a summary is built forecast-first
  (`summary.sentence_selection: "FORECAST_PRIORITY"`).

### 3.3 `POST /api/v4/simulate` — interactive what-if

Applies a new scenario to rows the user already holds. **Does not re-query the
database**, so it cannot widen data access.

```json
{ "user_query": "...", "raw_results": [ ... ],
  "scenario_text": "what if I reduce spending by 20%" }
```

Returns `{status, scenario, visualization, summary}`.

### 3.4 Errors

```json
{ "status": "ERROR", "error_code": "PRESENTATION_FAILED", "detail": "..." }
```

Codes: `ANALYSIS_FAILED`, `PRESENTATION_FAILED`, `SIMULATION_FAILED`, and
`INPUT_FORMAT_ERROR` (Stage 8) when `member2_result` itself is malformed (rows
without columns, rows that are not arrays, `columns`/`rows` not arrays). That
one is a caller-side problem: fix the payload, do not retry.

Note that most degradations are **not** errors: an empty result set, an
unforecastable series or an uninterpretable scenario all return `SUCCESS` with
an explanatory `warnings` entry and the relevant `skipped_reason`.

---

## 4. Security boundaries — what this component does and does not do

**Does not enforce.** Component 4 is downstream of the security gate. It does
not validate JWTs, rewrite SQL, or mask PII. It never issues a database query.

**Does enforce, defensively:**

| Control | Mechanism |
|---|---|
| Denied tables never bound | schema filtered before analysis |
| No cross-tenant cache reuse | `tenant_id` in the cache key |
| Injection markers surfaced | regex screen on raw text → `PROMPT_INJECTION_SUSPECTED` |
| PII columns flagged | name-pattern screen → `PII_COLUMNS_REFERENCED` |
| LLM cannot invent schema | every model-supplied table/column checked against the real schema |
| LLM cannot invent numbers | claim verifier rejects unverifiable narration wholesale |
| Scenarios cannot widen access | what-if is a bounded transform of already-returned rows |

**Assumption Member 2 must uphold:** rows arriving at `/api/v4/present` are
already masked. Component 4 renders and narrates values verbatim — it has no
way to distinguish a real email address from a masked one.

---

## 5. Versioning

`pipeline_version` (currently `1.0`) is returned in every envelope. Breaking
changes to the analysis contract will increment
`schemas.ANALYSIS_SCHEMA_VERSION`, returned as `analysis_schema_version`.
