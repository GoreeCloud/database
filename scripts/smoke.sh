#!/bin/sh
# Disposable local Compose smoke test; never touches external production databases.
set -eu
: "${GC_ADMIN_TOKEN:?Set GC_ADMIN_TOKEN from locally generated .env}"
BASE="http://127.0.0.1:${WEB_PORT:-4173}"
REST="http://127.0.0.1:${REST_PORT:-3000}"
ready=0
for attempt in $(seq 1 50); do
    if curl --fail --silent --output /dev/null "$BASE/api/healthz" &&
       curl --fail --silent --output /dev/null "$REST/catalog"; then
        ready=1
        break
    fi
    sleep 3
done
if [ "$ready" -ne 1 ]; then
    echo "Stack did not become healthy in the smoke-test window" >&2
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
echo "GoreeCloud Database smoke: OK (private web API + catalog REST)."
