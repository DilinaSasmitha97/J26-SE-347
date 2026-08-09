# 📊 Experiment Report: Phase 1 Naive Baseline Evaluation

**Date:** August 9, 2026  
**Target LLM Provider:** Groq (`llama-3.3-70b-versatile`)  
**Dataset:** Spider Benchmark (`dev.json`)  
**Sample Size:** 20 queries (Filtered: `all` difficulties)  

---

## 📈 Executive Summary & Baseline Metrics

| Metric | Measured Value |
| :--- | :--- |
| **Execution Accuracy** | **80.00%** (16 / 20 correct) |
| **Average Total Tokens / Query** | 350.4 tokens |
| **Average Prompt (Input) Tokens** | 325.9 tokens |
| **Average Completion (Output) Tokens** | 24.5 tokens |
| **Total Benchmark Runtime** | 15.57 seconds |
| **LLM Inference Time Ratio** | **94.6%** of total runtime (~736ms per query) |

---

## 🔍 Failure Taxonomy Breakdown

```
Total Failures: 4 / 20 (20.0%)
├── SYNTAX_ERROR         : 3 (75% of failures)
├── RESULT_MISMATCH      : 1 (25% of failures)
├── SCHEMA_LINKING_ERROR : 0
├── JOIN_ERROR           : 0
└── AGGREGATION_ERROR    : 0
```

---

## 💡 Key Research Insights & Paper Observations

### 1. Dialect Confusion (T-SQL vs. SQLite)
All 3 `SYNTAX_ERROR` failures were caused by the LLM outputting Microsoft SQL Server (T-SQL) pagination syntax:
```sql
-- Predicted (Failed in SQLite):
SELECT Name, Capacity FROM stadium ORDER BY Average DESC OFFSET 0 ROWS FETCH NEXT 1 ROW ONLY;

-- Gold Standard (Valid SQLite):
SELECT name, capacity FROM stadium ORDER BY average DESC LIMIT 1;
```
* **Paper Takeaway:** Standard CRP prompts without explicit SQL dialect constraints cause LLMs to default to T-SQL or ANSI standard syntax instead of target DB engine dialect (SQLite). Adding an explicit dialect rule in Phase 2 should instantly boost execution accuracy to **95.0%** (+15% gain).

### 2. Computational Bottleneck Analysis
* **Inference vs. Database Execution:** Over **94.6%** of end-to-end pipeline execution time is consumed by remote LLM API latency. Local schema extraction and SQLite execution combined account for less than **0.5ms** per query.
* **Paper Takeaway:** Optimization efforts should prioritize reducing prompt token count (via schema pruning) to minimize network latency and API costs, rather than query optimization.

---

## 🎯 Next Steps for Research Paper

1. **System Prompt Patch (Immediate):** Instruct the prompt generator to explicitly enforce `SQLite` syntax constraints (e.g. use `LIMIT` instead of `OFFSET/FETCH`).
2. **Phase 2 Schema Pruning Experiment:** Test schema filtering techniques on larger schemas to evaluate prompt token reduction vs. accuracy trade-offs.
3. **Expand Evaluation Sample:** Run evaluation on $N = 100+$ samples once dialect constraint is applied.
