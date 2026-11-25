"""Bounded, spreadsheet-safe CSV snapshots using the SELECT-only database role.

The endpoint returns only a requested page; it is not a consistent multi-page
snapshot, bulk export queue, or tenant-scoped data portability service.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from psycopg import sql

from .security import check_identifier, check_schema
from .store import columns, connection

MAX_ROWS = 500
MAX_CSV_BYTES = 2_097_152
MAX_CODEPOINTS = MAX_CSV_BYTES // 2


def safe_csv_cell(value: Any) -> str:
    """Prevent Excel/LibreOffice formula evaluation, even after leading spaces."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        result = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    elif isinstance(value, (bytes, bytearray, memoryview)):
        result = bytes(value).hex()
    elif isinstance(value, (datetime, date)):
        result = value.isoformat()
    elif isinstance(value, Decimal):
        result = str(value)
    else:
        result = str(value)
    # Leading whitespace does not make spreadsheet formula payloads safe.
    stripped = result.lstrip()
    if result[:1] in ("\t", "\r", "\n", "\x00") or stripped.startswith(("=", "+", "-", "@")):
        return "'" + result
    return result


def render_csv(headers: list[str], records: list[dict[str, Any]]) -> bytes:
    if not headers or len(headers) > 100 or len(records) > MAX_ROWS:
        raise HTTPException(status_code=413, detail="CSV export exceeds preview limits")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, dialect="excel", lineterminator="\r\n")
    writer.writerow([safe_csv_cell(column) for column in headers])
    for record in records:
        writer.writerow([safe_csv_cell(record.get(column)) for column in headers])
        if stream.tell() > MAX_CODEPOINTS:
            raise HTTPException(status_code=413, detail="CSV export exceeds 2 MiB")
    output = stream.getvalue().encode("utf-8")
    if len(output) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="CSV export exceeds 2 MiB")
    return output


def export_table_csv(schema: str, table: str, limit: int, offset: int) -> bytes:
    check_schema(schema)
    check_identifier(table)
    if not 1 <= limit <= MAX_ROWS or not 0 <= offset <= 1_000_000:
        raise HTTPException(status_code=422, detail="Invalid export page")
    with connection(read_only=True) as db:
        names = columns(db, schema, table)
        if len(names) > 100:
            raise HTTPException(status_code=413, detail="Too many columns for preview CSV export")
        with db.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT * FROM {}.{} LIMIT %s OFFSET %s").format(
                    sql.Identifier(schema), sql.Identifier(table)
                ),
                (limit, offset),
            )
            records = cur.fetchall()
    return render_csv(names, records)
