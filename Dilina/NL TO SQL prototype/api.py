import os
import time
from typing import Optional, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import main
import llm
import schema_extractor
import database

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Multi-Tenant NL-to-SQL Engine Gateway",
    description="Member 1 NL-to-SQL Engine with schema pruning, prompt injection, and self-correction.",
    version="1.0.0"
)

# Enable CORS for cross-origin requests from frontends and teammate services
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Data Models -----------------

class TranslateRequest(BaseModel):
    user_query: str = Field(..., description="Natural language question from the user", example="What is the name and capacity of the stadium with the highest average attendance?")
    db_id: Optional[str] = Field("default", description="Database identifier / tenant context", example="concert_singer")
    schema_meta: str = Field(..., description="DDL or schema CREATE TABLE statements", example="CREATE TABLE stadium (stadium_id INT, name VARCHAR, capacity INT, average INT);")
    injected_rules: Optional[str] = Field(None, description="Security / RBAC grounding rules from Member 3", example="STRICT CONSTRAINT: Filter all results by tenant_id = 'tenant_a_123'.")
    use_pruning: Optional[bool] = Field(True, description="Whether to apply Task 1 schema pruning")

class TranslateResponse(BaseModel):
    status: str
    predicted_sql: str
    metadata: dict

class AskRequest(BaseModel):
    question: str = Field(..., description="Natural language question to query against the ERP database", example="Show top 10 employees by salary")
    injected_rules: Optional[str] = Field(None, description="Security / Tenant isolation rules from Member 3", example="Filter by tenant_id = 'tenant_123'")
    execute_query: Optional[bool] = Field(True, description="Whether to execute the SQL on your ERP and return live rows")
    max_rows: Optional[int] = Field(50, description="Maximum number of rows to return from the database")

class AskResponse(BaseModel):
    status: str
    question: str
    predicted_sql: str
    row_count: Optional[int] = 0
    columns: Optional[list[str]] = []
    rows: Optional[list[dict]] = []
    metadata: dict

class SchemaExtractRequest(BaseModel):
    user_query: str
    schema_meta: str

class SchemaExtractResponse(BaseModel):
    status: str
    pruned_schema: str
    stats: dict

class HealthResponse(BaseModel):
    status: str
    llm_provider: str
    active_model: str

# ----------------- Endpoints -----------------

@app.get("/", summary="Root Index")
def root():
    return {
        "message": "NL-to-SQL Engine Gateway is running.",
        "docs_url": "/docs",
        "health_check": "/api/v1/health",
        "ask_endpoint": "/api/v1/ask"
    }

@app.get("/api/v1/health", response_model=HealthResponse, summary="Engine Health Check")
def health():
    """
    Health check endpoint to verify engine uptime and active LLM configuration.
    """
    provider = os.getenv("LLM_PROVIDER", "cerebras").lower().strip()
    active_model = "unknown"
    if provider == "groq":
        active_model = getattr(llm, "GROQ_MODEL", "openai/gpt-oss-120b")
    elif provider == "cerebras":
        active_model = getattr(llm, "CEREBRAS_MODEL", "gemma-4-31b")
    elif provider == "openrouter":
        active_model = getattr(llm, "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
    elif provider == "gemini":
        active_model = getattr(llm, "GEMINI_MODEL", "gemini-2.5-flash")
    elif provider == "openai":
        active_model = getattr(llm, "OPENAI_MODEL", "gpt-4o-mini")

    return HealthResponse(
        status="UP",
        llm_provider=provider,
        active_model=active_model
    )

@app.post("/api/v1/translate", response_model=TranslateResponse, summary="Translate Natural Language to SQL")
def translate_query(req: TranslateRequest):
    """
    Core translation endpoint adhering to Team Interface Contract:
    Accepts natural language query, schema DDL, and injected security rules,
    and returns predicted SQL with token execution metadata.
    """
    start_time = time.time()
    try:
        sql, token_stats = main.translate(
            nl_query=req.user_query,
            schema_meta=req.schema_meta,
            injected_rules=req.injected_rules,
            use_pruning=req.use_pruning
        )
        
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        if isinstance(token_stats, dict):
            token_stats["execution_time_ms"] = execution_time_ms

        return TranslateResponse(
            status="SUCCESS",
            predicted_sql=sql,
            metadata=token_stats if isinstance(token_stats, dict) else {"execution_time_ms": execution_time_ms}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "ERROR",
                "error_code": "TRANSLATION_FAILED",
                "detail": str(e)
            }
        )

@app.post("/api/v1/ask", response_model=AskResponse, summary="Ask Question Directly Against Live ERP Database")
def ask_database(req: AskRequest):
    """
    End-to-end question answering:
    1. Loads live/cached ERP database schema
    2. Prunes schema using Task 1 schema extractor
    3. Translates Natural Language question into SQL
    4. Executes the SQL against your local database (if execute_query=True)
    5. Returns both the SQL query and the actual data rows!
    """
    start_time = time.time()
    try:
        # 1. Fetch schema from live database or cache
        schema_meta = database.get_cached_or_live_schema()

        # 2. Translate question to SQL
        sql, token_stats = main.translate(
            nl_query=req.question,
            schema_meta=schema_meta,
            injected_rules=req.injected_rules,
            use_pruning=True
        )

        columns = []
        rows = []
        if req.execute_query:
            try:
                columns, rows = database.execute_query(sql, max_rows=req.max_rows)
            except Exception as db_err:
                if isinstance(token_stats, dict):
                    token_stats["db_execution_error"] = str(db_err)

        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        if isinstance(token_stats, dict):
            token_stats["execution_time_ms"] = execution_time_ms

        return AskResponse(
            status="SUCCESS",
            question=req.question,
            predicted_sql=sql,
            row_count=len(rows),
            columns=columns,
            rows=rows,
            metadata=token_stats if isinstance(token_stats, dict) else {"execution_time_ms": execution_time_ms}
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "ERROR",
                "error_code": "QUERY_EXECUTION_FAILED",
                "detail": str(e)
            }
        )

@app.post("/api/v1/extract-schema", response_model=SchemaExtractResponse, summary="Minimal-Context Schema Extractor")
def extract_schema(req: SchemaExtractRequest):
    """
    Standalone endpoint to extract only relevant tables/columns for a natural language query.
    """
    try:
        pruned_schema, pruning_stats = schema_extractor.extract_minimal_schema(req.user_query, req.schema_meta)
        return SchemaExtractResponse(
            status="SUCCESS",
            pruned_schema=pruned_schema,
            stats=pruning_stats
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "ERROR",
                "error_code": "EXTRACTION_FAILED",
                "detail": str(e)
            }
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
