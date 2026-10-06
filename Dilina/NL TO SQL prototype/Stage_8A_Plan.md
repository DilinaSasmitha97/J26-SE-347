# 🔬 Stage 8A Implementation Plan: Canonical Join Routing & Graph Subgraph Guidance
**Project:** Secure Multi-Tenant Natural Language Interface for Database Querying (J26-SE-347)  
**Lead Component:** Member 1 (Sasmitha A W D - IT23143418) — Schema-Aware NL-to-SQL Translation Engine  
**Target Baseline to Beat:** Stage 7 (**83.56% Yale Execution Accuracy / 80.37% Strict Set Accuracy**)  
**Standardized Foundation Model:** `Qwen/Qwen-2.5-Coder-32B-Instruct` via OpenRouter  

---

## 🎯 1. Scientific Objective & Hypothesis

### The Problem in Stage 7
In Stage 7, precision cell-value grounding eliminated 21 result mismatches, but **Join Errors increased from 15 to 23**. Forensic analysis revealed why:
* When categorical values were cleanly grounded to specific columns, the LLM became overconfident in writing **modular nested subqueries (`WHERE col IN (SELECT ...)`)** instead of canonical SQL joins (`FROM A JOIN B ON ...`).
* Subqueries frequently mishandled `NULL` values (e.g., student permanent addresses), symmetric edges (e.g., high school friends), or multi-table `OR` filters.
* Because the resulting tuple set differed from Gold and the predicted query did not contain the literal word `"JOIN"`, the evaluation harness classified all 23 cases as `JOIN_ERROR`.

### The Stage 8A Hypothesis
> **Hypothesis:** Augmenting the pruned schema context with **intent-weighted, negation-guarded canonical join skeletons** (generated via Dijkstra relational graph traversal) will guide the LLM to synthesize syntactically and semantically correct relational joins over error-prone nested subqueries, **reducing Join Errors from 23 to $< 10$ and pushing Yale Execution Accuracy past 84.5%**, without degrading the 89.74% Easy-tier accuracy or introducing syntax errors.

---

## 🛡️ 2. Comprehensive Failure Mode & Regression Defense

To guarantee we do not repeat the mistakes of Stage 4 (prompt poisoning) or introduce regressions, Stage 8A incorporates four strict architectural defenses:

```
                                  [ Pruned Subgraph Schema ]
                                               │
                                               ▼
                              { Selected Tables Count >= 2? }
                                     │                   │
                                   NO│                 YES│
                                     ▼                   ▼
                           [ SILENT: No Hints ]   { Negation Intent Detected? }
                                                         │                   │
                                                       YES│                 NO│
                                                         ▼                   ▼
                                            [ Negation Anti-Join Hint ]   [ Compute Lexical-Weighted Dijkstra ]
                                            (Suggests LEFT JOIN / NOT IN) (Selects Intent-Aligned Foreign Key)
                                                         │                   │
                                                         └─────────┬─────────┘
                                                                   │
                                                                   ▼
                                                    [ Gated Canonical Join Skeleton ]
                                                    (Max 1-2 Routes, Zero Easy-Query Spam)
```

| Failure Mode | Root Cause | Stage 8A Preventive Architecture |
| :--- | :--- | :--- |
| **1. Anti-Join & Negation Suppression** | Blindly suggesting `A JOIN B` breaks negative queries (*"students with NO pets"*, *"channels NOT playing X"*). | **Negation Intent Detector (`is_negation_intent`):** Scans for negation tokens (`not`, `no`, `never`, `without`, `except`, `neither`). If detected, either suppresses inner join hints or explicitly suggests a `LEFT JOIN ... WHERE B.id IS NULL` or `NOT IN` skeleton. |
| **2. Multi-Hop Shortest-Path Bias** | Dijkstra picking an arbitrary edge when multiple FK paths exist (e.g. `flight_2` `SourceAirport` vs `DestAirport`). | **Lexical Intent Edge Weighting:** Prioritizes edges whose foreign key column names have lexical token overlap with the natural language query before falling back to topological distance. |
| **3. Easy Query Prompt Poisoning** | Spamming obvious join paths on simple single-table or trivial 1-hop queries. | **Strict Minimal Gating:** Emits **zero join hints** if only 1 table is pruned, or if the relationship is self-evident and unambiguous. Capped at a maximum of 2 join skeletons. |
| **4. Token Bloat Regression** | Adding excessive DDL commentary that displaces few-shot exemplars. | **Compact Relational Skeleton:** Formats hints as single-line structural recommendations rather than multi-line verbose blocks (budget: $< 35$ tokens). |

---

## 🏗️ 3. Concrete Code Architectural Changes

### Component 1: `relationship_mapper.py` Upgrade
1. **Add `detect_negation_intent(nl_query: str) -> bool`:**
   ```python
   NEGATION_PATTERN = re.compile(
       r'\b(no|not|never|neither|nor|without|except|excluding|don\'t|doesn\'t|didn\'t)\b', 
       re.IGNORECASE
   )
   ```
