# Stage 5 Completion Report — Component 4 (Visualization & Prediction Layer)

5 October 2026 · Wijethunge W M V (IT23256750) · Project J26-SE-347

## Summary

Stage 5 tested the component's two classifiers on questions their author did not write, then fixed what that test exposed:

- The **analytical intent** classifier (trend, ranking, lookup, ...).
- The **response shape** classifier (single answer, table, chart, summary, mixed report).

Every earlier intent test set, at 100%, was written by the same person who wrote the rules.

The independent test uses the 1,032 questions of the **Spider dev set**, written by Spider's annotators for a different purpose. Each question's labels come from its gold SQL, by fixed rules frozen before the classifier was run. The questions are split by database: changes were made on DEV (531 questions), and TEST (501) was evaluated once with the frozen code.

Headline results on the held-out TEST databases:

- **Analytical intent: 45.1% → 88.2%** (McNemar p < 10⁻⁵⁰). Before Stage 5, 28% of these questions got no intent at all.
- **Response shape: 85.6% → 89.0%** (p = 0.012). 29 questions fixed, 12 newly wrong.
- **Rows silently lost:** questions whose SQL returns many rows, but for which the layer would ask Member 1 for `LIMIT 1`, went from **16.7% to 5.8%**.
- **Scalar forecast questions** ("how much will I spend next month") now get the projected figure and its range. Before, guardrail G1 replaced the answer with the 24-row history table.
- **Response-shape stress set: 26/45 → 42/45.** The author-written sets stay at 100% (intent 48/48, response shape 125/125 and 50/50).

All Stage 5 work is in the working tree of branch `vonara-nl-to-sql-prototype-stage-5`, which contains Stages 1–4. Nothing has been committed or pushed, and `main` is untouched.

## Starting point

| What was measured | Before Stage 5 | What it meant |
| --- | --- | --- |
| Analytical intent | 100% on 48 author-written questions | Only 45.1% on independent questions; 28% got UNKNOWN |
| Response shape | 100% on 125 + 50 author-written inputs | 57.8% on the author's own stress set; 85.6% on Spider TEST |
| "Single answer" questions | Always asked Member 1 for `LIMIT 1` | Truncated multi-row results in 16.7% of Spider TEST's multi-row questions |
| "How much will I spend next month?" | Classified SINGLE_ANSWER, then turned into a TABLE by guardrail G1 | The user got the history, not the forecast |

## Work completed

1. **Independent benchmark** (`benchmark_data/prepare_spider_intent.py`, `evaluate_spider_intent.py`).
   - **Labelling.** Each gold SQL is labelled by eight ordered rules: set operation, `LIMIT 1`, `GROUP BY`, aggregates only, mixed aggregates, top-N, ordered, plain lookup. Each rule gives an *acceptable set* of shapes and intents. Where the SQL cannot decide, both readings are accepted; for example, a grouped count may be a table or a chart.
   - **Freezing.** One rule was corrected after checking the labels against the SQL, before any classifier run: a `GROUP BY … HAVING` that only filters returns a list, so it cannot be charted. The file was then frozen (SHA-256 `853f412d…`).
   - **Split.** By database, so Spider's paraphrase pairs never cross DEV and TEST.
   - **Error types.** It reports shape and intent accuracy, and separates "multi-row read as one" from the costly case where `LIMIT 1` is actually requested.
2. **Shared rewrite of misleading phrases** (`response_intent.neutralize`, used by both classifiers). "at least / at most", "no more than", "more than a single" and "than the average / minimum" become neutral filter tokens. "first / last / middle name" becomes a single column token. Before this, "teachers who teach **at least** two courses" read as a superlative and requested `LIMIT 1`.
3. **Analytical intent fixes** (`query_analyzer.py`):
   - Literal markers must start a word: "each" no longer matches "t**each**", nor "per" "**per**cent".
   - One weak lookup cue covers retrieval questions ("what are the …", "return the …", "which …"). It is deliberately the lowest tier, so any real marker outranks it.
   - Extra superlatives: fewest, youngest, oldest, greatest, most common, biggest.
   - Counts: "count the", "the number of X" (but not "the phone number of the student"), and pairs of aggregates.
   - "first" is a ranking only as "first 10" or "the first X to …".
   - Precedence: a count per group ("in each location") is COMPARISON, and the entity at a superlative ("the code of the airport with the most flights") is RANKING.
