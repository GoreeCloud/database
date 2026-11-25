"""Owner-scoped RLS notes; never accept owner-subject from request payload."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from psycopg.errors import CheckViolation

from .store import connection


def delete_personal_note(subject: str, raw_id: str) -> None:
    """Delete one row owned by the verified OIDC subject, also enforced by RLS."""
    try:
        note_id = UUID(raw_id)
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=400, detail="Malformed private note ID") from None
    with connection() as db, db.cursor() as cur:
        cur.execute("SELECT set_config('gc.request_subject', %s, true)", (subject,))
        cur.execute(
            "DELETE FROM gc_personal.notes WHERE id = %s AND owner_sub = %s RETURNING id",
            (note_id, subject),
        )
        deleted = cur.fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Private note not found")


def list_personal_notes(subject: str, limit: int, offset: int) -> list[dict[str, Any]]:
    with connection(read_only=True) as db, db.cursor() as cur:
        # The signed OIDC subject is transaction local, and PostgreSQL RLS is
        # the authoritative isolation guard. No pooled session reuse.
        cur.execute("SELECT set_config('gc.request_subject', %s, true)", (subject,))
        cur.execute(
            "SELECT id::text AS id, title, content, created_at "
            "FROM gc_personal.notes ORDER BY created_at DESC, id DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
        return cur.fetchall()


def create_personal_note(subject: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"title", "content"}:
        raise HTTPException(status_code=422, detail="Supply title and content only")
    title, body = payload["title"], payload["content"]
    if (
        not isinstance(title, str) or not 1 <= len(title) <= 120
        or not isinstance(body, str) or not 1 <= len(body) <= 2048
        or len(body.encode("utf-8")) > 8192
    ):
        raise HTTPException(status_code=422, detail="Invalid private note size or value")
    try:
        with connection() as db, db.cursor() as cur:
            cur.execute("SELECT set_config('gc.request_subject', %s, true)", (subject,))
            cur.execute(
                "INSERT INTO gc_personal.notes (owner_sub, title, content) "
                "VALUES (%s, %s, %s) "
                "RETURNING id::text AS id, title, content, created_at",
                (subject, title, body),
            )
            return cur.fetchone()
    except CheckViolation as exc:
        if getattr(exc.diag, "constraint_name", None) == "gc_personal_notes_quota":
            raise HTTPException(status_code=507, detail="Personal note preview quota reached") from None
        raise
