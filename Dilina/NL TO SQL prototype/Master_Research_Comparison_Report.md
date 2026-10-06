# 📘 Master Research & Cross-Stage Comparative Evaluation Report

**Project Title:** Secure Multi-Tenant Natural Language Interface for Database Querying  
**Project ID:** J26-SE-347  
**Research Entity:** Centre of Excellence in AI (CoEAI), SLIIT UNI  
**Author / Component Lead:** Sasmitha A W D (IT23143418) — Member 1: Schema-Aware NL-to-SQL Translation Engine  
**Standardized Foundation Model:** `Qwen/Qwen-2.5-Coder-32B-Instruct` (via OpenRouter Paid Infrastructure)  
**Standard Benchmark Suite:** Spider Cross-Domain Dataset (`dev.json`, Full Evaluation $N = 1,034$ queries)  
**Evaluation Standard:** 100% Yale `test-suite-sql-eval` Metric Standard (Zhong et al., EMNLP 2020)  
**Live Target Enterprise Database:** `NemsuERPNew` (Microsoft SQL Server, 100+ Tables, 330KB DDL)  
**Report Version:** 4.0 (Master Living Empirical Record) — Updated October 5, 2026  

---

## Executive Summary

This Master Document serves as the authoritative, central scientific record for Member 1's research component within the secure multi-tenant NLIDB framework. 

To ensure complete experimental control and eliminate model capability drift, all research stages are standardized on a single high-capability code-specialized model: **Qwen-2.5-Coder-32B-Instruct**. The research systematically evaluates the progression from a naive full-schema baseline to an adaptive, self-correcting, entity-resolved, exemplar-augmented, and actively probed relational translation engine across the entire Spider benchmark suite ($N = 1,034$).

