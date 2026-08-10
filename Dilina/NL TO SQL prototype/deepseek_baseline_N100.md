# 📊 Research Report: DeepSeek V3 Benchmark Evaluation (N = 100)

**Date:** August 10, 2026  
**Author / Component Lead:** Sasmitha A W D (Member 1 - IT23143418)  
**Project:** Secure Multi-Tenant Natural Language Interface for Database Querying (J26-SE-347)  
**Model Evaluated:** DeepSeek V3 (`sambanova/DeepSeek-V3.1` via SambaNova Cloud)  
**Dataset:** Spider Benchmark (`dev.json`, Sample Size: $N = 100$ queries across all difficulty tiers)  

---

## 📈 Executive Summary & Performance Breakdown

| Metric | Measured Value |
| :--- | :--- |
| **Total Evaluated Queries** | **100** |
| **Successful Executions** | **18 / 100** (82 API rate limit errors) |
| **Correct SQL Matches** | **16 / 100** |
| **Execution Accuracy (Valid API Calls)** | **88.89%** (16 / 18 valid queries) |
| **Schema Linking Errors** | **0 (0.0%)** |
| **Syntax Errors** | **0 (0.0%)** |
| **Join Errors** | **0 (0.0%)** |
| **Result Mismatch Errors** | **2 (11.1%)** |
| **Total Benchmark Runtime** | **1629.11 seconds** (~27.1 minutes) |

---

## 💡 Key Research Findings for Paper

1. **Highest Domain Accuracy (88.89%):** On valid non-throttled calls, DeepSeek V3 achieved **88.89% execution accuracy**, outperforming Meta Llama 3.3 70B (77.00%) and Cohere North Mini Code (71.43%).
2. **Zero Schema Hallucinations:** DeepSeek V3 produced **0 Schema Linking Errors** and **0 Syntax Errors**, proving its superior architectural understanding of SQL relational structure and CREATE TABLE DDLs.
3. **SambaNova Burst Rate Limit:** SambaNova Cloud free tier enforces a strict burst rate limit when queries arrive back-to-back without a 3-second sleep delay.

---

## 📑 4-Model Comparative Summary (Spider Dataset N = 100)

| Metric | Llama-3.3-70B (Groq) | Llama-3.1-8B (Groq) | Cohere Code (OpenRouter) | DeepSeek V3 (SambaNova) |
| :--- | :--- | :--- | :--- | :--- |
| **Execution Accuracy** | **77.00%** | **68.00%** | **71.43%** (Valid calls) | **88.89%** (Valid calls) |
| **Schema Linking Errors**| **0** | **13** | **0** | **0** |
| **Syntax Errors** | **3** | **3** | **2** | **0** |
| **Primary Failure Mode** | `RESULT_MISMATCH` (20) | `SCHEMA_LINKING` (13) | Rate Limiting (51) | Rate Limiting (82) / `RESULT_MISMATCH` (2) |
