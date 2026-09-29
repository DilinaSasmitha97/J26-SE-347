# Response Intent — Design & Evaluation

**Component 4, Part 5 — Response Shaping**
Status: prototype, stage 1. Deterministic engine complete and benchmarked; the
LLM path is wired but is not the primary decision-maker.

---

## 1. The problem this solves

Component 4 already classified *what the user is asking about* — `QueryIntent`
(`TREND_ANALYSIS`, `RANKING`, `PROPORTION`, …). That taxonomy is analytical, and
it is the right input for choosing a forecasting strategy and a chart grammar.

It is the wrong taxonomy for deciding **what the user gets back**. Two examples
show why the two questions are genuinely independent:

| Question | Analytical intent | Right output |
|---|---|---|
| "what was our highest invoice" | `RANKING` | one number |
| "how many customers do we have" | `KPI_SINGLE_VALUE` | one number |
| "revenue by month" | `TREND_ANALYSIS` | a chart |
| "revenue by region" | `COMPARISON` | a chart |

Different analytical intents collapse to the same output shape, and the same
analytical intent can produce different shapes depending on how the user asked.
The mapping is many-to-many, so it needs its own classifier.

## 2. The taxonomy

Five members, closed and exhaustive. Declared in `schemas.ResponseIntent`.

| Intent | Fires when | Blocks emitted |
|---|---|---|
| `SINGLE_ANSWER` | the user wants one value or one record — a highest/lowest, a max/min, a total, a count, "who is the top" | `ANSWER` |
| `SHORT_SUMMARY` | the user wants a few sentences in words — "summarise", "briefly", "overview", "how did X do" | `SUMMARY` |
| `TABLE_CONTENT` | the user wants the dataset itself — "list all", "every record", "export", a top-N of several rows | `TABLE` |
| `CHART` | the user wants a visual reading — they said chart/graph/plot, or asked for a trend, comparison, share or distribution | `CHART` |
| `MIXED_SUMMARY` | the user wants a full report — "full report", "deep dive", "dashboard", or they named two or more formats at once | `SUMMARY` + `TABLE` + `CHART` |

Two properties are enforced rather than assumed:

**There is no `UNKNOWN`.** A presentation layer must always render something.
Low confidence is expressed through the confidence score and a
`LOW_CONFIDENCE_RESPONSE_INTENT` warning — never through an unrenderable label.
The fallback when nothing at all can be decided is `TABLE_CONTENT`, because raw
rows are the only shape that asserts nothing the data does not contain.

**The intent *is* its block list.** `schemas.RESPONSE_BLOCKS` maps each intent to
an ordered tuple of blocks, and `response_renderer.render()` emits exactly those
and nothing else. This is what makes the taxonomy testable end to end — a test
asserts that a `SINGLE_ANSWER` response contains an `ANSWER` block and no others
(`test_response_intent.py`, "Renderer — block contract").

## 3. Architecture

Three stages. Each is independently auditable, and each records why it decided
what it decided.

```
  user question
       │
       ▼
  ┌─────────────────────────────────────────────┐
  │ Stage A — LEXICAL          (pre-execution)  │
  │   lexical repair → weighted markers → rules │
  └─────────────────────────────────────────────┘
       │  verdict + confidence
       ▼
  ┌─────────────────────────────────────────────┐
  │ Stage B — ANALYTIC PRIOR   (pre-execution)  │
  │   only when Stage A is weak AND the user     │
  │   named no format explicitly                │
  └─────────────────────────────────────────────┘
       │
       ├──────────► exposed on `QueryAnalysis.response_intent`
       │            Members 1 and 3 can read this before any SQL runs
       ▼
    [ SQL executes, results are profiled ]
       │
       ▼
  ┌─────────────────────────────────────────────┐
  │ Stage C — GUARDRAILS       (post-execution) │
  │   repair the verdict against the real rows  │
  └─────────────────────────────────────────────┘
       │
       ▼
  response_renderer.render() → the blocks
```

### Stage A — lexical

Weighted marker evidence over the five families, on the same ordinal scale the
analytical engine already uses (4 = decisive, 3 = strong, 2 = moderate,
1 = weak corroboration).

