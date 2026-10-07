# Stage 4 Completion Report — Component 4 (Visualization & Prediction Layer)

5 October 2026 · Wijethunge W M V (IT23256750) · Project J26-SE-347

## Summary

Stage 4 covers the two places where the component turns language into numbers or numbers into language:

- **The what-if parser**, which reads a scenario such as "what if we cut spending by 20%".
- **The summary verifier**, which decides whether an LLM-written summary may be shown.

Both were measured before they were changed, then measured again with the same benchmarks.

Headline results:

- **What-if parsing:** on 94 labelled phrasings, the parser went from about half correct to all correct.
  - On the held-out TEST questions, it went from 15 of 30 to 30 of 30 correct.
  - Wrong simulations on those TEST questions (a confident chart for the wrong scenario) went from **12 to 0**.
  - Caveat: the test phrasings and the parser's word lists are by the same author. So this shows the known phrasing types are covered, not that real users' wording will be.
- **Summary verifier:** fault injection on the claims of the 12 benchmark scenarios.
  - Numbers off by 5% are now caught **98%** of the time (was 48%).
  - Correct rewrites the old verifier wrongly rejected ("48.3k", "6,040-6,869", reworded dates) now pass (false rejections **0%**, was 75–100%).
  - Invented numbers written as words are caught **98%** of the time (was 0%).
- **Live LLM narration** (Groq, `openai/gpt-oss-120b`): all 12 narrations were verified and shown. None were rejected, so live use did not exercise the rejection path; the fault injection is the evidence for it.

All Stage 4 work is in the working tree of branch `vonara-nl-to-sql-prototype-stage-4`, which contains Stages 1–3. Nothing has been committed or pushed, and `main` is untouched.

## Starting point

| What was measured | Before Stage 4 | What it meant |
| --- | --- | --- |
| What-if parsing | No benchmark; 3 test phrasings | The known "unless" bug was the tip of the problem |
| Direction words | Matched as substrings | "unless" → "less" (decrease); "supplier" and "group" → "up"; "execute" → "cut" |
| Question route | A clause with a magnitude but no direction word was simulated as a **decrease** | "assuming sales rise 5%" showed a 5% fall |
| Two parsers | The analyzer and the simulate box each had their own copy | The same words could be read two ways |
| Verifier | A number passed if within 2% of *any* number in any claim | Untested; LLM narration never measured |

## Work completed

1. **Labelled what-if test set** (`whatif_testset.json`): 94 phrasings, 64 DEV and 30 TEST, written before any parser change. Its phrasing types are substring traps, negations, two changes, ranges, absolute amounts, target levels ("to 80%"), multipliers, signs, ramp wording, other numbers in the sentence, and vague requests.
2. **What-if benchmark** (`evaluate_whatif.py`). It scores both routes: the simulate box (`parse_scenario`) and a what-if inside the question (analyzer → `scenario_from_analysis`). It separates *wrong simulations* from *refusals of valid scenarios*, the safer failure. The Stage 3 parser's results are saved as the baseline.
3. **One scenario parser** (`scenario_language.py`), used by both routes:
   - **Whole words only.** The direction word nearest the number decides.
   - **Refuses rather than guesses**, with a reason code for each kind of refusal:

     | Case | Reason code |
     | --- | --- |
     | negated | `NEGATED` |
     | two changes | `MULTIPLE_CHANGES` |
     | range | `RANGE` |
     | money or headcount | `ABSOLUTE_AMOUNT` |
     | no direction word | `NO_DIRECTION` |
     | no percentage | `NO_MAGNITUDE` |
   - **Reads more forms:**
     - target levels ("cut to 80%" is a 20% cut)
     - multipliers (double, triple, quadruple, halve, twice)
     - signs ("-8%")
     - comparatives ("10% less", "15% lower")
   - **Bounds:** increases up to 300%, decreases up to 100%.
   - The question route keeps ramp wording ("gradually"), which it used to drop.
   - A clause with no direction word is never simulated as a decrease. An LLM analysis may fill in only a missing direction or magnitude, and never overrides a refusal.
