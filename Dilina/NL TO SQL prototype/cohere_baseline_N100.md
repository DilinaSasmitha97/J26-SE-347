# 📊 Research Report: Cohere North Mini Code Benchmark Evaluation (N = 100)

**Date:** August 10, 2026  
**Author / Component Lead:** Sasmitha A W D (Member 1 - IT23143418)  
**Project:** Secure Multi-Tenant Natural Language Interface for Database Querying (J26-SE-347)  
**Model Evaluated:** Cohere (`cohere/north-mini-code:free` via OpenRouter)  
**Dataset:** Spider Benchmark (`dev.json`, Sample Size: $N = 100$ queries across all difficulty tiers)  

---

## 📈 Executive Summary & Performance Breakdown

| Metric | Measured Value |
| :--- | :--- |
| **Total Evaluated Queries** | **100** |
| **Successful Executions** | **49 / 100** (51 API rate limit errors) |
| **Correct SQL Matches** | **35 / 100** |
| **Execution Accuracy (Overall)** | **35.00%** |
| **Execution Accuracy (Valid API Calls)** | **71.43%** (35 / 49 valid queries) |
| **Average Total Tokens / Query** | **243.7 tokens** |
| **Average Prompt Tokens** | **121.2 tokens** |
| **Average Completion Tokens** | **122.6 tokens** |
| **Total Benchmark Runtime** | **1063.17 seconds** (~17.7 minutes) |

---

## 🔍 Failure Taxonomy Breakdown

```
Completed Non-Throttled Query Failures: 14 / 49
├── RESULT_MISMATCH      : 11 cases  (78.6%)
├── SYNTAX_ERROR         :  2 cases  (14.3%)
├── JOIN_ERROR           :  1 case   (7.1%)
└── SCHEMA_LINKING_ERROR :  0 cases  (0.0%)
```

---

## 💡 Key Research Findings for Paper

1. **High Code Efficiency on Valid Calls:** When un-throttled, Cohere North Mini Code achieved a **71.43% execution accuracy** on successful requests, demonstrating strong SQL domain-specific capabilities.
2. **Detailed Reasoning Output:** Cohere generated longer explanation strings alongside SQL (averaging 122.6 completion tokens per query), requiring strict regex post-processing.
3. **OpenRouter Shared Pool Throttling:** On OpenRouter's free tier, shared pool rate-limiting caused 51 HTTP 429 timeouts over a 17-minute evaluation window.

---

## 📑 Comparative Summary (Meta Llama 3.3 70B vs Meta Llama 3.1 8B vs Cohere Code)

| Metric | Llama-3.3-70B (Groq) | Llama-3.1-8B (Groq) | Cohere North Mini (OpenRouter) |
| :--- | :--- | :--- | :--- |
| **Execution Accuracy** | **77.00%** | **68.00%** | **71.43%** (Valid calls) / 35.0% total |
| **Schema Linking Errors**| **0** | **13** | **0** |
| **Primary Failure Mode** | `RESULT_MISMATCH` (20) | `SCHEMA_LINKING` (13) | Rate Limiting (51) / `RESULT_MISMATCH` (11) |
| **Evaluation Runtime** | **210.95s** | **276.32s** | **1063.17s** |