4. **`LIMIT 1` only where something orders the rows** (`derive_bounds`). This is the documented contract, which the code had not followed.
5. **Response-shape fixes** (`response_intent.py`):
   - A refused format ("**don't** give me a chart") is not chosen. The negation stops at "please / just / but".
   - Two questions in one request get the mixed report, unless a later clause refers back ("…how many courses do **they** teach") or the request asks for two extremes ("who spent the most and who spent the least").
   - Yes/no questions about direction ("is revenue up or down since Q1") and "what does the data tell us" get a short summary.
   - A count per listed row is a table column.
   - "all" as a scope ("the total bonus given **in all** evaluations") no longer vetoes a single answer.
   - New phrases: "tabulate", "headline number", "only the top one", "then", "but … too".
6. **Scalar forecast questions.** Guardrail G1 is not applied when a forecast was explicitly requested; the renderer's existing forecast answer is shown instead. "Next week", "tomorrow" and "will we / will our" now count as forecast requests.
7. **Hybrid LLM comparison** (`--llm 60`): rules only against rules + Groq LLM, on the first 60 TEST questions.
8. **Tests.** `test_intent.py` has 21 checks.

## Results

### Independent benchmark (`spider_intent_benchmark.md`)

| Split | Questions | Shape, Stage 4 → 5 | Intent, Stage 4 → 5 | Multi-row read as one, 4 → 5 | `LIMIT 1` requested on multi-row, 4 → 5 |
| --- | --- | --- | --- | --- | --- |
| DEV (changes made here) | 531 | 85.3% → 90.0% | 48.2% → 92.3% | 13.8% → 9.6% | 13.8% → 0.8% |
| **TEST (held out)** | 501 | **85.6% → 89.0%** | **45.1% → 88.2%** | 16.7% → 11.2% | **16.7% → 5.8%** |

Paired McNemar exact tests on TEST:

| | Fixed | Newly wrong | p |
| --- | --- | --- | --- |
| Shape | 29 | 12 | 0.012 |
| Intent | 225 | 9 | 4 × 10⁻⁵⁵ |

On the costliest error (rows lost to `LIMIT 1`), DEV improved more than TEST: 0.8% against 5.8%. That gap is the part of the DEV improvement that came from fitting DEV.

**Response shape on TEST, by SQL rule** (Stage 4 → Stage 5):

| SQL rule | Correct |
| --- | --- |
| GROUPED | 76 → 85 / 105 |
| LIMIT_1 | 70 → 74 / 81 |
| LOOKUP | 98 → 99 / 116 |
| SCALAR | 125 → 128 / 134 |
| SET_OP | 41 → 42 / 43 |
| ORDERED | 12 → 12 / 13 |
| TOP_N | 6 → 5 / 8 |

**The 12 newly wrong TEST shapes:**
- **5 from the new "two questions in one" rule.** For example: "For each continent, list its id, name, **and how many** countries it has". "it / its" was deliberately not treated as a back-reference, because "what is our MRR **and how is it** trending" is a genuine second question.
- **3 questions with "each time" or "with 4 cylinders" read as grouped.**
- **2 "first names of all players, and their average rankings"**, read as a single figure.
- **1 top-3 question and 1 earliest-year question** read as single answers.

### Hybrid LLM path (first 60 TEST questions, Groq)

| Path | Shape | Intent | Multi-row read as one |
| --- | --- | --- | --- |
| Rules only | 93.3% | 91.7% | 3.3% |
| Rules + LLM | **98.3%** | 81.7% | 3.3% |

The LLM improves the response shape but lowers intent agreement. 6 of its 11 newly "wrong" intents call "list singer names and the number of concerts for each singer" a lookup, where the SQL-derived label says per-group comparison. Both readings are defensible, so part of this gap is ambiguity in the taxonomy, not plain LLM error. Two of the 60 LLM calls failed with connection errors and fell back to the rules. The sample is small: 60 questions, one model.

### Other sets

