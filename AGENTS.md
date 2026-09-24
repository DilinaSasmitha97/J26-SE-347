# 🔬 Project Research Directives, Novelty Mandate & Enterprise Vision
**Project:** Secure Multi-Tenant Natural Language Interface for Database Querying (J26-SE-347)  
**Lead Component:** Member 1 (Sasmitha A W D - IT23143418) — Schema-Aware NL-to-SQL Translation Engine  
**Research Entity:** Centre of Excellence in AI (CoEAI), SLIIT UNI  

---

## 🎯 1. The Core Vision: Uncompromising Pursuit of Novelty Accuracy
* **Never Settle for Incremental Baselines:** We do not stop at standard baseline improvements or arbitrary predicted plateaus (e.g., 88%). The overriding goal is to push Member 1's engine to **genuine scientific novelty and state-of-the-art empirical accuracy**.
* **Systematic Empirical Exploration:** We will systematically hypothesize, architect, engineer, and benchmark diverse advanced techniques and relational representations (e.g., lexical + semantic graph closure, non-executing compiler feedback loops, in-memory schema caches, multi-hop relationship resolution, vector/fuzzy entity disambiguation, and dialect-specific AST alignment).
* **Progressive Benchmark Domination:**
  1. **Spider Benchmark:** Systematically climb and aim to **top the cross-domain Spider benchmark** ($N = 1,034$).
  2. **BIRD Benchmark:** Transition to the harder, real-world **BIRD benchmark** (BI, big data, complex schemas, cell values, and external knowledge).
  3. **Continuous Expansion:** Benchmark against any higher-standard modern text-to-SQL suites as research advances.

---

## 🏢 2. Enterprise Product Context & Economically Sound Scalability
* **Real-World Enterprise Destination:** This engine is not a toy benchmark parser; it is the translation core of our research group's enterprise product. It must reliably query real-world enterprise databases (e.g., ERP databases like `NemsuERPNew` with 100+ tables, hundreds of columns, composite keys, and complex foreign key graphs).
* **Contextually Sound Token & Performance Economics:** "Efficiency" does NOT mean imposing a rigid, artificial token limit (e.g., `<350` tokens) that chokes enterprise context. Instead, it means **economically sound, Pareto-optimal scaling tailored for production enterprise viability**:
  - Keep prompts minimal and laser-focused on the relevant relational subgraph, eliminating useless catalog bloat.
  - Scale prompt context dynamically and proportionately when complex multi-table enterprise queries require deeper schema context or entity grounding hints.
  - Preserve production turnaround times ($<2\text{s}$ remote LLM latency, sub-millisecond local graph/cache traversal) to make continuous multi-tenant querying cost-effective.

---

## 🚫 3. Absolute Behavioral Constraints
* **No Premature Demos or Presentation Distractions:** Do NOT suggest creating slides, UI mockups, or preparing demonstrations unless explicitly requested by the user. Keep focus locked on algorithmic engineering, empirical benchmarking, and scientific discovery.
* **Continuous Academic & Thesis Documentation:** Document every experiment, benchmark run, hypothesis, failure pattern, and performance curve for the direct purpose of the **undergraduate dissertation (thesis)** and **peer-reviewed research papers (IEEE / Springer / ACM conferences)**.
* **Living Empirical Master Records:** Always maintain and update the Master Research Comparison Document (`Master_Research_Comparison_Report.md` & `.docx`) with exact empirical numbers, failure taxonomies, and difficulty-tier breakdowns across all stages.
* **Standardized Foundation Model for Research Control:** Strictly benchmark all comparative stages against the standardized foundation model: **`Qwen/Qwen-2.5-Coder-32B-Instruct`** (via OpenRouter paid tier) to prevent model capability drift from confounding experimental validity.
* **Respect Component Boundaries (TAF Compliance):**
  - **Member 1 (Sasmitha - THIS COMPONENT):** Schema extraction, CRP prompt engineering, compiler dry-run validation (`EXPLAIN` / `SET NOEXEC ON`), schema caching, and entity/relationship resolution.
  - **Member 2:** AST safety middleware, dangerous command blocking (`DROP`/`ALTER`), PII masking, and Controlled Write Protocol.
  - **Member 3:** Multi-tenant row-level isolation AST rewriting and JWT claim enforcement.
  - **Member 4:** Vega-Lite chart visualization and predictive forecasting.
