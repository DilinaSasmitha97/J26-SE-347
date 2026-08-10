# 📊 Research Report: Cross-Model Baseline Benchmark Comparison (N = 100)

**Date:** August 9, 2026  
**Author / Component Lead:** Sasmitha A W D (Member 1 - IT23143418)  
**Project:** Secure Multi-Tenant Natural Language Interface for Database Querying (J26-SE-347)  
**Evaluated Models:** Meta `Llama-3.3-70B-versatile` vs. Meta `Llama-3.1-8B-instant`  
**Dataset:** Spider Benchmark (`dev.json`, Sample Size: $N = 100$ queries across all difficulty tiers)  

---

## 📈 Cross-Model Comparative Baseline Table

| Evaluation Metric | Llama-3.3-70B-versatile (70B) | Llama-3.1-8B-instant (8B) | Comparative Analysis |
| :--- | :--- | :--- | :--- |
| **Execution Accuracy** | **77.00%** (77 / 100) | **68.00%** (68 / 100) | 🔴 **-9.00% Accuracy Penalty** for 8B model |
| **Schema Linking Errors** | **0** (0.0%) | **13** (13.0%) | 🔴 8B model frequently references non-existent columns |
| **Join Errors** | **0** (0.0%) | **4** (4.0%) | 🔴 8B model fails to construct multi-table JOINs |
| **Syntax Errors** | **3** (3.0%) | **3** (3.0%) | 🟡 Both models exhibit T-SQL dialect confusion (`OFFSET`) |
| **Result Mismatch Errors**| **20** (20.0%) | **12** (12.0%) | 🔵 70B attempts more complex SQL logic |
| **Avg Prompt Tokens** | **299.5 tokens** | **299.5 tokens** | 🟢 Identical input prompt size |
| **Avg Output Tokens** | **42.6 tokens** | **32.2 tokens** | 🔵 8B emits shorter SQL responses |
| **Total Evaluation Time** | **210.95 seconds** | **276.32 seconds** | 🟢 70B engine completed faster on Groq LPUs |

---

## 🔍 Key Research Discoveries for Literature

### 1. The Schema Linking Vulnerability in Smaller Models (8B vs. 70B)
* **Finding:** While **Llama-3.3-70B** achieved **0 Schema Linking Errors**, **Llama-3.1-8B** failed **13 times** due to `SCHEMA_LINKING_ERROR` (e.g., trying to execute `SELECT Model FROM car_names WHERE Weight < ...` when `Weight` is located in `cars_data`).
* **Paper Significance:** This empirically validates the necessity of **Task 1 (Minimal-Context Schema Injection)**. Smaller models (8B) suffer from high schema hallucinations when given un-pruned DDLs. Pruning the schema prior to generation will drastically reduce hallucinated column mappings in lightweight models.

### 2. Universal Dialect Confusion Across Model Scale
* **Finding:** Both 70B and 8B models generated identical T-SQL pagination syntax (`OFFSET 0 ROWS FETCH NEXT 1 ROW ONLY;`) when answering top-1 ranking queries, triggering SQLite `SYNTAX_ERROR` failures.
* **Paper Significance:** Model scale alone **does not fix dialect confusion**. This underscores the necessity of **Task 3 (Autonomous Refinement Loop)**, which forces execution-based self-correction regardless of model size.

---

## 📌 Paper Section Outline Contribution

This comparative experiment provides ready-to-publish data for:
> **Section 4.2: Model Parameter Scale Impact on Text-to-SQL Performance**  
> *"Evaluating Llama-3.3-70B against Llama-3.1-8B demonstrates a 9.0% execution accuracy degradation in 8B models, primarily driven by a 13% spike in Schema Linking Errors."*
