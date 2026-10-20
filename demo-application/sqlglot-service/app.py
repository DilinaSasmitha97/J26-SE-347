# app.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from inspector import (
    parse_sql,
    SQLInspectorError
)

from extractor import (
    extract_sql_info
)
from rewriter import isolate_sql
from typing import Any


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="SQLGlot Inspection Service",
    description=(
        "Small SQL inspection service used by the "
        "Secure Multi-Tenant SQL Security Middleware."
    ),
    version="1.0.0"
)


# ---------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------

class SQLInspectRequest(BaseModel):
    """
    JSON body expected by POST /inspect
    """

    sql: str = Field(
        ...,
        min_length=1,
        description="Raw SQL query to inspect"
    )

    dialect: str = Field(
        default="mysql",
        description="SQL dialect used by SQLGlot"
    )


class TenantIsolationRequest(SQLInspectRequest):
    tenant_id: Any = None
    rules: list[dict[str, Any]] = Field(default_factory=list)
    repair: bool = True


@app.post("/tenant-isolation")
def tenant_isolation(request: TenantIsolationRequest):
    return {"success": True, "tenantRewrite": isolate_sql(
        request.sql, request.tenant_id, request.rules, request.dialect, request.repair
    )}


# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------

@app.get("/")
def root():
    """
    Simple service status endpoint.
    """

    return {
        "service": "sqlglot-service",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
def health():
    """
    Health endpoint for Node.js or deployment checks.
    """

    return {
        "status": "ok"
    }


# ---------------------------------------------------------
# SQL Inspection Endpoint
# ---------------------------------------------------------

@app.post("/inspect")
def inspect_sql(request: SQLInspectRequest):
    """
    Parse and inspect SQL.

    Flow:

        Raw SQL
            ↓
        inspector.py
            ↓
        SQLGlot AST
            ↓
        extractor.py
            ↓
        JSON-friendly analysis
    """

    try:

        # ---------------------------------------------
        # 1. Parse SQL using SQLGlot
        # ---------------------------------------------

        expression = parse_sql(
            request.sql,
            dialect=request.dialect
        )


        # ---------------------------------------------
        # 2. Extract useful SQL information
        # ---------------------------------------------

        analysis = extract_sql_info(
            expression
        )


        # ---------------------------------------------
        # 3. Return analysis
        # ---------------------------------------------

        return {
            "success": True,
            "analysis": analysis
        }


    except SQLInspectorError as error:

        # Invalid SQL / multiple statements / empty SQL
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SQL_INSPECTION_ERROR",
                "message": str(error)
            }
        )


    except Exception as error:

        # Unexpected internal error
        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": str(error)
            }
        )


# ---------------------------------------------------------
# Optional endpoint:
# Parse SQL and return only simple basic information.
# Useful for debugging.
# ---------------------------------------------------------

@app.post("/inspect/basic")
def inspect_sql_basic(request: SQLInspectRequest):
    """
    Return a smaller response useful while developing.
    """

    try:

        expression = parse_sql(
            request.sql,
            dialect=request.dialect
        )

        analysis = extract_sql_info(
            expression
        )

        return {
            "success": True,

            "statementType":
                analysis.get("statementType"),

            "normalizedSql":
                analysis.get("normalizedSql"),

            "tableCount":
                len(analysis.get("tables", [])),

            "columnCount":
                len(analysis.get("columns", [])),

            "filterCount":
                len(analysis.get("filters", [])),

            "joinCount":
                len(analysis.get("joins", []))
        }


    except SQLInspectorError as error:

        raise HTTPException(
            status_code=400,
            detail={
                "code": "SQL_INSPECTION_ERROR",
                "message": str(error)
            }
        )


    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail={
                "code": "INTERNAL_ERROR",
                "message": str(error)
            }
        )


# ---------------------------------------------------------
# Local development entry point
# ---------------------------------------------------------

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8001,
        reload=True
    )
