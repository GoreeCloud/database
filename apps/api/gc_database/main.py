"""Authenticated management API; not a general-purpose SQL execution endpoint."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from psycopg import Error as DatabaseError

from . import store
from .security import current_scope, require_admin, require_read, require_configuration, check_schema, check_identifier

log = logging.getLogger("goreecloud.database")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    require_configuration()
    yield


app = FastAPI(title="GoreeCloud Database", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update({
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "X-Frame-Options": "DENY",
    })
    return response


@app.exception_handler(DatabaseError)
def database_error(_request: Request, exception: DatabaseError):
    log.error("Database operation failed: %s", exception.sqlstate or "unknown SQLSTATE")
    return JSONResponse(status_code=503, content={"detail": "Database operation unavailable"})


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "online"}


@app.get("/v1/session")
def session(scope: str = Depends(current_scope)):
    return {"scope": scope, "permissions": ["read", "write"] if scope == "admin" else ["read"]}


@app.get("/v1/tables", dependencies=[Depends(require_read)])
def tables():
    return {"tables": store.list_tables()}


@app.get("/v1/tables/{schema}/{table}/rows", dependencies=[Depends(require_read)])
def rows(schema: str, table: str, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0, le=1000000)):
    check_schema(schema)
    check_identifier(table)
    return jsonable_encoder(store.fetch_rows(schema, table, limit, offset))


@app.post("/v1/tables/{schema}/{table}/rows", status_code=201, dependencies=[Depends(require_admin)])
def add_row(schema: str, table: str, payload: dict):
    check_schema(schema)
    check_identifier(table)
    return jsonable_encoder(store.insert_row(schema, table, payload))