With the completion of **Stage 7 (Precision Value Grounding & Targeted Active Probing)**, the translation core achieved:
* **Official Yale Execution Accuracy (Primary SOTA Metric):** **83.56% (864 / 1,034)**, representing an absolute gain of **+1.26% (+13 queries)** over Stage 5 (82.30%) and **+15.09%** over the unpruned baseline (68.47%).
* **Strict Set Execution Accuracy (Legacy Baseline):** **80.37% (831 / 1,034)**, breaking the 80% ceiling for strict tuple matching (+13 queries over Stage 5's 79.11%).
* **Semantic Result Mismatch Reduction:** Cut result mismatches down to **133** (-21 semantic errors eliminated compared to Stage 5's 154).
* **Zero Syntax Errors:** Achieved **0 syntax errors (0.0%)** across all 1,034 queries through compiler-gated formatting.
* **Flawless Schema Linking:** Maintained **0 schema linking errors (0.0%)** across all 1,034 queries and 140+ database schemas.
* **Pareto-Optimal Token Economics:** Reduced average tokens per query to **575.6 tokens** (down from 638.8 in Stage 5), saving 63.2 tokens per query while improving accuracy.
* **All-Time Peak Across Complexity Tiers:** Reached all-time highs in Easy (**89.74%**), Medium (**82.83%**), Hard (**73.53%**), and Extra Hard (**50.00%**).

---

## Master System Architecture & Pipeline Flow

The diagram below illustrates the end-to-end operational lifecycle of Member 1's translation engine across all developmental stages:

```
                                  [ User Natural Language Query ]
                                                 │
                                                 ▼
             [ Member 3: Access Control & Rule Injection (injected_rules) ]
                                                 │
                     ┌───────────────────────────┴───────────────────────────┐
                     │                                                       │
           STAGE 1: NAIVE BASELINE                              STAGES 2 - 7: PRECISION PIPELINE
                     │                                                       │
        [ Full Unpruned DDL Dump ]                        [ Full DDL Catalog (330KB / 140+ Tables) ]
       (High Tokens / Distractors)                                           │
                     │                                                       ▼
                     │                                  [ STAGE 7: Precision Entity & Value Resolver ]
                     │                                  ├── In-Memory Categorical Index (200 vals/col)
                     │                                  ├── Targeted Active Single-Row Database Probing
                     │                                  ├── Anti-Hallucination Bidirectional Boundary Check
                     │                                  └── Protected Terminal Tables Retention Seed
                     │                                                       │
                     │                                                       ▼
                     │                                  [ STAGE 4B: Relational Graph Mapper ]
                     │                                  ├── Dijkstra Shortest Path Bridge Resolution
                     │                                  ├── Post-Pruning Subgraph Join Path Hints
                     │                                  └── Regex Word-Boundary Terminal Discovery
                     │                                                       │
                     │                                                       ▼
                     │                                  [ STAGE 2 / TASK 1: Schema Extractor ]
                     │                                  ├── Lexical & Jaccard Relevance Scorer
                     │                                  ├── Protected/Bridge Tables Retention Lock
                     │                                  └── Foreign-Key Dependency Graph Closure
                     │                                                       │
                     │                                                       ▼
                     │                                  [ STAGE 5 / TASK 2.5: Exemplar Selector ]
                     │                                  ├── In-Memory TF-IDF Subword N-Gram Index
                     │                                  └── Top-2 Syntactic Relational Blueprints (2.01ms)
                     │                                                       │
                     │                                    [ Pruned Minimal DDL Context ]
                     │                                     (40% - 70% Context Reduction)
                     │                                                       │
                     │                                                       ▼
                     │                                  [ Context-Aware CRP v2 Prompt ]
                     │                                  ├── Minimal Schema + Foreign Key Join Paths
                     │                                  ├── Targeted Column Disambiguation Hints (Max 2)
                     │                                  ├── 2 Few-Shot Exemplars (DAIL-SQL Inspired)
                     │                                  └── Multi-Tenant Isolation Constraints
                     │                                                       │
                     └───────────────────────────┬───────────────────────────┘
                                                 │
                                                 ▼
                         [ Foundation LLM: Qwen-2.5-Coder-32B-Instruct ]
                                                 │
                                                 ▼
                                        [ Raw Candidate SQL ]
                                                 │
                     ┌───────────────────────────┴───────────────────────────┐
                     │                                                       │
           STAGE 1: NO REFINEMENT                               STAGE 3 / TASK 3: REFINEMENT LOOP
                     │                                                       │
                     │                                        [ Compiler Dry-Run Validation ]
                     │                                        ├── SQLite: EXPLAIN <query>
                     │                                        └── MSSQL: SET NOEXEC ON; ...
                     │                                                       │
                     │                                                       ▼
                     │                                            { Dry-Run Compilation Valid? }
                     │                                           ┌───────────┴───────────┐
                     │                                        YES│                     NO│
                     │                                           │                       ▼
                     │                                           │           [ Zero-Cost Spacing Sanitizer ]
                     │                                           │           (Fixes P2ON, T1JOIN in 0.48ms)
                     │                                           │                       │
                     │                                           │           [ Targeted Error Re-prompt ]
                     │                                           │           (Max 2 Iterations)
                     │                                           │                       │
                     │                                           └───────────┬───────────┘
                     │                                                       │
                     ▼                                                       ▼
          [ Candidate Raw SQL ]                                  [ Verified & Cleaned SQL ]
                     │                                                       │
                     └───────────────────────────┬───────────────────────────┘
                                                 │
                                                 ▼
                    [ Member 2: AST Security Middleware & Controlled Write ]
                                                 │
                                                 ▼
                    [ Member 3: JWT Multi-Tenant Isolation Rewriter ]
                                                 │
                                                 ▼
                    [ Member 4: Execution Result & Vega-Lite Charting ]
```

---

## 7-Stage Master Comparative Matrix

All metrics are benchmarked on the exact same $N = 1,034$ Spider validation suite with identical system conditions and foundation model (`Qwen-2.5-Coder-32B-Instruct` via OpenRouter):

| Evaluation Dimension | Stage 1: Base | Stage 2: Prune | Stage 3: Refine | Stage 4: Entity | Stage 4.1: Precision | Stage 5: Exemplars | Stage 7: Probing (SOTA) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **System Architectural Novelty** | Unpruned DDL Dump | Minimal Extractor | Dry-Run Compiler Loop | Value Scan + Steiner | Silent Invariant + Sanitizer | In-Context Exemplars + Yale | Active Probing + Disambig |
| **Yale Execution Accuracy (Official)** | *N/A* | *N/A* | *N/A* | *N/A* | *N/A* | 82.30% (851) | **83.56% (864 / 1,034) [SOTA!]** |
| **Strict Set Accuracy (Legacy)** | 68.47% (708) | 66.25% (685) | 77.27% (799) | 70.70% (731) | 77.47% (801) | 79.11% (818) | **80.37% (831 / 1,034) [PEAK!]** |
| **Total Query Failures** | 326 (31.5%) | 349 (33.8%) | 233 (22.5%) | 301 (29.1%) | 231 (22.3%) | 181 (17.5%) | **165 (16.0%) [-49.4%]** |
| **Schema Linking Errors** | 10 (3.1%) | 11 (3.2%) | 2 (0.9%) | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%) [EXTINCT!]** |
| **Join Errors** | 52 (16.0%) | 48 (13.8%) | 25 (10.7%) | 13 (4.3%) | 17 (7.4%) | 15 (8.3%) | **23 (13.9%)** |
| **Aggregation Errors** | 32 (9.8%) | 29 (8.3%) | 7 (3.0%) | 83 (27.6%) | 7 (3.0%) | 8 (4.4%) | **9 (5.5%)** |
| **Syntax Errors** | 121 (37.1%) | 142 (40.7%) | 25 (10.7%) | 50 (16.6%) | 1 (0.4%) | 4 (2.2%) | **0 (0.0%) [FLAWLESS!]** |
| **Result Mismatches** | 111 (34.0%) | 119 (34.1%) | 174 (74.7%) | 157 (52.2%) | 206 (89.2%) | 154 (85.1%) | **133 (80.6%) [-21 ERRORS]** |
| **Queries Healed by Refinement** | 0 (No Loop) | 0 (No Loop) | 11 queries | 19 queries | 44 queries | 79 queries | **68 queries** |
| **Avg. Total Tokens / Query** | 425.2 | 358.1 | 362.8 | 528.3 | 507.5 | 638.8 | **575.6 tokens [-63.2 tokens]** |
| **Local Pipeline Latency / Query** | 0.0 ms | 4.5 ms | 4.8 ms | 18.06 ms | < 15.0 ms | < 28.0 ms | **< 25.0 ms (SLA Compliant)** |
| **Total Evaluation Wall-Clock** | 2,520s (~42m) | 2,650s (~44m) | 2,544s (~42m) | 2,955s (~49m) | 2,021s (~33.7m) | 1,884s (~31.4m) | **2,344s (~39.1m)** |

*(Note: Stage 6 Multi-Candidate Consistency Decoding regressed to 79.59% Yale EX with 3x token bloat and was cleanly documented as an empirical ablation on branch `dilina-nl-to-sql-prototype-stage-6-consistency-engine`.)*

---

## Complexity Tier Evolution Across All 7 Stages

| Difficulty Tier | Stage 1: Base | Stage 2: Prune | Stage 3: Refine | Stage 4: Entity | Stage 4.1: Precision | Stage 5: Exemplar | Stage 7: Probing (SOTA) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Easy ($N = 458$)** | 84.06% (385) | 83.19% (381) | 85.81% (393) | 77.73% (356) | 81.88% (375) | 88.65% (406) | **89.74% (411) [+5]** |
| **Medium ($N = 332$)** | 62.65% (208) | 62.05% (206) | 74.40% (247) | 66.87% (222) | 77.71% (258) | 82.53% (274) | **82.83% (275) [+1]** |
| **Hard ($N = 238$)** | 48.32% (115) | 39.50% (94) | 65.13% (155) | 64.29% (153) | 70.17% (167) | 71.01% (169) | **73.53% (175) [+6]** |
| **Extra Hard ($N = 6$)** | 0.00% (0) | 66.67% (4) | 66.67% (4) | 0.00% (0) | 16.67% (1) | 33.33% (2) | **50.00% (3) [+1]** |
| **Overall Total ($N = 1,034$)** | **68.47% (708)** | **66.25% (685)** | **77.27% (799)** | **70.70% (731)** | **77.47% (801)** | **82.30% (851)** | **83.56% (864) [+13]** |

---

## Key Scientific & Empirical Insights

### 1. Targeted Active Probing Beats Blind Sampling
In Stage 4 and 4.1, categorical discovery was restricted to a static 50-row sample (`LIMIT 50`). If an entity appeared at row 51 (such as car make `'amc hornet sportabout (sw)'`), the engine was completely blind to it. Stage 7 introduced **Targeted Active Probing**, executing a lightweight single-row query (`SELECT col FROM table WHERE col = ? OR col LIKE ? LIMIT 1`) when high-value entities miss the cache. This eliminated data blindness while adding $< 0.5\text{ms}$ local overhead.

### 2. Column Disambiguation vs. The Stage 4 Poisoning Trap
Stage 4 collapsed from 77.27% to 70.70% because it spammed prompts with 1:1 obvious hints (e.g. `-- Grounding: Pets.PetType = 'dog'`). Stage 4.1 retreated to total silence. Stage 7 established the optimal middle ground:
* **Silent Schema Protection:** 1:1 self-evident terms protect tables silently without emitting prompt text.
* **Precise Column Disambiguation:** When a multi-word entity lives in a non-obvious column (e.g. `'amc hornet sportabout (sw)'` in `car_names.Make` rather than `Model`), the engine emits an exact location hint (`-- Value Location: ... is found in column car_names.Make`). This prevented the model from inventing hallucinated joins to `model_list`.

### 3. Bidirectional Anti-Hallucination Boundaries
A critical defect in Stage 4 was loose substring matching (`val in term`), which erroneously mapped a 3-letter value (`'amc'`) to an entire 60-character sentence. Stage 7 enforced strict bidirectional token boundaries: candidate values must account for $\ge 70\%$ of the query term length or match an exact word boundary of length $\ge 4$. This eradicated false-positive column bindings.

### 4. Zero Syntax Errors (0 / 1,034)
Combining the Stage 4.1 compiler-gated spacing sanitizer with Stage 5's structural exemplars and Stage 7's clean CRP v2 prompts reduced syntax errors to **literally 0 (0.0%)** across the entire 1,034-sample suite.

### 5. Enterprise Product Translation (`NemsuERPNew`)
For our research group's enterprise product:
* In multi-tenant databases with 100+ tables, users refer to entities by business codes, vendor names, and customer acronyms.
* Active probing allows the engine to ground un-aliased business terms directly to specific enterprise columns in $< 5\text{ms}$, while strictly scoping queries by `Tenant_ID` to preserve Member 3 multi-tenant isolation.
