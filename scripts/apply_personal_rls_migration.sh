#!/bin/sh
# Explicit additive RLS preview migration. Does not modify existing app tables.
set -eu
if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/apply_personal_rls_migration.sh --apply" >&2
    echo "Review 007-personal-notes-rls.sql, verify backups and test roles first." >&2
    exit 2
fi
command -v docker >/dev/null || { echo "Docker Compose required." >&2; exit 1; }
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/007-personal-notes-rls.sql'
echo "Isolated owner-scoped RLS notes migration applied. Verify no cross-user access."
