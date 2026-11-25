#!/bin/sh
# Explicit RLS DELETE-policy migration for only gc_personal.notes.
set -eu
if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/apply_personal_note_delete_migration.sh --apply" >&2
    echo "Verify backups and owner-RLS policies before applying; never reset volumes." >&2
    exit 2
fi
command -v docker >/dev/null || { echo "Docker Compose required." >&2; exit 1; }
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/009-personal-note-delete.sql'
echo "Private note owner-scoped deletion policy updated; validate isolation before use."