| Set | Before | After |
| --- | --- | --- |
| Author intent set (48) | 100% | 100% |
| Response shape, dev (125) / holdout (50) | 100% / 100% | 100% / 100% |
| Response shape, stress (45) | 26 (57.8%) | **42 (93.3%)** |

The stress set was used for design in Stage 5, so its 42/45 is a development figure.

### Scalar forecast questions

| Question (24 months of history) | Before | After |
| --- | --- | --- |
| "How much will I spend next month?" | history table | **Projected amount 6,454, range 6,040 to 6,869** |
| "How much will I spend over the next 3 months?" | history table | **Projected total 19,725** (Jan–Mar 2026) |
| "How many orders will we get next week?" | not detected as a forecast | answered by the forecast |
| "How much did I spend in total?" (past) | table (G1) | table (G1), unchanged as intended |

### Regression

- **Test suites:** all 9 pass.

  | Suite | Checks |
  | --- | --- |
  | test_intent | 21 |
  | test_whatif | 30 |
  | test_anomaly | 19 |
  | test_component | 61 |
  | test_strategies | 24 |
  | test_forecast_delivery | 42 |
  | test_readiness | 23 |
  | test_input_adapter | 27 |
  | test_response_intent | passes |
- **Unchanged evaluations:** what-if parsing (94/94), summary grounding (100%).

## What this means for the research claims

- **The intent claim now has real evidence.** On questions the author did not write, the analytical intent is right 88% of the time and the response shape 89%. Before Stage 5 the honest independent figure was 45%, hidden behind 100% on the author's own set. The 100% figures should no longer be quoted alone.
- **The row-loss fix is a design correction, not only a lexicon change.** A single answer used to imply `LIMIT 1`, which is only safe when something orders the rows. The code now follows the contract already given to Member 1.
- **The hybrid LLM path is not a free improvement.** It helps the response shape and lowers intent agreement on this sample, so the deterministic rules remain the default.

## Limitations and open issues

1. **Spider only covers part of the taxonomy.** Its questions never ask for summaries, reports, charts by name or forecasts. Those shapes are tested only by the author-written sets and the stress set.
2. **SQL-derived labels are mechanical.** The rules are mine, though fixed before the classifier ran. Some labels are strict: a lookup of one record with two attributes is labelled "table", so a single answer there counts as an error. Labels written by the team on real business questions would be stronger.
3. **Column names that are format words** ("the degree **summary** name", "**describe** the section") still read as format requests. Fixing this needs the bound schema, which the classifier does not use.
4. **Known remaining errors:**
   - "names of stores whose **number of** products is more than the average" still reads as a count.
   - 5.8% of held-out multi-row questions still request `LIMIT 1`.
5. **Forecast periods.** "What will revenue be next **quarter**?" on monthly data answers with the next month, not the next three months combined.
6. **Not run:** the MySQL harness (still needs `MYSQL_ADMIN_PASSWORD`), and the forecasting, anomaly and verifier benchmarks. Their code was not changed in Stage 5.

## Files

| File | Change |
| --- | --- |
| `benchmark_data/prepare_spider_intent.py`, `benchmark_data/spider_dev_intent.json` | New: Spider dev questions, SQL-derived labels, database split (provenance in `benchmark_data/README.md`) |
| `evaluate_spider_intent.py` | New: independent benchmark; `--baseline`, `--llm N` |
| `response_intent.py` | `neutralize`, negation, two questions, per-row counts, new phrases, `LIMIT 1` only with order, G1 forecast exemption |
| `query_analyzer.py` | Shared rewrite, whole-word markers, retrieval cue, superlatives, counts, precedence, forecast words |
| `pipeline.py` | Passes `forecast_requested` to the guardrails |
| `test_intent.py` | New: 21 checks |
| `data_and_reports/` | Benchmark report, Stage 4 baseline, README, roadmap, team contract, this report |

**To reproduce:**
- `python evaluate_spider_intent.py`
- `python evaluate_spider_intent.py --llm 60` (sends 60 public Spider questions to the LLM provider in `.env`)
- `python test_intent.py`

## Next stage

Stage 6 is integration:
- Run the MySQL harness.
- Connect to Member 1's SQL generation and Member 2's masked results.
- Measure the end-to-end latency.