4. **Precision-aware verifier** (`summarization.verify_summary`).
   - **The rule:** a narrated number passes only if a claim number lies within the precision it is written at.
     - "48.3k" covers 48,250–48,350.
     - "6,454" covers 6,453.5–6,454.5.
     - "48,300" keeps at least two significant figures, so it covers 48,250–48,350.
   - **What it now reads correctly:**
     - k, million and billion suffixes
     - ISO dates, of which only the year is checked
     - hyphen ranges ("6,040-6,869" is two positive numbers, not a minus sign)
     - numbers written as words, from "two" to "ninety-nine", plus hundreds, thousands and millions ("one" is excluded because of "one of", "one-off")
   - The old relative rule is kept behind a parameter, for the benchmark comparison only.
5. **Verifier benchmark** (`evaluate_verifier.py`). It applies seven kinds of correct rewrite, seven kinds of corruption and three known blind spots to the claim sets of the 12 scenarios. With `--live N`, it also narrates through the production function (`render_with_llm`) and records, for each narration, what the old rule would have decided.
6. **Audit field.** `summary.rejected_narration` keeps a narration the verifier refused, so rejections can be reviewed. It is never shown as the summary.
7. **Tests.** `test_whatif.py` has 30 checks covering whole words, refusals, amounts, route agreement and the verifier.

## Results

### What-if parsing (`whatif_benchmark.md`)

| Split, route | Stage 3 correct | Stage 3 wrong simulations | Stage 4 correct | Stage 4 wrong simulations |
| --- | --- | --- | --- | --- |
| TEST, question | 15 / 30 | 12 | **30 / 30** | **0** |
| TEST, simulate box | 14 / 30 | 7 | **30 / 30** | **0** |
| DEV, question | 29 / 59 | 22 | 59 / 59 | 0 |
| DEV, simulate box | 33 / 64 | 18 | 64 / 64 | 0 |

By phrasing type, question route, DEV + TEST, Stage 3 → Stage 4:

| Phrasing type | Stage 3 | Stage 4 |
| --- | --- | --- |
| Substring traps | 6 / 15 | 15 / 15 |
| Two opposite changes | 0 / 4 | 4 / 4 |
| Ramp wording | 1 / 6 | 6 / 6 |
| Target levels | 0 / 4 | 4 / 4 |
| Ranges | 0 / 3 | 3 / 3 |
| Negations | 2 / 5 | 5 / 5 |

### Summary verifier (`verifier_benchmark.md`, seed 2026)

| Narration | Cases | Stage 3 | Stage 4 |
| --- | --- | --- | --- |
| **Correct rewrites, share wrongly rejected** | | | |
| As written, no separators, rounded to 3 significant figures | 12 each | 0% | 0% |
| "48.3k" / "1.23 million" | 12 | 91.7% | **0%** |
| "6,040-6,869" | 12 | 100% | **0%** |
| Reworded dates | 12 | 75.0% | **0%** |
| Claim numbers written as words | 6 | 0% | 0% |
| **Corrupted narrations, share caught** | | | |
| One number off by 5% / 10% / 25% | 60 each | 48.3% / 66.7% / 68.3% | **98.3% / 100% / 100%** |
| Digits transposed | 60 | 58.3% | **100%** |
| Invented value / 10× value | 60 each | 96.7% / 98.3% | 96.7% / 98.3% |
| Invented number written as a word | 60 | 0% | **98.3%** |
| **Blind spots (a number-only check cannot see these)** | | | |
| One number off by 1.5% | 60 | 0% | 93.3% |
| Two correct numbers swapped | 60 | 8.3% | 8.3% |
| "increased" → "decreased" | 12 | 0% | 0% |