Before scoring, a narrow **lexical repair** step runs. Users mistype exactly the
words that carry the format signal — `summery`, `chartt`, `how mnay`, `liat all`.
Losing the decisive marker to a transposed letter drops an entirely
understandable request to the analytical prior, which is a visibly worse answer.

The repair is guarded on four independent checks — same first letter, same last
letter, length within one, similarity ≥ 0.75 — and a token on
`_PROTECTED_TOKENS` is never touched. That deny-list exists because without it
the repair turns `cost` into `count`, `last` into `list` and `cart` into `chart`;
every entry was added in response to a real collision. Every repair is recorded
in the rationale, so a wrong one is visible rather than silent.

**Precedence rules.** Where families collide, the winner is decided by rules that
encode a real asymmetry in the request, not an arbitrary tie-break:

| Rule | Claim |
|---|---|
| **R1** multi-modality | Naming two formats joined by a conjunction requests both. Applied *decisively* (`MIXED = max(others) + 2`), because "a table and a chart" scores highly for CHART on its own words and additive points would not overcome that. |
| **R2** named beats inferred | "as a chart" is the user stating a requirement; "over time" is us inferring one. The inference must not override the statement. |
| **R3a** enumeration veto | "list all", "top 10" — an N-row request is a table, whatever superlatives surround it. |
| **R3b** grouping veto | "per region", "by month" — one value *per group* is a series, and a series is a chart. |
| **R3c** paired superlatives | "the highest **and** lowest" is two rows, so a small table. Decisive, because the scalar reading accumulates score from the very superlatives that defeat it. |
| **R3d** plural entity | "which department**s** spend the most" is several entities, so a table. Decisive for the same reason as R3c. |
| **R4** count disambiguation | "how many orders" is one number; "how many orders **per region**" is a series. |
| **R5** mixed damping | A stray "detailed" is not a request for three blocks. `MIXED` needs decisive phrasing or R1. |
| **R6** brevity cap | An explicitly *short* answer cannot be a full report, even when it mentions data. |

Splitting R3 into *enumeration* and *grouping* was the single highest-value fix
found during evaluation. Collapsed into one veto, "total revenue by month" came
back as a scalar and "how many orders per region" came back as a count — both
because a grouping was being treated as an enumeration.

**Tie-break.** Equal evidence resolves toward the more expressive shape
(`MIXED > CHART > TABLE > SUMMARY > SINGLE`). A richer block set never hides
what the narrower one would have shown, so it is the safer error.

### Answer focus — which half of the row is the answer

`SINGLE_ANSWER` covers two questions that return the *same row* but are answered
by opposite halves of it:

| Question | Focus | Answer | Qualifier |
|---|---|---|---|
| "which department spends the most" | `ENTITY` | `Engineering` | Total Spend: 482,000 |
| "how much did engineering spend" | `VALUE` | `482,000` | Department: Engineering |

`detect_answer_focus()` decides this from the question, and the renderer orients
the `ANSWER` block accordingly. An explicit quantity request wins over an entity
cue, because "how much does the top department spend" contains both and is
unambiguously about the money.

The other half always travels with the answer as the qualifier — it is the
evidence for an `ENTITY` choice and the subject of a `VALUE` one — so the figure
is never shown without its subject, nor the subject without its evidence. The
aggregation prefix ("Sum of…") is applied only to a number; prefixing an entity
name with it would describe the wrong half of the row.

Plurality decides row count: "which department**s** spend the most" is a ranking
of several, so R3d routes it to `TABLE_CONTENT`. A lookahead protects the
singular nouns that end in 's' (`business`, `status`, `analysis`, …).

### Implicit row bounds — what "the most" means numerically

"the most" is a superlative: it names a bounded top slice. When the user counts
it out ("top 10") the bound is `EXPLICIT` and nothing is inferred. When they do
not, leaving the request unbounded is wrong in both directions — it asks Member 1
for a full scan, and it answers "which departments spend the most" with every
department there is.

