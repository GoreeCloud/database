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


def describe_table(schema: str, table: str) -> dict[str, Any]:
    """Return schema metadata without executing caller-authored SQL.

    All catalog queries are bound and operate over the allowlisted app schema.
    A dedicated SELECT-only PostgreSQL connection serves the request.
    """
    check_schema(schema)
    check_identifier(table)
    with connection(read_only=True) as db, db.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type, udt_name, is_nullable, "
            "column_default, ordinal_position, character_maximum_length "
            "FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s "
            "ORDER BY ordinal_position",
            (schema, table),
        )
        raw_columns = cur.fetchall()
        if not raw_columns:
            raise HTTPException(status_code=404, detail="Table not found")
        cur.execute(
            "SELECT a.attname AS name "
            "FROM pg_catalog.pg_index i "
            "JOIN pg_catalog.pg_class c ON c.oid = i.indrelid "
            "JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
            "JOIN pg_catalog.pg_attribute a "
            "  ON a.attrelid = c.oid AND a.attnum = ANY(i.indkey) "
            "WHERE i.indisprimary = true AND n.nspname = %s AND c.relname = %s",
            (schema, table),
        )
        primary_names = {row["name"] for row in cur.fetchall()}
        cur.execute(
            "SELECT indexname AS name, indexdef AS definition "
            "FROM pg_catalog.pg_indexes "
            "WHERE schemaname = %s AND tablename = %s ORDER BY indexname",
            (schema, table),
        )
        indexes = cur.fetchall()

    columns = [
        {
            "name": item["column_name"],
            "type": item["data_type"],
            "database_type": item["udt_name"],
            "nullable": item["is_nullable"] == "YES",
            "default": item["column_default"],
            "ordinal": item["ordinal_position"],
            "max_length": item["character_maximum_length"],
            "primary_key": item["column_name"] in primary_names,
        }
        for item in raw_columns
    ]
    return {"schema": schema, "table": table, "columns": columns, "indexes": indexes}
