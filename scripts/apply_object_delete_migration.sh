#!/bin/sh
# Explicit storage privilege change, never operate on unknown volumes.
set -eu
if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/apply_object_delete_migration.sh --apply" >&2
    echo "Review 008-small-object-delete.sql and independently verify recovery first." >&2
    exit 2
fi
command -v docker >/dev/null || { echo "Docker Compose required." >&2; exit 1; }
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/008-small-object-delete.sql'
echo "Object delete privilege configured; inspect gc_api/grants on approved target."