| Phrasing | limit | `limit_source` | ordering |
|---|---|---|---|
| "which department**s** spend the most" | **5** | `INFERRED` | `spend DESC` |
| "which department spends the most" | **1** | `INFERRED` | `spend DESC` |
| "which departments spend the least" | **5** | `INFERRED` | `spend ASC` |
| "top 10 departments by spend" | 10 | `EXPLICIT` | `spend DESC` |
| "list all departments" | 0 | `NONE` | — |

**Why 5.** It is a convention, not a derivation, and it is labelled as one. Five
sits below `visualization.FEW_CATEGORIES` (8), so an inferred slice stays
legible in every encoding including a donut, and it is small enough that being
wrong costs the user one follow-up rather than a flood of rows. Every inferred
bound raises `IMPLICIT_LIMIT_APPLIED` so a client can show "top 5" with a widen
control — an assumed bound is never presented as a user requirement.

**Why 1 for the singular.** A scalar answer is one row by construction. Stating
it lets Member 1 emit `LIMIT 1` instead of returning the whole group and leaving
guardrail G1 to discover after the fact that the "single answer" was 30 rows.

**Direction is not always inferable.** `most/highest/largest/top` → `DESC`,
`least/lowest/smallest/bottom` → `ASC`. But `best` and `worst` depend on whether
the metric is one you want high or low — the *worst* return rate is the highest,
the *worst* revenue is the lowest — and that is a property of the column, which
this layer does not know. Those emit no ordering and raise
`ORDERING_DIRECTION_AMBIGUOUS` for Member 1 to resolve with schema knowledge,
rather than guessing.

**Post-execution, the bound is applied only when it can be proved.** If the SQL
returns 30 rows for an inferred top-5, the table block trims to 5 *only* when
the result is verifiably sorted on the ordering column. Trimming an unordered
result would present an arbitrary five as "the most", which is worse than
showing everything — so in that case the rows are left intact and
`implied_limit_applied: false` reports the unapplied bound with its reason.
`row_count` is always the true total either way.

### Chart hint follows the response shape

The analytical intent proposes an encoding — `RANKING` maps to `bar` — but the
response intent is the authority on presentation. If the user asked *which
department spends the most*, a bar-chart hint advertises output they did not
ask for, so `CHART_HINT_BY_RESPONSE` overrides it:

| Response intent | `recommended_chart` |
|---|---|
| `SINGLE_ANSWER` | `kpi_card` |
| `TABLE_CONTENT` | `table` |
| `SHORT_SUMMARY` | `none` |
| `CHART`, `MIXED_SUMMARY` | the analytical encoding, unchanged |

The pipeline goes further and **does not build the chart at all** when the
decided blocks contain no `CHART`. This is safe because guardrails never
*promote* a shape to `CHART` — they only move away from it when the data cannot
support one — so deciding early cannot leave a later stage wanting a spec that
was never made. The `visualization` key stays in the envelope with
`chart_type: "none"` and `skipped: true`, so the contract does not change shape
between requests. LLM narration is gated the same way: claims are always
computed (cheap, deterministic, part of the existing contract), but the paid
narration call is skipped when no `SUMMARY` block will be rendered from it.

### Stage B — analytic prior

When Stage A is weak, the analytical intent arbitrates. Each mapping is a claim
about the question's natural shape:

- a scalar question has one answer → `SINGLE_ANSWER`
- row retrieval has no aggregate to plot → `TABLE_CONTENT`
- everything else describes a *relationship* between values, and a relationship
  is what a chart exists to show → `CHART`

Stage B is **skipped when the user named a format explicitly** (a tier-4 hit for
the winner). Low confidence there reflects a contest between two named formats —
"the chart or maybe just the number" — not an absence of evidence, and the
analytical intent, which knows nothing about presentation, has no standing to
overrule the user's own words.

### Stage C — guardrails

The pre-execution verdict is re-checked against the rows that actually came
back. Guardrails fire **only on a contradiction the result set proves**, never on
a second reading of the language, and each repair is recorded in
`guardrails_applied` alongside the intent it replaced.

