"""Bounded, authenticated metadata-only PostgreSQL LISTEN/NOTIFY SSE preview."""
from __future__ import annotations

import asyncio
import json
import os

import psycopg
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

# Bound database listener connections per API worker, not system-wide.
_SLOTS = asyncio.BoundedSemaphore(8)
_CHANNEL = "gc_catalog_changes"


def format_catalog_notice(raw: str) -> str | None:
    """Reject arbitrary NOTIFY payloads and escape all SSE framing characters."""
    if len(raw) > 1024:
        return None
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema") != "app" or payload.get("table") != "catalog":
        return None
    if payload.get("operation") not in {"INSERT", "UPDATE", "DELETE"}:
        return None
    item_id = payload.get("id")
    if type(item_id) is not int or item_id < 1:
        return None
    data = {"schema": "app", "table": "catalog", "operation": payload["operation"], "id": item_id}
    return "event: catalog\ndata: " + json.dumps(data, separators=(",", ":")) + "\n\n"


async def catalog_event_stream():
    try:
        async with await psycopg.AsyncConnection.connect(
            host=os.environ["DB_HOST"],
            port=int(os.environ.get("DB_PORT", "5432")),
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_READ_USER"],
            password=os.environ["DB_READ_PASSWORD"],
            connect_timeout=5,
            autocommit=True,
        ) as connection:
            await connection.execute("LISTEN gc_catalog_changes")
            yield "retry: 3000\nevent: ready\ndata: {}\n\n"
            while True:
                async for notice in connection.notifies(timeout=12.0, stop_after=20):
                    rendered = format_catalog_notice(notice.payload)
                    if rendered:
                        yield rendered
                yield ": heartbeat\n\n"
    finally:
        _SLOTS.release()


async def open_catalog_event_stream() -> StreamingResponse:
    try:
        await asyncio.wait_for(_SLOTS.acquire(), timeout=0.1)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=503, detail="Too many active listeners")
    return StreamingResponse(
        catalog_event_stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
    )
