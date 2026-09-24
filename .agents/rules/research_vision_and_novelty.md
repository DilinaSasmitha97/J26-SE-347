# 🔬 Research Vision, Novelty Goal & Operational Directives
**Project:** Secure Multi-Tenant Natural Language Interface for Database Querying (J26-SE-347)  
**Lead Component:** Member 1 (Sasmitha A W D - IT23143418) — Schema-Aware NL-to-SQL Translation Engine  
**Research Entity:** Centre of Excellence in AI (CoEAI), SLIIT UNI  

---

## 🎯 1. The Core Vision: Uncompromising Pursuit of Novelty Accuracy
* **Never Settle for Incremental Targets:** We do not stop at standard baseline improvements or arbitrary predicted plateaus (e.g. 88%). The overriding goal is to push the component to **genuine scientific novelty and state-of-the-art empirical accuracy**.
* **Iterate Through Advanced Techniques & Paradigms:** We will systematically research, design, prototype, and benchmark diverse advanced techniques and relational representations (e.g. lexical + semantic graph closure, non-executing compiler feedback loops, in-memory schema caches, multi-hop relationship resolution, vector/fuzzy entity disambiguation, and dialect-specific AST alignment).
* **Pursue the Pareto-Optimal Accuracy-to-Token Frontier:** Novelty accuracy must not come from brute-force token bloat or prohibitive latency. Every technique must strictly optimize and defend:
  1. **High Execution Accuracy (EX)** on full cross-domain benchmarks ($N = 1,034$ Spider).
  2. **Minimal, Predictable Token Footprint** (preserving compact prompt and completion tokens).
  3. **Real-World Low Latency** (sub-millisecond local graph/cache lookups, $<2\text{s}$ remote LLM turnaround).

---

## 🚫 2. Absolute Behavioral Constraints
* **No Premature Demos or Presentation Distractions:** Do NOT suggest creating slides, UI mockups, or preparing demonstrations unless the user explicitly requests them. All cognitive and computational effort stays locked on algorithmic engineering, empirical benchmarking, and scientific discovery.
* **Continuous Academic & Thesis Documentation:** Document every experiment, benchmark, hypothesis, failure pattern, and performance curve for the direct purpose of the **undergraduate dissertation (thesis)** and **peer-reviewed research papers (IEEE / Springer / ACM conferences)**.
* **Living Empirical Master Records:** Always maintain and update the Master Research Comparison Document (`Master_Research_Comparison_Report.md` & `.docx`) with exact empirical numbers, failure taxonomies, and difficulty-tier breakdowns.
* **Single Standardized Model for Research Control:** Strictly benchmark all comparative stages against the standardized foundation model: **`Qwen/Qwen-2.5-Coder-32B-Instruct`** (via OpenRouter paid tier) to prevent model capability drift from confounding experimental validity.
* **Respect Component Boundaries (TAF Compliance):**
  - **Member 1 (Sasmitha - THIS COMPONENT):** Schema extraction, CRP prompt engineering, compiler dry-run validation (`EXPLAIN` / `SET NOEXEC ON`), schema caching, and entity/relationship resolution.
  - **Member 2:** AST safety middleware, dangerous command blocking (`DROP`/`ALTER`), PII masking, and Controlled Write Protocol.
  - **Member 3:** Multi-tenant row-level isolation AST rewriting and JWT claim enforcement.
  - **Member 4:** Vega-Lite chart visualization and predictive forecasting.