| Rule | Condition | Repair |
|---|---|---|
| **G0** | zero rows | anything → `TABLE_CONTENT`; a chart or a scalar over an empty set fabricates an answer |
| **G1** | `SINGLE_ANSWER` but the result is >1 row or >2 columns | → `TABLE_CONTENT` |
| **G2** | `CHART` but no measure, no axis, or <2 points | → `SINGLE_ANSWER` or `TABLE_CONTENT` |
| **G3** | `TABLE_CONTENT` over a 1×1 grid, not explicitly requested | → `SINGLE_ANSWER` |
| **G4** | `MIXED_SUMMARY` over unplottable data | keep the intent, drop the `CHART` block |

G1 is the load-bearing one. "What was our highest monthly revenue?" classifies as
`SINGLE_ANSWER`, but if the executed SQL returns 6 monthly rows rather than the
maximum, presenting one of them as *the* answer would be a lie about the data.
The guardrail catches the mismatch and returns the table, recording:

```
G1 scalar contradicted: result is 6x2, not one value -> TABLE_CONTENT
```

## 4. Arbitration with the LLM

The model votes on `response_intent` through the same closed vocabulary
(`prompts.py`), and its vote is parked in metadata until the deterministic
verdict exists. It may override the rules only when **it is confident (≥ 0.60)
AND the rule verdict was itself weak (< 0.55)**. A confident rule verdict is
never overturned by the model.

This keeps the offline accuracy figures a genuine floor: the numbers in §5 were
produced with no network access at all, and enabling the LLM can only move
low-confidence cases.

## 5. Evaluation

Two corpora, both in this directory:

- `response_intent_dataset.csv` — 125 labelled inputs. **Development split: the
  rules were tuned against it.**
- `response_intent_holdout.csv` — 50 labelled inputs, written afterwards and
  **not tuned against**.

Run either:

```
python evaluate_response_intent.py                                    # dev
python evaluate_response_intent.py --dataset response_intent_holdout.csv
```

Each run writes `<dataset>_predictions.csv` — one row per input recording the
expected label, what the engine actually said, `CORRECT`/`WRONG`, the confidence,
the source stage and the full rationale. That file is the record of the existing
state: re-run after any lexicon change and diff the two to see exactly which
inputs moved.

### Results (deterministic engine, no LLM)

| Corpus | Accuracy | Well-formed | Degraded |
|---|---|---|---|
| Development (125) | 100.0% | 100.0% (77/77) | 100.0% (48/48) |
| Hold-out (50) | 100.0% | 100.0% (32/32) | 100.0% (18/18) |

Macro-F1 is 1.00 on both, with a clean diagonal confusion matrix.

**These numbers need two honest caveats.**

First, the development figure is a *fit* statistic, not a generalisation
estimate. The rules were iterated against that corpus until it passed; 100% on
it means the ruleset is consistent with its own training data and nothing more.
The evaluation started at 80.8% and the 23 initial errors are what produced R3a/
R3b, the lexical repair step, and the Stage B skip condition; R3d and the
entity-focus split came later, from real questions asked of the prototype.

Second, the hold-out corpus was written by the same author as the rules, so it
shares phrasing priors that real users will not. A clean 50/50 says the rules
generalise beyond the exact strings they were tuned on; it does **not** establish
a production accuracy figure. The corpus that would establish one is real logged
user queries, which do not exist yet at this stage of the project. Treat 100% as
"no known failure mode in 175 inputs", not as an expected field accuracy.

### Input-quality coverage

Accuracy is reported broken down by input quality, never as a single headline
number: a classifier that scores well on clean input and collapses on typos is
not shippable. The corpora deliberately include inputs a real user gets wrong.

| Quality | Meaning | Dev | Hold-out |
|---|---|---|---|
| `WELL_FORMED` | clean, unambiguous | 77 | 32 |
| `MIXED_SIGNAL` | markers from two families collide | 16 | 6 |
| `ELLIPTIC` | fragments — "maximum salary", "list" | 10 | 2 |
| `TYPO` | misspelled decisive markers | 6 | 4 |
| `VAGUE` | no clear subject | 5 | 1 |
| `AMBIGUOUS` | genuinely two readings | 3 | 1 |
| `NON_DATA` | greetings, keyboard mash | 3 | 2 |
| `ADVERSARIAL` | prompt / SQL injection attempts | 3 | 1 |
| `EMPTY` | empty or whitespace-only | 2 | 1 |

