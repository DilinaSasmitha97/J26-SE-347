# 🤝 Multi-Tenant NLIDB Architecture: Team Interface Contract

**Project Title:** Secure Multi-Tenant Natural Language Interface for Database Querying  
**Project ID:** J26-SE-347  
**Research Group:** CoEAI - Centre of Excellence for AI (SLIIT UNI)  

This document defines the formal API contracts, data models, and integration boundaries between all 4 research components.

---

## 🏗️ System Data Flow Overview

```
User Query + JWT Token
        │
        ▼
[ Member 3: Access Control & Federated Auth ]
        │  ├── Validates JWT & extracts Tenant ID / Roles
        │  └── Generates First-Stage Prompt Rules (`injected_rules`)
        ▼
[ Member 1: Schema-Aware NL-to-SQL Engine ] (SASMITHA / THIS MODULE)
        │  ├── Minimal-Context Schema Extraction
        │  ├── REST API Gateway (`POST /api/v1/translate`)
        │  ├── Translates NL + Schema + Rules -> Raw SQL
        │  └── Runs Automated Self-Correction Loop
        ▼
[ Member 2: AST Security & Validation Layer ]
        │  ├── AST Safety Parsing & Danger Function Blocking
        │  ├── Second-Stage Row-Level Access Control AST Rewriting
        │  ├── Controlled Write Protocol (Transaction Preview/Rollback)
        │  └── Real-time PII Masking Pipeline
        ▼
[ Member 4: Presentation & Prediction Layer ]
        └── Vega-Lite Visualization + SARIMA Forecasting + Grounded Summaries
```

---

## 📑 Component Interface Specifications

### 1. Member 1 (Sasmitha) — NL-to-SQL Engine & REST API Interface
* **Module Location:** `Dilina/NL TO SQL prototype/`
* **Python Engine Signature:**
  ```python
  def translate(
      nl_query: str, 
      schema_meta: str, 
      injected_rules: str = None
  ) -> tuple[str, dict]:
      """
      Translates Natural Language queries into target SQL.
      
      Parameters:
        - nl_query (str): User's natural language question.
        - schema_meta (str): DDL or minimal schema metadata.
        - injected_rules (str, optional): First-stage RBAC/ABAC prompt rules from Member 3.
        
      Returns:
        - tuple[str, dict]: (Generated SQL string, Token/Execution Metadata Dict)
      """
  ```

* **FastAPI REST Endpoints (Middleware Gateway Specification):**

  #### Endpoint 1: `POST /api/v1/translate`
  * **Summary:** Accepts natural language query, database schema, and security rules, returning translated SQL & metadata.
  * **Request Headers:** `Content-Type: application/json`
  * **Request Payload (JSON):**
    ```json
    {
      "user_query": "What is the name and capacity of the stadium with the highest average attendance?",
      "db_id": "concert_singer",
      "schema_meta": "CREATE TABLE stadium (stadium_id INT, name VARCHAR, capacity INT, average INT);",
      "injected_rules": "STRICT CONSTRAINT: Filter all results by tenant_id = 'tenant_a_123'."
    }
    ```
  * **Response Payload — 200 OK (JSON):**
    ```json
    {
      "status": "SUCCESS",
      "predicted_sql": "SELECT name, capacity FROM stadium ORDER BY average DESC LIMIT 1;",
      "metadata": {
        "prompt_tokens": 326,
        "completion_tokens": 31,
        "total_tokens": 357,
        "model": "llama-3.3-70b-versatile",
        "refinement_attempts": 1,
        "execution_time_ms": 488.3
      }
    }
    ```
  * **Response Payload — Error Response (JSON):**
    ```json
    {
      "status": "ERROR",
      "error_code": "SYNTAX_REFINEMENT_FAILED",
      "detail": "Failed to generate syntactically valid SQL after max refinement attempts."
    }
    ```

  #### Endpoint 2: `GET /api/v1/health`
  * **Summary:** Health check for engine and LLM provider connectivity.
  * **Response Payload (JSON):**
    ```json
    {
      "status": "UP",
      "llm_provider": "groq",
      "active_model": "llama-3.3-70b-versatile"
    }
    ```

---

### 2. Member 3 (Jinajith) — Access Control & Auth Interface
* **Responsibility:** Pre-generation grounding & JWT validation.
* **Contract Output to Member 1:** `injected_rules` string injected into prompt context.
* **Contract Specification:**
  ```json
  {
    "tenant_id": "tenant_a_123",
    "user_role": "FINANCE_VIEWER",
    "prompt_grounding_rules": "STRICT CONSTRAINT: Only generate queries referencing tables permitted for tenant_a_123. Filter all financial records by tenant_id = 'tenant_a_123'."
  }
  ```

---

### 3. Member 2 (Navodya) — AST Security & Validation Middleware
* **Responsibility:** Post-generation safety validation & PII masking.
* **Contract Input from Member 1:** Accepts `predicted_sql`.
* **Contract Specification:**
  ```python
  def validate_and_mask_query(
      generated_sql: str, 
      tenant_id: str, 
      user_role: str
  ) -> dict:
      """
      Validates SQL AST for dangerous commands, rewrites queries for row-level isolation,
      and applies PII masking on return.
      """
  ```

---

### 4. Member 4 (Wijethunge) — Presentation & Prediction Layer
* **Responsibility:** Receives masked result sets and SQL query intent to render Vega-Lite charts, SARIMA forecasts, and grounded summaries.
* **Contract Input:**
  ```json
  {
    "query_intent": "AGGREGATE_TIMESERIES",
    "raw_results": [{"quarter": "Q1", "expenses": 12000}, {"quarter": "Q2", "expenses": 15000}],
    "schema_types": {"quarter": "DATE", "expenses": "NUMERIC"}
  }
  ```
