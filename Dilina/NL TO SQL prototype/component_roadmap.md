# 🎯 Research Component Roadmap: Member 1 (Sasmitha A W D)

**Project Title:** Secure Multi-Tenant Natural Language Interface for Database Querying  
**Project ID:** J26-SE-347  
**Research Group:** CoEAI - Centre of Excellence for AI (SLIIT UNI)  
**Sub-Objective:** Architect a context-optimized, schema-aware Natural Language-to-SQL translation engine capable of dynamically resolving semantic ambiguities and generating highly accurate relational queries.

---

## 📌 Deliverable Breakdown & Novelty

### Novelty Statement
The introduction of a **minimal-context schema injection and autonomous refinement pipeline** that maximizes LLM generation accuracy while strictly minimizing structural database exposure prior to middleware security validation.

---

## 🗺️ Implementation Tasks & Roadmap

| Task # | TAF Task Description | Target Module / Component | Status |
| :--- | :--- | :--- | :--- |
| **Task 1** | Dynamically map natural language intent to complex schemas using **minimal-context extraction** algorithms. | `schema_extractor.py` / Minimal-Context Extractor | 🟢 **Complete (Stage 2)** |
| **Task 2** | Engineer **context-aware prompt management pipeline** that optimizes LLM token limits while preserving schema integrity. | `prompts.py` / `llm.py` | 🟡 **Baseline Complete (CRP)** |
| **Task 3** | Develop an **automated query refinement loop** that utilizes schema-aware feedback to self-correct syntactically invalid or ambiguous SQL. | `refinement_loop.py` / Self-Correction Engine | 🟢 **Complete (Stage 3)** |
| **Task 4** | Resolve structural ambiguities in NL queries through advanced **contextual entity resolution and relationship mapping**. | `entity_resolver.py` / Relationship Mapper | ⏳ **Planned (Phase 4)** |

---

## 🔄 Integration Boundaries with Team Members

1. **Input from Member 3 (Jinajith):** Receives JWT claims & tenant authorization rules (`injected_rules` parameter in `translate()`).
2. **Output to Member 2 (Navodya):** Passes generated raw SQL query to the AST-driven security middleware for safety parsing, PII masking, and Controlled Write Protocol validation.
3. **Execution & Results to Member 4 (Wijethunge):** Delivers clean query execution results to the adaptive presentation and prediction layer for Vega-Lite visualization and temporal forecasting.
