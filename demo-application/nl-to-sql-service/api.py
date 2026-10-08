import os
import json
import time
from typing import Optional, Any, Union
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import main
import llm
import schema_extractor
import database
from profiler import begin_trace, end_trace, trace

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
    user_query: str = Field(..., description="Natural language question from the user", example="List all active employees and their departments")
    db_id: Optional[str] = Field("default", description="Database identifier: default (multitenant_hr) or nemsuerp", example="default")
    schema_meta: Optional[str] = Field(None, description="Optional DDL schema. If omitted, default multi-tenant HR schema is loaded automatically.")
    injected_rules: Optional[Union[str, dict[str, Any]]] = Field(None, description="User-supplied NL-to-SQL rules as a JSON object or legacy plain text")
    use_pruning: Optional[bool] = Field(True, description="Whether to apply Task 1 schema pruning")
    enable_refinement: Optional[bool] = Field(True, description="Whether to apply Task 3 automated self-correction loop")
    max_refinement_attempts: Optional[int] = Field(2, description="Maximum self-correction refinement attempts")

class TranslateResponse(BaseModel):
    status: str
    predicted_sql: str
    metadata: dict

class AskRequest(BaseModel):
    question: str = Field(..., description="Natural language question to query against the database", example="Show top 5 employees by basic salary")
    db_id: Optional[str] = Field("default", description="Database identifier: default (multitenant_hr) or nemsuerp", example="default")
    injected_rules: Optional[str] = Field(None, description="Security / Tenant isolation rules from Member 3", example="STRICT CONSTRAINT: Filter by tenant_id = 101")
    execute_query: Optional[bool] = Field(True, description="Whether to execute the SQL on database and return live rows")
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

@app.get("/api/v1/schema", summary="Inspect Active Database Schema")
def get_database_schema(db_id: Optional[str] = "default"):
    """
    Returns the active database schema DDL statements.
    Default: Multi-Tenant HR & Payroll schema (14 tables).
    """
    try:
        schema = database.get_cached_or_live_schema(db_id=db_id)
        return {
            "status": "SUCCESS",
            "db_id": db_id,
            "schema_bytes": len(schema),
            "schema_meta": schema
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail={"status": "ERROR", "detail": str(e)})

@app.post("/api/v1/translate", response_model=TranslateResponse, summary="Translate Natural Language to SQL")
def translate_query(req: TranslateRequest):
    """
    Core translation endpoint adhering to Team Interface Contract:
    Accepts natural language query, optional schema DDL, and injected security rules,
    and returns predicted SQL with token execution metadata.
    If schema_meta is omitted, the default multi-tenant HR schema is loaded automatically.
    """
    start_time = time.time()
    conn = None
    trace_token = begin_trace("/api/v1/translate", req.model_dump(exclude_unset=True))
    try:
        rules_text = req.injected_rules if isinstance(req.injected_rules, str) else (
            json.dumps(req.injected_rules, indent=2, ensure_ascii=False) if req.injected_rules is not None else None
        )
        trace("RULES FOR ENGINE PROMPT", rules_text)
        # Load default multi-tenant HR schema if caller didn't supply custom DDL
        schema_meta = req.schema_meta
        if not schema_meta:
            schema_meta = database.get_cached_or_live_schema(db_id=req.db_id)
            # Connect so the refinement loop gets a real compiler dry-run (EXPLAIN,
            # nothing is executed). Without a connection it can only check that the
            # SQL starts with SELECT, so errors like "101AND" were returned as valid.
            # Skipped for caller-supplied DDL: that schema is not in this database.
            try:
                conn = database.get_db_connection(db_id=req.db_id)
            except Exception as connection_error:
                conn = None
                trace("COMPILER CONNECTION UNAVAILABLE", str(connection_error))
        trace("SCHEMA SOURCE", {"db_id": req.db_id, "caller_supplied_schema": bool(req.schema_meta), "compiler_connection": conn is not None})

        sql, token_stats = main.translate(
            nl_query=req.user_query,
            schema_meta=schema_meta,
            injected_rules=rules_text,
            use_pruning=req.use_pruning,
            enable_refinement=req.enable_refinement,
            max_refinement_attempts=req.max_refinement_attempts,
            db_conn=conn,
            full_schema_meta=schema_meta
        )
        
        execution_time_ms = round((time.time() - start_time) * 1000, 2)
        if isinstance(token_stats, dict):
            token_stats["execution_time_ms"] = execution_time_ms

        response = TranslateResponse(
            status="SUCCESS",
            predicted_sql=sql,
            metadata=token_stats if isinstance(token_stats, dict) else {"execution_time_ms": execution_time_ms}
        )
        trace("HTTP RESPONSE OUTPUT", response.model_dump())
        return response
    except Exception as e:
        trace("HTTP ERROR OUTPUT", {"status": "ERROR", "error_code": "TRANSLATION_FAILED", "detail": str(e)})
        raise HTTPException(
            status_code=500,
            detail={
                "status": "ERROR",
                "error_code": "TRANSLATION_FAILED",
                "detail": str(e)
            }
        )
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        end_trace(trace_token)

@app.post("/api/v1/ask", response_model=AskResponse, summary="Ask Question Directly Against Live Database")
def ask_database(req: AskRequest):
    """
    End-to-end question answering:
    1. Loads live/cached schema (defaults to multi-tenant HR & Payroll)
    2. Prunes schema using Task 1 schema extractor
    3. Translates Natural Language question into SQL conforming to Member 3 rules
    4. Validates & self-corrects using compiler dry-run (Task 3)
    5. Executes SQL against database (MySQL or portable SQLite)
    6. Returns both SQL query and actual data rows!
    """
    start_time = time.time()
    conn = None
    try:
        # 1. Fetch schema from cache or database
        schema_meta = database.get_cached_or_live_schema(db_id=req.db_id)

        # Connect to DB for live dry-run validation and row fetch
        if req.execute_query:
            try:
                conn = database.get_db_connection(db_id=req.db_id)
            except Exception as e:
                conn = None

        # 2. Translate question to SQL with self-correction
        sql, token_stats = main.translate(
            nl_query=req.question,
            schema_meta=schema_meta,
            injected_rules=req.injected_rules,
            use_pruning=True,
            enable_refinement=True,
            max_refinement_attempts=2,
            db_conn=conn,
            full_schema_meta=schema_meta
        )

        columns = []
        rows = []
        if req.execute_query and conn:
            try:
                cursor = conn.cursor()
                cursor.execute(sql)
                columns = [col[0] for col in cursor.description] if cursor.description else []
                if columns:
                    for row in cursor.fetchmany(req.max_rows):
                        row_dict = {}
                        for col_name, val in zip(columns, row):
                            if val is not None and not isinstance(val, (int, float, bool, str)):
                                row_dict[col_name] = str(val)
                            else:
                                row_dict[col_name] = val
                        rows.append(row_dict)
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
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

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
