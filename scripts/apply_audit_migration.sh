#!/bin/sh
# Explicit additive metadata-audit migration. Do not apply without verified backup.
set -eu
if [ "${1:-}" != "--apply" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/apply_audit_migration.sh --apply" >&2
    echo "Review 006-audit-metadata.sql and verify independent recovery first." >&2
    exit 2
fi
command -v docker >/dev/null || { echo "Docker Compose required." >&2; exit 1; }
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/006-audit-metadata.sql'
echo "Audit triggers applied to app.catalog and gc_storage.objects; verify least privilege."