2. **Add `find_intent_weighted_path(...)`:**
   Scores competing FK edges between tables by matching column tokens against `nl_query` (e.g., if query mentions `"destination"`, edge `DestAirport` receives priority over `SourceAirport`).
3. **Add `generate_canonical_join_skeleton(...)`:**
   Transforms graph steps into a clean structural template:
   ```sql
   -- Recommended Join: FROM table1 JOIN table2 ON table1.fk = table2.pk
   ```
   If negation is detected:
   ```sql
   -- Recommended Negative Pattern: FROM table1 WHERE table1.id NOT IN (SELECT table2.fk FROM table2 ...)
   ```

### Component 2: `main.py` Integration & Gating
* Refine the Task 4B injection hook:
  * Only invoke when `len(selected_tables) >= 2`.
  * Pass `nl_query` to `relationship_mapper.get_subgraph_join_paths` to enable lexical weighting and negation detection.
  * Inject the resultant skeleton string into `prompts.generate_crp_prompt(join_paths=...)`.

### Component 3: `prompts.py` Verification
* Ensure `join_paths` placeholder in `generate_crp_prompt` renders immediately above dynamic exemplars without corrupting the DDL comment block.

---

## 🔬 4. Step-by-Step Execution Roadmap

```
Step 1: Git Branch Creation (`stage-8a-join-router`)
   └── Isolate Stage 8A from Stage 7 production baseline
Step 2: Engine Implementation (`relationship_mapper.py` + `main.py`)
   └── Add negation detector, lexical edge weighting, and skeleton generator
Step 3: Unit Testing Suite (`test_relationship_mapper.py`)
   └── Test negation handling, multi-path resolution, and 1-table gating
Step 4: Targeted Smoke Benchmark (Targeting Stage 7 Join Errors)
   └── Run evaluate on the 23 Join Error queries (Idx 152, 226, 355, 550, 584, 636, 769, 897)
Step 5: Full Spider Validation Benchmark ($N = 1,034$)
   └── Standardized model: Qwen/Qwen-2.5-Coder-32B-Instruct via OpenRouter
Step 6: Diff-in-Diff Confusion Matrix Analysis
   └── Automated script comparing Stage 7 vs Stage 8A predictions
Step 7: Verification Against Hard Gate Criteria
   └── Accept or Rollback based on empirical metrics
```

---

## 🧪 5. Verification & Testing Protocol

### A. Pre-Benchmark Unit Tests (`test_relationship_mapper.py`)
* `test_negation_intent_detection`: Verifies queries with "no friends" or "not enrolled" trigger negative pattern skeletons.
* `test_lexical_weighted_disambiguation`: Verifies `flight_2` with "destination" picks `DestAirport` over `SourceAirport`.
* `test_single_table_gating`: Verifies queries selecting only 1 table produce empty string `""` (zero prompt pollution).

### B. Targeted Pre-Flight Smoke Test
Run evaluation on a 25-sample subset containing the primary Stage 7 `JOIN_ERROR` samples:
```powershell
python evaluate.py -n 25 -d all
```
Verify that the model successfully synthesizes `JOIN`s for Idx 584 and Idx 769 without breaking syntax.

### C. Full Benchmark ($N = 1,034$)
Run full evaluation:
```powershell
python evaluate.py -n 1034 -d all
```

### D. Automated Diff-in-Diff Confusion Matrix
Run a differential comparison script (`scratch/diff_stage7_vs_stage8a.py`):
```
Stage 7 -> Stage 8A Ledger:
- HEALED: (Stage 7 FAIL -> Stage 8A PASS): count & query IDs
- REGRESSED: (Stage 7 PASS -> Stage 8A FAIL): count & query IDs
- NET DELTA: Healed - Regressed
```

---

## 🛑 6. Hard Gate Exit & Acceptance Criteria

To be accepted as the new SOTA baseline and advance to Stage 8B:

| Metric | Stage 7 Baseline | Stage 8A Acceptance Threshold | Decision Rule |
| :--- | :---: | :---: | : |
| **Yale Execution Accuracy** | **83.56% (864 / 1,034)** | **$\ge 84.40\%$ ($\ge 873 / 1,034$)** | **Must be strictly greater than Stage 7** |
| **Strict Set Accuracy** | 80.37% (831 / 1,034) | $\ge 81.00\%$ | Supporting validation |
| **Join Errors** | 23 | **$\le 12$** | Primary objective validation |
| **Syntax Errors** | 0.0% (0 / 1,034) | **0.0% (0 / 1,034)** | Zero tolerance for syntax regression |
| **Easy Tier Accuracy** | 89.74% (411 / 458) | **$\ge 89.50\%$** | Guard against Easy-tier prompt poisoning |
| **Net Query Delta** | Reference | **$\ge +10$ queries net** | $\text{Healed} - \text{Regressed} \ge +10$ |

### Rollback / Pivot Strategy
* If Stage 8A results in a net regression (e.g., Yale EX drops below 83.56%), **immediately rollback to branch `dilina-nl-to-sql-prototype-stage-7-database-probing`**.
* Dissect the regressed queries using the confusion matrix to identify whether negation suppression or edge misweighting occurred, adjust the gating invariants, and re-test.
