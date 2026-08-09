# NL-to-SQL Engine — Member 1 (Month 1 Naive Baseline)

This repository contains the **Phase 1 Naive Text-to-SQL Baseline Engine** and automated evaluation harness for the NL-to-SQL research prototype.

## 📌 Month 1 Baseline Architecture

- **Strategy**: Code Representation Prompt (CRP) without pre-filtering or self-correction.
- **Supported Providers**: Google Gemini (`gemini-3.5-flash`) & Groq (`llama-3.3-70b-versatile`).
- **Contract Stub Signature**:
  ```python
  def translate(nl_query: str, schema_meta: str, injected_rules: str = None) -> tuple[str, dict]:
      """
      Translates natural language questions into SQL.
      injected_rules is an optional placeholder parameter reserved for Member 3 integration.
      Returns (sql_query, token_stats_dict).
      """
  ```

---

## 📊 Baseline Performance Reference Metrics

> **Control Baseline**: These metrics serve as the control reference against which all future context-filtering and self-correction improvements will be evaluated.

| Metric | Baseline Value |
| :--- | :--- |
| **LLM Provider** | Groq / Gemini (Configurable via `.env`) |
| **Execution Accuracy** | *Recorded via automated eval run* |
| **Average Tokens per Query** | *Logged per evaluation cycle* |
| **Evaluation Strategy** | Spider Execution Accuracy (Result set matching) |

### Failure Taxonomy Categories

1. `SCHEMA_LINKING_ERROR`: Referencing non-existent table or column names.
2. `JOIN_ERROR`: Incorrect or missing table join clauses.
3. `AGGREGATION_ERROR`: Mismatched `COUNT`, `SUM`, `AVG`, or `GROUP BY` logic.
4. `SYNTAX_ERROR`: Malformed SQL causing execution failure.
5. `RESULT_MISMATCH`: Syntactically valid SQL that produces incorrect row outputs.

---

## 🚀 Environment Setup & Running

### 1. Prerequisites & Virtual Environment

Activate the virtual environment:
```powershell
.\venv\Scripts\Activate.ps1
```
Or run commands directly using `.\venv\Scripts\python.exe`.

### 2. Environment Variables (`.env`)

Configure your API keys in `.env`:
```env
LLM_PROVIDER=groq  # or gemini
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
DB_SERVER=MSI\SQLEXPRESS
DB_NAME=NemsuERPNew
```

### 3. Running Single Query Engine

```powershell
.\venv\Scripts\python.exe main.py
```

### 4. Running Benchmark Evaluation Harness

Filter queries by **complexity** (`easy`, `medium`, `hard`, `extra`, or `all`) and set the **sample limit**:

```powershell
# Evaluate 10 'easy' queries
.\venv\Scripts\python.exe evaluate.py -n 10 -d easy

# Evaluate 5 'hard' queries
.\venv\Scripts\python.exe evaluate.py -n 5 -d hard

# Evaluate 10 'extra' queries (Notifies if fewer than 10 extra queries exist)
.\venv\Scripts\python.exe evaluate.py -n 10 -d extra

# Default: 10 queries across all complexities
.\venv\Scripts\python.exe evaluate.py
```

If the dataset has fewer questions than requested for a specific complexity, the harness evaluates all available matching questions and displays a notice:
`⚠️ Notice : Requested 10 questions for difficulty 'extra', but only 6 matching questions exist in the dataset. Evaluating all 6 available questions.`

