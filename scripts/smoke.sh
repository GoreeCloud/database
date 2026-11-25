#!/bin/sh
# Disposable local Compose smoke test; never touches external production databases.
set -eu
: "${GC_ADMIN_TOKEN:?Set GC_ADMIN_TOKEN from locally generated .env}"
BASE="http://127.0.0.1:${WEB_PORT:-4173}"
REST="$BASE/rest"
ready=0
for attempt in $(seq 1 20); do
    if curl --fail --silent --output /dev/null "$BASE/api/healthz" &&
       curl --fail --silent --output /dev/null "$BASE/api/readyz" &&
       curl --fail --silent --output /dev/null "$REST/catalog"; then
        ready=1
        break
    fi
    sleep 3
done
if [ "$ready" -ne 1 ]; then
    echo "Stack did not become healthy in the smoke-test window" >&2
    for target in "$BASE/api/healthz" "$REST/catalog"; do
        result=$(curl --silent --max-time 3 --output /dev/null --write-out "%{http_code}" "$target" || true)
        echo "$target HTTP $result (000 = transport unavailable)" >&2
    done
    exit 1
fi
status=$(curl --silent --output /dev/null --write-out '%{http_code}' "$BASE/api/v1/tables")
if [ "$status" != "401" ]; then
    echo "Unauthenticated table listing returned HTTP $status (expected 401)" >&2
    exit 1
fi
curl --fail --silent --show-error "$BASE/api/v1/tables" -H "Authorization: Bearer $GC_ADMIN_TOKEN" |
    python3 -c 'import json,sys; obj=json.load(sys.stdin); assert any(t["schema"]=="app" and t["name"]=="catalog" for t in obj["tables"])'
curl --fail --silent --show-error "$BASE/api/v1/tables/app/catalog/rows" -H "Authorization: Bearer $GC_ADMIN_TOKEN" |
    python3 -c 'import json,sys; obj=json.load(sys.stdin); assert any(r["slug"]=="welcome" for r in obj["rows"])'
curl --fail --silent --show-error "$REST/catalog" |
    python3 -c 'import json,sys; data=json.load(sys.stdin); assert any(r["slug"]=="welcome" for r in data)'
status=$(curl --silent --output /dev/null --write-out '%{http_code}' "$BASE/api/v1/tables" -H "Authorization: Bearer $GC_READ_TOKEN")
if [ "$status" != "200" ]; then
    echo "Viewer token GET returned HTTP $status (expected 200)" >&2
    exit 1
fi
status=$(curl --silent --output /dev/null --write-out '%{http_code}' -X POST "$BASE/api/v1/tables/app/catalog/rows" -H "Authorization: Bearer $GC_READ_TOKEN" -H "Content-Type: application/json" --data '{"slug":"blocked"}')
if [ "$status" != "401" ]; then
    echo "Viewer token INSERT returned HTTP $status (expected 401)" >&2
    exit 1
fi
curl --fail --silent --show-error "$BASE/api/v1/tables/app/catalog/export.csv?limit=25" -H "Authorization: Bearer $GC_READ_TOKEN" |
    python3 -c 'import csv,sys; rows=list(csv.DictReader(sys.stdin)); assert any(row["slug"]=="welcome" for row in rows), "CSV export missing welcome row"'
status=$(curl --silent --output /dev/null --write-out '%{http_code}' "$BASE/api/v1/tables/app/catalog/export.csv")
if [ "$status" != "401" ]; then
    echo "Anonymous CSV export returned HTTP $status (expected 401)" >&2
    exit 1
fi
curl --fail --silent --show-error "$BASE/api/v1/tables/app/catalog/schema" -H "Authorization: Bearer $GC_READ_TOKEN" |
    python3 -c 'import json,sys; obj=json.load(sys.stdin); assert obj["schema"]=="app" and obj["table"]=="catalog"; assert any(c["name"]=="id" and c["primary_key"] for c in obj["columns"]); assert len(obj["indexes"])>=1'
status=$(curl --silent --output /dev/null --write-out '%{http_code}' "$BASE/api/v1/tables/pg_catalog/pg_class/schema" -H "Authorization: Bearer $GC_ADMIN_TOKEN")
if [ "$status" != "404" ]; then
    echo "Catalog schema access must be restricted (got HTTP $status)" >&2
    exit 1
fi
echo "GoreeCloud Database smoke: OK (scoped roles, schema inspection, bounded CSV export and catalog REST)."
