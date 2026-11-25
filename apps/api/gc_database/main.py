"""Authenticated management API; not a general-purpose SQL execution endpoint."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Header
from fastapi.responses import Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from psycopg import Error as DatabaseError

from . import store, storage, audit
from .exports import export_table_csv
from .realtime import open_catalog_event_stream
from .security import current_scope, require_admin, require_admin_view, require_read, require_configuration, check_schema, check_identifier

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
    """Process liveness only: does not imply database connectivity."""
    return {"status": "online"}


@app.get("/readyz")
def readiness() -> dict[str, str]:
    """Read-only database readiness; never returns connection or identity details."""
    store.check_database_readiness()
    return {"status": "ready"}


@app.get("/v1/session")
def session(scope: str = Depends(current_scope)):
    return {"scope": scope, "permissions": ["read", "write"] if scope == "admin" else ["read"]}


@app.get("/v1/events/catalog", dependencies=[Depends(require_read)])
async def stream_catalog_changes():
    return await open_catalog_event_stream()


@app.get("/v1/audit/events", dependencies=[Depends(require_admin_view)])
def audit_events(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
):
    return jsonable_encoder({
        "events": audit.list_audit_events(limit, offset),
        "limit": limit,
        "offset": offset,
    })


@app.get("/v1/tables", dependencies=[Depends(require_read)])
def tables():
    return {"tables": store.list_tables()}


@app.get("/v1/tables/{schema}/{table}/export.csv", dependencies=[Depends(require_read)])
def download_table_csv(
    schema: str, table: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0, le=1000000),
):
    check_schema(schema)
    check_identifier(table)
    contents = export_table_csv(schema, table, limit, offset)
    return Response(
        content=contents,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{schema}-{table}-page.csv"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
            "Cache-Control": "no-store",
        },
    )


@app.get("/v1/tables/{schema}/{table}/schema", dependencies=[Depends(require_read)])
def describe_schema(schema: str, table: str):
    check_schema(schema)
    check_identifier(table)
    return jsonable_encoder(store.describe_table(schema, table))


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


@app.get("/v1/objects", dependencies=[Depends(require_read)])
def list_private_objects(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1000000),
):
    return jsonable_encoder({"objects": storage.list_objects(limit, offset), "limit": limit, "offset": offset})


@app.post("/v1/objects", status_code=201, dependencies=[Depends(require_admin)])
async def upload_private_object(request: Request, filename: str = Query(...)):
    storage.check_filename(filename)
    media_type = storage.check_media_type(
        request.headers.get("content-type", "application/octet-stream").split(";")[0].strip().lower()
    )
    declared_size = request.headers.get("content-length")
    if declared_size:
        try:
            expected = int(declared_size)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from None
        if expected > storage.MAX_OBJECT_BYTES:
            raise HTTPException(status_code=413, detail="Object exceeds 1 MiB limit")
    content = bytearray()
    async for part in request.stream():
        if len(content) + len(part) > storage.MAX_OBJECT_BYTES:
            raise HTTPException(status_code=413, detail="Object exceeds 1 MiB limit")
        content.extend(part)
    if not content:
        raise HTTPException(status_code=422, detail="Empty objects are not supported")
    return jsonable_encoder({"object": storage.save_object(filename, media_type, bytes(content))})


@app.delete("/v1/objects/{object_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_private_object(
    object_id: str,
    x_confirm: str | None = Header(default=None, alias="X-GC-Confirm-Delete"),
    x_expected_sha256: str | None = Header(default=None, alias="X-GC-Expected-SHA256"),
):
    if x_confirm != "permanently-delete" or x_expected_sha256 is None:
        raise HTTPException(status_code=428, detail="Explicit confirmation and expected checksum required")
    storage.delete_object(object_id, x_expected_sha256)
    return Response(status_code=204)


@app.get("/v1/objects/{object_id}", dependencies=[Depends(require_read)])
def download_private_object(object_id: str):
    result = storage.read_object(object_id)
    return Response(
        content=result["contents"],
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{result["filename"]}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Security-Policy": "sandbox",
        },
    )
