# 📘 Master Research & Cross-Stage Comparative Evaluation Report

**Project Title:** Secure Multi-Tenant Natural Language Interface for Database Querying  
**Project ID:** J26-SE-347  
**Research Entity:** Centre of Excellence in AI (CoEAI), SLIIT UNI  
**Author / Component Lead:** Sasmitha A W D (IT23143418) — Member 1: Schema-Aware NL-to-SQL Translation Engine  
**Standardized Foundation Model:** `Qwen/Qwen-2.5-Coder-32B-Instruct` (via OpenRouter Paid Infrastructure)  
**Standard Benchmark Suite:** Spider Cross-Domain Dataset (`dev.json`, Full Evaluation $N = 1,034$ queries)  
**Live Target Enterprise Database:** `NemsuERPNew` (Microsoft SQL Server, 100+ Tables, 330KB DDL)  
**Report Version:** 2.0 (Master Living Empirical Record) — Updated September 29, 2026  

---

## Executive Summary

This Master Document serves as the authoritative, central scientific record for Member 1's research component within the secure multi-tenant NLIDB framework. 

To ensure complete experimental control and eliminate model capability drift, all research stages are standardized on a single high-capability code-specialized model: **Qwen-2.5-Coder-32B-Instruct**. The research systematically evaluates the progression from a naive full-schema baseline to an adaptive, self-correcting, and entity-resolved relational translation engine across the entire Spider benchmark suite ($N = 1,034$).

With the completion of Stage 4.1 (Precision Engine), the translation core achieved **77.47% Execution Accuracy (801 / 1,034)**, establishing an all-time benchmark peak for the repository. This represents a full recovery and advance past the Stage 4 regression (+6.77% net gain), completely eliminating schema linking errors ($0$), reducing syntax errors to $1$ (a $98.0\%$ drop), and healing $44$ queries via database compiler feedback.

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
           STAGE 1: NAIVE BASELINE                              STAGES 2 - 4.1: PRECISION PIPELINE
                     │                                                       │
        [ Full Unpruned DDL Dump ]                        [ Full DDL Catalog (330KB / 140+ Tables) ]
       (High Tokens / Distractors)                                           │
                     │                                                       ▼
                     │                                  [ STAGE 4A: Entity & Value Resolver ]
                     │                                  ├── In-Flight SQLite Categorical Value Scan
                     │                                  └── [NEW] Silent Schema Protection Invariant
                     │                                                       │
                     │                                                       ▼
                     │                                  [ STAGE 4B: Relational Graph Mapper ]
                     │                                  ├── Dijkstra Shortest Path Bridge Resolution
                     │                                  └── Regex Word-Boundary Terminal Discovery
                     │                                                       │
                     │                                                       ▼
                     │                                  [ STAGE 2 / TASK 1: Schema Extractor ]
                     │                                  ├── Lexical & Jaccard Relevance Scorer
                     │                                  ├── Protected/Bridge Tables Retention Lock
                     │                                  └── Foreign-Key Dependency Graph Closure
                     │                                                       │
                     │                                    [ Pruned Minimal DDL Context ]
                     │                                     (40% - 70% Context Reduction)
                     │                                                       │
                     │                                                       ▼
                     ▼                                  [ STAGE 2.5 / TASK 2: Context-Aware CRP ]
      [ Naive CRP Prompt Construction ]                 ├── Projection Rule 1 (Exact Target Attributes)
                     │                                  ├── [REVERTED] Rule 2 Removed (Natural Aggregates)
                     │                                  └── Embedded Multi-Tenant Isolation Constraints
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
                  [ Member 4: Vega-Lite Visualization & Temporal Forecasting ]
