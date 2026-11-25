#!/bin/sh
# Applies an additive, idempotent read-only DB-role migration to an existing database.
set -eu
if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/apply_readonly_migration.sh --apply" >&2
    echo "Ensure a verified database backup and review migration SQL first." >&2
    exit 2
fi
command -v docker >/dev/null || { echo "Docker Compose is required." >&2; exit 1; }
echo "Applying additive 002-readonly.sql to the configured Compose PostgreSQL service."
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/002-readonly.sql'
echo "Read-only database role migration applied. Verify role access with an authenticated API read."
