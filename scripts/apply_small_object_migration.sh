#!/bin/sh
# Explicit additive migration for an existing database after verified backup.
set -eu
if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/apply_small_object_migration.sh --apply" >&2
    echo "Review migration 004 and verify an independently recoverable backup first." >&2
    exit 2
fi
command -v docker >/dev/null || { echo "Docker Compose required" >&2; exit 1; }
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/004-small-objects.sql'
echo "Small-object private schema migration applied. Verify API access boundaries."