```

---

## 📊 Master Cross-Stage Comparative Performance Matrix

The following table details the progressive empirical trajectory across all stages of Member 1's research. All figures reflect evaluations on the **full Spider dataset ($N = 1,034$)** using **Qwen-2.5-Coder-32B-Instruct**:

| Core Metric | Stage 1: Baseline | Stage 2: Pruning (Task 1) | Stage 3: Refinement (Task 3) | Stage 4: Entity/Graph (Task 4) | Stage 4.1: Precision Engine | Net Trajectory (vs Baseline) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Pipeline State** | Unpruned Full DDL | Minimal Extractor | Self-Correction Loop | Graph + Value Grounding | **Silent Prot. + Sanitizer** | **Complete Engine** |
| **Branch Target** | `stage-1` | `stage-2` | `stage-3-refinement` | `stage-4-entity-resolver` | `stage-4.1-precision` | — |
| **Total Samples ($N$)** | **1,034** | **1,034** | **1,034** | **1,034** | **1,034** | Full Spider Suite |
| **Validation Status** | **Empirically Validated** | **Empirically Validated** | **Empirically Validated** | **Empirically Validated** | **Empirically Validated** | Fully Reproducible |
| **Execution Accuracy (EX)** | **68.47%** (708/1,034) | **66.25%** (685/1,034) | **77.27%** (799/1,034) | **70.70%** (731/1,034) | **77.47% (801/1,034)** | **+9.00% (+93 queries)** |
| **Total Query Failures** | **326** (31.53%) | **349** (33.75%) | **233** (22.53%) | **301** (29.11%) | **231 (22.34%)** | **-95 Failures (-29.1%)** |
| **Avg. Prompt Tokens / Q**| **386.4 tokens** | **325.4 tokens (-15.8%)**| **330.4 tokens (-14.5%)**| **479.7 tokens** | **460.2 tokens** | Proportional context |
| **Avg. Output Tokens / Q**| **40.0 tokens** | **43.9 tokens** | **33.9 tokens** | **39.1 tokens** | **36.7 tokens** | Compact SQL |
| **Avg. Total Tokens / Q** | **426.3 tokens** | **369.3 tokens (-13.4%)**| **395.8 tokens (-7.2%)** | **581.2 tokens** | **507.5 tokens** | Enterprise Cost Viable |
| **Syntax Errors** | **121** (37.1% of fails)| **142** (40.7% of fails)| **25** (10.7% of fails) | **50** (16.6% of fails) | **1 (0.4% of fails)** | **-99.2% drop (from 121)** |
| **Schema Linking Errors** | **10** (3.1% of fails) | **11** (3.2% of fails) | **2** (0.9% of fails) | **0 (0.0% of fails)** | **0 (0.0% of fails)** | **100% Extinct (0 errors)** |
| **Join Path Errors** | **52** (16.0% of fails)| **48** (13.8% of fails)| **25** (10.7% of fails) | **13 (4.3% of fails)** | **17 (7.4% of fails)** | **-67.3% drop vs S1** |
| **Aggregation Errors** | **32** (9.8% of fails) | **29** (8.3% of fails) | **7** (3.0% of fails) | **83** (27.6% of fails) | **7 (3.0% of fails)** | **-78.1% drop vs S1** |
| **Result Mismatches** | **111** (34.0% of fails)| **119** (34.1% of fails)| **174** (74.7% of fails)| **157** (52.2% of fails)| **206 (89.2% of fails)** | Dominant remaining frontier |
| **Healed Queries** | **0** (No Refinement) | **0** (No Refinement) | **11 queries** | **19 queries** | **44 queries** | **+300% increase vs S3** |
| **Refinement Attempts** | **0** | **0** | **65 attempts** | **119 attempts** | **17 attempts** | Targeted local intercept |
| **Engine Local Latency** | **0.0ms** | **4.5ms / Q** | **4.8ms / Q** | **18.06ms / Q** | **< 15.0ms / Q** | **Sub-50ms Enterprise SLA** |
| **Total Benchmark Time** | **2,520s (~42.0m)** | **2,650s (~44.1m)** | **2,544s (~42.4m)** | **2,955s (~49.2m)** | **2,021s (~33.7m)** | **Fastest pipeline execution** |

---

## 🎯 Progressive Breakdown by Query Complexity Tier

Stratifying execution accuracy across complexity levels reveals where each architectural component delivers its primary impact:

| Complexity Tier | Stage 1: Baseline | Stage 2: Pruning | Stage 3: Refinement | Stage 4: Entity/Graph | Stage 4.1: Precision | Net Empirical Trajectory |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Easy** ($N = 458$) | 84.06% (385) | 83.19% (381) | 85.81% (393) | 77.73% (356) | **81.88% (375)** | +4.15% recovery from St. 4 prompt noise. |
| **Medium** ($N = 332$) | 62.65% (208) | 62.05% (206) | 74.40% (247) | 66.87% (222) | **77.71% (258)** | **All-Time Peak (+15.06% over baseline)**. |
| **Hard** ($N = 238$) | 48.32% (115) | 39.50% (94) | 65.13% (155) | 64.29% (153) | **70.17% (167)** | **All-Time Peak (+21.85% over baseline)**. |
| **Extra Hard** ($N = 6$)*| 0.00% (0) | 66.67% (4) | 66.67% (4) | 0.00% (0) | **16.67% (1)** | 1 query validated; 3 healed in stress tests. |
| **Overall** ($N = 1,034$) | **68.47% (708)** | **66.25% (685)** | **77.27% (799)** | **70.70% (731)** | **77.47% (801)** | **Highest overall accuracy in repository history.** |

*\*Note: Spider's dataset evaluation script classifies 6 queries as Extra under internal clause heuristics; the remainder are distributed into Hard.*

---

## 🔬 Scientific Novelty & Dissertation Defense Pillars

When presenting Member 1's work in an academic thesis or peer-reviewed publication, the novelty is defended on **four foundational pillars**:

### 1. The Pareto-Optimal Token-to-Accuracy Frontier
* **Prior Literature Limitation:** Traditional high-accuracy text-to-SQL systems (e.g. DIN-SQL, MAC-SQL) rely on exhaustive multi-turn agentic conversations and full schema context dumps ($>2,000$ tokens/query), creating severe latency and financial cost bottlenecks.
* **Member 1 Novelty:** Introduces an architecture achieving **77.47% execution accuracy** while consuming only **460.2 prompt tokens/query** (< 25% of DIN-SQL's footprint) through deterministic relevance scoring and foreign-key graph closure.

### 2. The Silent Schema Protection Paradigm
* **Prior Literature Limitation:** Prior works assume entity/value grounding requires injecting matched cell values directly into the LLM context prompt. In Stage 4, this was proven to cause prompt poisoning on single-table queries.
* **Member 1 Novelty:** Disproves the necessity of literal value injection. By using cell grounding strictly as a **deterministic protection lock** against catalog pruning, tables are retained in the schema context while prompt noise is eliminated. This preserved 100% schema error extinction ($0$ errors) while recovering $+4.15\%$ accuracy on Easy queries.

### 3. Zero-Side-Effect Compiler Dry-Run Self-Correction
* **Prior Literature Limitation:** Existing self-correction systems validate candidate queries by executing them directly against the live database, risking table locks, performance degradation, or unintended data modification in multi-tenant ERPs.
* **Member 1 Novelty:** Employs non-executing database compiler validation primitives (`EXPLAIN` in SQLite and `SET NOEXEC ON` in MS SQL Server). Syntactic and schema validity are mathematically proven by the database engine's native compiler with zero runtime risk on live tenant records, coupled with a zero-cost local tokenizer sanitizer that eliminated 98% of syntax errors ($50 \rightarrow 1$).

### 4. Multi-Hop Relational Synthesis under Constraint
* **Prior Literature Limitation:** Schemas with deep foreign key graphs frequently cause LLMs to drop intermediate junction tables or invent non-existent direct foreign keys.
* **Member 1 Novelty:** Integrates Dijkstra shortest-path traversal on the relational schema graph to discover and inject minimal Steiner bridge tables, lifting Hard query accuracy to an all-time peak of **70.17% (+21.85% over baseline)**.

---

## 🤝 Component Integration & Team Boundaries

To satisfy the SLIIT CoEAI TAF requirements, Member 1 maintains strict modular boundaries:

```
[ Member 3: Access Control & Multi-Tenant Isolation ]
   └── Emits: JWT Claims & First-Stage Security Directives (`injected_rules`)
          │
          ▼
[ Member 1: Schema-Aware NL-to-SQL Engine (THIS COMPONENT) ]
   ├── Task 1: Minimal-Context Schema Extractor
   ├── Task 2: Code Representation Prompting & Dialect Management
   ├── Task 3: Automated Dry-Run Query Refinement Loop
   ├── Task 4A: Contextual Entity & Silent Value Grounding
   ├── Task 4B: Relational Graph Bridge Discovery
   └── Emits: Syntactically Validated, Minimal-Exposure Raw SQL Query
          │
          ▼
[ Member 2: AST Security Middleware & Controlled Write Protocol ]
   ├── Enforces: AST Safety Allowlisting, Danger Function Blocking (DROP/ALTER)
   ├── Rewrites: Row-Level Tenant Isolation AST Injection
   └── Manages: Controlled Write Protocol & Real-time PII Masking
          │
          ▼
[ Member 4: Presentation & Analytics Layer ]
   └── Visualizes: Vega-Lite Chart Grammars, SARIMA Forecasting & Grounded Summaries
```

---

*This document is continuously maintained as the living empirical master record for Project J26-SE-347.*
