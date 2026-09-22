# 📊 Research Report: Stage 1 Naive Baseline Benchmark Evaluation (N = 1,034)

**Project Title:** Secure Multi-Tenant Natural Language Interface for Database Querying  
**Project ID:** J26-SE-347  
**Research Group:** CoEAI - Centre of Excellence for AI (SLIIT UNI)  
**Author / Component Lead:** Sasmitha A W D (IT23143418) — Member 1  
**Target Model:** Alibaba Cloud `Qwen/Qwen-2.5-Coder-32B-Instruct` (via OpenRouter)  
**Dataset:** Spider Full Evaluation Benchmark (`dev.json`, Sample Size: $N = 1,034$ queries across all difficulty tiers)  
**Date:** September 22, 2026  

---

## 📈 1. Executive Summary & Full Benchmark Metrics

In Stage 1 (Naive Baseline), the engine translates natural language queries into SQL by feeding the **unpruned, raw database schema (DDL)** directly to the foundation model within a standard Code Representation Prompt (CRP). This establishes the primary scientific control reference against which Stage 2 (Minimal-Context Schema Pruning) and Stage 3 (Automated Self-Correction Refinement) will be measured.

| Metric | Empirical Value | Notes / Significance |
| :--- | :--- | :--- |
| **Foundation Model** | `qwen/qwen-2.5-coder-32b-instruct` | 32B Code-Specialized Open-Weights Model |
| **Sample Size ($N$)** | **1,034 queries** (100% of Spider dev set) | Full cross-domain benchmark across 140+ relational schemas |
| **Successful Executions (Match)** | **708 / 1,034** | Result sets match gold SQL standard exactly |
| **Execution Accuracy (EX)** | **68.47%** | Rigorous baseline for unpruned zero-shot CRP translation |
| **Total Pipeline Failures** | **326 / 1,034** (31.53%) | Classified into granular failure taxonomy categories |
| **Total Evaluation Runtime** | **2,520.5 seconds (~42.0 minutes)** | Average cycle latency: ~2.44s per sample |
| **Total Tokens Consumed** | **440,827 tokens** | Total prompt + completion tokens |
| **Avg. Tokens per Query** | **426.3 tokens** | **386.4 prompt in** / **40.0 completion out** |
| **LLM Inference Time Ratio** | **78.9%** (1,988.6s of total runtime) | Network/model inference constitutes the dominant cost |

---

## 🎯 2. Query Complexity & Difficulty Tier Breakdown

The Spider dataset classifies queries into four complexity tiers based on SQL clauses, aggregations, and number of joins. The Stage 1 baseline exhibits a distinct accuracy decay curve as relational query complexity increases:

| Complexity Tier | Available Matching Queries | Correct (Match) | Execution Accuracy | Analysis & Observations |
| :--- | :---: | :---: | :---: | :--- |
| **Easy** | 458 | 385 | **84.06%** | High baseline competence on single-table selections and simple `WHERE` filters. |
| **Medium** | 332 | 208 | **62.65%** | Moderate degradation when handling 1-2 joins and basic `GROUP BY` / `HAVING` clauses. |
| **Hard** | 238 | 115 | **48.32%** | Significant drop on multi-table joins (3+ tables), nested subqueries, and set operations. |
| **Extra Hard** | 6 | 0 | **0.00%** | Complete failure on deeply nested subqueries, multi-hop joins, and compound set operations. |
| **Overall Total** | **1,034** | **708** | **68.47%** | Comprehensive cross-complexity benchmark reference. |

---

## 🔍 3. Failure Taxonomy Breakdown & Root Cause Analysis

All 326 failed queries were programmatically captured and categorized into the standard research taxonomy:

```
Total Failures: 326 / 1,034 (31.53%)
├── RESULT_MISMATCH      : 175 (53.68% of failures)
├── SYNTAX_ERROR         : 121 (37.12% of failures)
├── JOIN_ERROR           :  15 ( 4.60% of failures)
├── SCHEMA_LINKING_ERROR :  10 ( 3.07% of failures)
└── AGGREGATION_ERROR    :   5 ( 1.53% of failures)
```