On `ADVERSARIAL` inputs the classifier's job is *only* to return a renderable
shape. Injection detection, PII flagging and tenant enforcement all happen
upstream in `query_analyzer` and Member 3's layer; the tests confirm the shape
verdict is not derailed by the injected text, not that the request is safe.

### Calibration

Two dev inputs and one hold-out input were flagged
`LOW_CONFIDENCE_RESPONSE_INTENT` (< 0.45); none of them were wrong. The
distinction the harness reports is deliberate: an error the engine flagged is a
*degraded* answer the UI can hedge, while an error it was confident about is a
*wrong* answer. Only the second kind is dangerous.

## 6. Files

| File | Role |
|---|---|
| `schemas.py` | `ResponseIntent`, `ResponseBlock`, `RESPONSE_BLOCKS`, `ResponseIntentResult`; new fields on `QueryAnalysis` |
| `response_intent.py` | Stages A, B and C — markers, repair, precedence rules, guardrails |
| `response_renderer.py` | block assembly; enforces the intent-to-blocks contract |
| `query_analyzer.py` | calls `classify()` after the analytical intent settles; arbitrates the LLM vote |
| `pipeline.py` | runs Stage C and the renderer as Part 5; adds `response` to the envelope |
| `prompts.py` | the closed `response_intent` vocabulary given to the model |
| `response_intent_dataset.csv` | 125-input development corpus |
| `response_intent_holdout.csv` | 50-input hold-out corpus |
| `evaluate_response_intent.py` | benchmark harness; writes the predictions CSV |
| `test_response_intent.py` | 52 assertions over focus, chart suppression, guardrails and the block contract |

## 7. Envelope shape

`pipeline.run()` gains a top-level `response` key:

```json
{
  "response": {
    "response_intent": {
      "intent": "MIXED_SUMMARY",
      "confidence": 0.9625,
      "source": "RULE",
      "rationale": "Lexical evidence 9.5 for MIXED_SUMMARY vs ...",
      "blocks": ["SUMMARY", "TABLE", "CHART"],
      "evidence": { "scores": {...}, "matched_markers": {...},
                    "runner_up": "CHART", "margin": 0.42 },
      "guardrails_applied": [],
      "original_intent": "MIXED_SUMMARY",
      "warnings": []
    },
    "blocks_emitted": ["SUMMARY", "TABLE", "CHART"],
    "blocks_declared": ["SUMMARY", "TABLE", "CHART"],
    "summary": { "text": "...", "claim_count": 6, "verified": true },
    "table":   { "columns": [...], "rows": [...], "row_count": 24,
                 "truncated": false },
    "chart":   { "chart_type": "line", "spec": { ... } }
  }
}
```

Blocks the intent did not request are **absent, not empty**, so a client can
branch on key presence alone. `analysis.response_intent` carries the
pre-execution verdict for callers who need it before SQL runs.

## 8. Known limits at this stage

1. **No real user data.** Both corpora are authored. The first priority once the
   system is in front of users is to replace the hold-out set with logged
   queries and re-baseline; the current numbers will fall.
2. **English only.** Markers, the repair vocabulary and the protected list are
   all English. Another language needs its own lexicon, not a translation.
3. **The protected token list is empirical.** It grows by collision. A larger
   format vocabulary raises the chance of an unguarded collision, so entries
   should be added to `_FORMAT_VOCAB` only with a matching test.
4. **`MIXED_SUMMARY` always claims three blocks.** G4 drops the chart when the
   data cannot support it, but there is no rule yet for dropping the table on a
   very large result set — it is bounded at 200 rows instead.
5. **Stage B never escalates to `MIXED_SUMMARY`.** No analytical intent implies a
   full report, so a mixed response requires the user to ask for one lexically.
   This is intentional — a report is expensive and should not be inferred — but
   it means paraphrases the lexicon misses degrade to a single block.
