#!/bin/sh
# Explicit production-safe gate: deploy only after independently verified backup.
set -eu
if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/apply_object_quota_migration.sh --apply" >&2
    echo "Review 005-object-quota.sql, check data footprint, and verify backup first." >&2
    exit 2
fi
command -v docker >/dev/null || { echo "Docker Compose required." >&2; exit 1; }
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/005-object-quota.sql'
echo "Quota trigger updated. Verify denied over-quota writes on disposable stack."
