"""SQL identifiers are quoted; request values always travel as bind parameters."""
from __future__ import annotations
import os
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from fastapi import HTTPException

from .security import check_identifier, check_schema


@contextmanager
def connection(read_only: bool = False):
    with psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_READ_USER"] if read_only else os.environ["DB_USER"],
        password=os.environ["DB_READ_PASSWORD"] if read_only else os.environ["DB_PASSWORD"],
        connect_timeout=5,
        row_factory=dict_row,
        options="-c statement_timeout=5000 -c default_transaction_read_only=on" if read_only else "-c statement_timeout=5000",
    ) as db:
        yield db


def list_tables() -> list[dict[str, Any]]:
    with connection(read_only=True) as db, db.cursor() as cur:
        cur.execute(
            "SELECT schemaname AS schema, tablename AS name "
            "FROM pg_catalog.pg_tables WHERE schemaname = %s ORDER BY tablename",
            ("app",),
        )
        return cur.fetchall()


def columns(db: psycopg.Connection, schema: str, table: str) -> list[str]:
    check_schema(schema)
    check_identifier(table)
    with db.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position",
            (schema, table),
        )
        result = [r["column_name"] for r in cur.fetchall()]
    if not result:
        raise HTTPException(status_code=404, detail="Table not found")
    return result


def fetch_rows(schema: str, table: str, limit: int, offset: int) -> dict[str, Any]:
    with connection(read_only=True) as db:
        allowed = columns(db, schema, table)
        with db.cursor() as cur:
            cur.execute(
                sql.SQL("SELECT * FROM {}.{} LIMIT %s OFFSET %s").format(
                    sql.Identifier(schema), sql.Identifier(table)
                ),
                (limit, offset),
            )
            data = cur.fetchall()
    return {"schema": schema, "table": table, "columns": allowed, "rows": data, "limit": limit, "offset": offset}


def insert_row(schema: str, table: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not payload or len(payload) > 50:
        raise HTTPException(status_code=422, detail="Supply 1–50 columns")
    with connection() as db:
        allowed = set(columns(db, schema, table))
        names = list(payload)
        if any(not isinstance(name, str) or not check_identifier(name) or name not in allowed for name in names):
            raise HTTPException(status_code=422, detail="Unknown field")
        if any(isinstance(payload[k], (dict, list)) for k in names):
            raise HTTPException(status_code=422, detail="Nested values require explicit JSON schema support")
        with db.cursor() as cur:
            cur.execute(
                sql.SQL("INSERT INTO {}.{} ({}) VALUES ({}) RETURNING *").format(
                    sql.Identifier(schema), sql.Identifier(table),
                    sql.SQL(", ").join(map(sql.Identifier, names)),
                    sql.SQL(", ").join(sql.Placeholder() for _ in names),
                ),
                [payload[k] for k in names],
            )
            row = cur.fetchone()
    return {"row": row}
