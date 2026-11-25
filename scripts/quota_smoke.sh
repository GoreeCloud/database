#!/bin/sh
# Tests the object-count quota inside a rolled-back transaction on a disposable CI database.
set -eu
if [ "${1:-}" != "--disposable" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/quota_smoke.sh --disposable" >&2
    echo "NEVER run against production or any important data volume." >&2
    exit 2
fi
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' <<'SQL'
BEGIN;
DO $$
DECLARE
  n integer;
  initial_count integer;
  rejected boolean := false;
  actual_constraint text;
BEGIN
  SELECT count(*) INTO initial_count FROM gc_storage.objects;
  IF initial_count > 5 THEN
    RAISE EXCEPTION 'Refusing quota smoke on a nonempty database';
  END IF;
  FOR n IN 1..(512 - initial_count) LOOP
    INSERT INTO gc_storage.objects (filename, media_type, size_bytes, sha256, contents)
    VALUES ('quota-' || n::text || '.txt', 'text/plain', 1, repeat('a', 64), decode('78', 'hex'));
  END LOOP;
  BEGIN
    INSERT INTO gc_storage.objects (filename, media_type, size_bytes, sha256, contents)
    VALUES ('quota-excess.txt', 'text/plain', 1, repeat('a', 64), decode('78', 'hex'));
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS actual_constraint = CONSTRAINT_NAME;
    IF actual_constraint <> 'gc_storage_total_quota' THEN
      RAISE;
    END IF;
    rejected := true;
  END;
  IF NOT rejected THEN
    RAISE EXCEPTION 'Quota trigger did not deny insertion above 512 objects';
  END IF;
END
$$;
ROLLBACK;
SQL
echo "Small-object count quota passed in a rolled-back disposable transaction."