The old rule's weakness was density. In a monthly series the legitimate numbers sit close together, so a wrong number usually landed within 2% of some *other* legitimate one: 31 of the 60 off-by-5% numbers did. Matching to the written precision removes most of those collisions.

### Live LLM narration

Run with Groq's `openai/gpt-oss-120b` on the 12 benchmark scenarios. **12 of 12 narrations were verified and shown; none were rejected**, and the old rule agrees on all 12. I read two narrations against their claims and found no swapped numbers or reversed directions. The model mostly merges claim sentences and keeps numbers verbatim.

### Regression

| Check | Result |
| --- | --- |
| Test suites (8) | All pass: test_whatif 30, test_anomaly 19, test_component 61, test_strategies 24, test_forecast_delivery 42, test_readiness 23, test_input_adapter 27, test_response_intent |
| Intent classification | 100%, unchanged |
| Response-shape evaluation | 125 / 125, unchanged; compared before and after the change on the same code base |
| Summary grounding | 100% (415 numbers; the count was 465 before, when ISO dates were read as three numbers each) |

## What this means for the research claims

- **What-if engine.** It is now safe in a specific sense: on every labelled phrasing it either simulates the right change or says why it won't. Before, 23–40% of phrasings, depending on route and split, produced a confident chart for the wrong scenario. The claim to make is "refuses what it cannot read", not "understands any phrasing".
- **Claim verification.** The verifier has measured detection and false-alarm rates instead of an untested design. The live run shows it does not block a well-behaved model, but it has not yet caught a real LLM error because none occurred. Both facts should be reported.

## Limitations and open issues

1. **Author-written what-if set.** The test phrasings and the word lists come from the same person. The TEST wording (climb, jump, slash, trim) was seen before the word lists were finalised. A set of 30–50 phrasings written by teammates or test users is the needed independent check.
2. **One change at a time.** "Raise prices 5% and cut costs 3%" is refused, not simulated as two changes. Absolute amounts ("$500") are refused too, because the engine only applies percentage changes.
3. **Verifier blind spots.** It checks numbers, not meaning. Two correct numbers swapped between sentences, or "increased" written as "decreased", pass. Closing these needs claim-level checks (which claim a sentence states, and its direction).
4. **Live narration is small.** 12 scenarios and one model, with no rejections observed. More scenarios, a second model (Gemini is configured), and a deliberately weaker model would show the rejection rate in use.
5. **Where narration runs.** The pipeline narrates only when the response includes a written summary, so chart-only answers always use the deterministic text. This is by design, but it means the live run had to call the narration function directly.
6. **Not run:** the MySQL harness (still needs `MYSQL_ADMIN_PASSWORD`), and the forecasting and anomaly benchmarks. Their code was not changed in Stage 4.

## Files

| File | Change |
| --- | --- |
| `scenario_language.py` | New: the shared scenario parser |
| `whatif.py` | Uses the shared parser; `reason_code`; bounds; `scenario_from_analysis` re-reads the clause |
| `query_analyzer.py` | `_detect_what_if` uses the shared parser; substring marker lists removed |
| `summarization.py` | Precision-aware `verify_summary`; `rejected_narration` |
| `evaluate_whatif.py`, `whatif_testset.json` | New: what-if benchmark and labelled phrasings |
| `evaluate_verifier.py` | New: verifier fault injection and live run |
| `test_whatif.py` | New: 30 checks |
| `test_component.py` | Clamp check uses the new increase bound |
| `data_and_reports/` | README, roadmap, team contract, this report; benchmark reports and Stage 3 baselines |

**To reproduce:**
- `python evaluate_whatif.py`
- `python evaluate_verifier.py`
- `python evaluate_verifier.py --live 12` (sends the synthetic claim text to the LLM provider in `.env`)
- `python test_whatif.py`

## Next stage

Stage 5 is intent classification:
- Evaluate on a blind test set labelled by someone else.
- Fix future single-value questions ("How much will I spend next month?") getting a table instead of one number.
