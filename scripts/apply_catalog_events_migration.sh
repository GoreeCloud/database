#!/bin/sh
# Apply an additive metadata-only LISTEN/NOTIFY trigger to existing volumes.
set -eu
if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/apply_catalog_events_migration.sh --apply" >&2
    echo "Verify a recoverable PostgreSQL backup and review SQL first." >&2
    exit 2
fi
command -v docker >/dev/null || { echo "Docker Compose required" >&2; exit 1; }
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/003-catalog-events.sql'
echo "Metadata-only catalog trigger migration applied. Test events through authenticated TLS or loopback."