### Taxonomy Category Analysis

#### 1. `SYNTAX_ERROR` (121 queries — 37.12% of failures)
* **Root Cause**: The LLM generated queries with dialect collisions (e.g. using T-SQL bracket escaping `[...]` or pagination clauses that failed in the SQLite execution environment), unquoted reserved keywords, or trailing syntax anomalies.
* **Research Implication for Task 3**: **This is the primary target of the Stage 3 Automated Query Refinement Loop.** In Stage 3, database compiler dry-run feedback (`EXPLAIN`) will detect these 121 syntax errors in $<2\text{ms}$ and provide targeted compiler diagnostics to heal them on Attempt 2.

#### 2. `RESULT_MISMATCH` (175 queries — 53.68% of failures)
* **Root Cause**: The generated SQL compiled and executed without errors, but the returned dataset did not match the gold SQL result set. Common causes included:
  - Inverted sort order (`ASC` vs `DESC`)
  - Missing distinct filters (`SELECT` vs `SELECT DISTINCT`)
  - Semantic boundary conditions (e.g. `> 1` vs `>= 1`)
* **Research Implication**: Highlights the boundary of syntactic self-correction versus semantic intent disambiguation.

#### 3. `SCHEMA_LINKING_ERROR` & `JOIN_ERROR` (25 queries — 7.67% of failures)
* **Root Cause**: In unpruned full-schema prompts, the model was exposed to distractor tables with similar column names, leading to referencing non-existent columns in the target table or picking the wrong foreign-key path.
* **Research Implication for Task 1**: **Validates Stage 2 Minimal-Context Schema Pruning.** Filtering out distractor tables prior to prompt generation will reduce column hallucinations and focus attention on valid foreign-key pathways.

---

## ⏱️ 4. Latency & Computational Timing Profile

```
============================================================
       TIMING BREAKDOWN SUMMARY (Full Spider Benchmark N=1034)
============================================================
 Total Pipeline Runtime: 2,520.52 seconds (~42.0 minutes)
------------------------------------------------------------
 * LLM API Inference          :  1,988.63s ( 78.9%) ====================
 * Inter-Query Rate Pacing    :    517.00s ( 20.5%) =====
 * Predicted Query Execution  :      7.68s (  0.3%) 
 * Gold Query Execution       :      5.00s (  0.2%) 
 * SQLite Connection Opening  :    391.8ms ( <0.1%) 
 * Schema DDL Extraction      :    244.3ms ( <0.1%) 
 * Result Set Comparison      :    141.5ms ( <0.1%) 
 * CRP Prompt Construction    :     16.9ms ( <0.1%) 
 * SQL Post-Processing        :     15.0ms ( <0.1%) 
============================================================
```

* **Observation**: Database operations, connection management, and local prompt construction take less than **1%** of total runtime. Remote API inference and network roundtrips account for **99.4%** of active processing time.
* **Key Finding**: Reducing input prompt token size via Stage 2 pruning will directly reduce API processing latency and overall system response time.

---

## 📌 5. Comparative Trajectory: Hypothesis for Stages 2 & 3

With the **Stage 1 Baseline firmly established at 68.47% ($N = 1,034$)**, the research roadmap defines the following empirical progression:

| Research Stage | Implemented Feature | Target Failure Mode Eliminated | Projected Execution Accuracy |
| :--- | :--- | :--- | :---: |
| **Stage 1 (Current)** | **Naive Baseline (Raw DDL)** | None (Control Reference) | **68.47%** |
| **Stage 2 (Task 1)** | **Minimal-Context Schema Pruning** | Distractor tables, Token bloat | **~71% – 74%** |
| **Stage 3 (Task 3)** | **Compiler Dry-Run Self-Correction** | 121 `SYNTAX_ERROR` failures | **~77% – 82%** |
| **Stage 4 (Task 4)** | **Entity Resolution & Relational Graph** | `JOIN_ERROR` & Complex queries | **~83% – 86%+** |

---

*Report exported and verified on branch `dilina-nl-to-sql-prototype-stage-1`.*
