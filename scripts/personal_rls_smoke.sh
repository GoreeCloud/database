#!/bin/sh
# Transaction-rolled-back RLS isolation test on a verified disposable CI volume.
set -eu
if [ "${1:-}" != "--disposable" ] || [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/personal_rls_smoke.sh --disposable" >&2
    echo "Only use with independently verified disposable data volumes." >&2
    exit 2
fi
docker compose exec -T postgres sh -c 'exec psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB"' <<'SQL'
BEGIN;
-- A superuser sets up disposable fixtures; these are rolled back below.
INSERT INTO gc_personal.notes (owner_sub, title, content)
VALUES ('ci-person-a', 'alice', 'a-test-private'), ('ci-person-b', 'bob', 'b-test-private');

SET LOCAL ROLE gc_reader;
DO $$
DECLARE found_rows integer;
BEGIN
  SELECT count(*) INTO found_rows FROM gc_personal.notes;
  IF found_rows <> 0 THEN
    RAISE EXCEPTION 'RLS failed closed without trusted subject';
  END IF;
END $$;
SELECT set_config('gc.request_subject', 'ci-person-a', true);
DO $$
DECLARE found_rows integer;
BEGIN
  SELECT count(*) INTO found_rows FROM gc_personal.notes;
  IF found_rows <> 1 THEN
    RAISE EXCEPTION 'Reader isolation failed: expected one note for person A';
  END IF;
  SELECT count(*) INTO found_rows FROM gc_personal.notes WHERE title='bob';
  IF found_rows <> 0 THEN
    RAISE EXCEPTION 'Reader leaked person B data to person A';
  END IF;
END $$;
SELECT set_config('gc.request_subject', 'ci-person-b', true);
DO $$
DECLARE found_rows integer;
BEGIN
  SELECT count(*) INTO found_rows FROM gc_personal.notes;
  IF found_rows <> 1 THEN
    RAISE EXCEPTION 'Reader isolation failed: expected one note for person B';
  END IF;
END $$;

RESET ROLE;
SET LOCAL ROLE gc_api;
SELECT set_config('gc.request_subject', 'ci-person-a', true);
DO $$
DECLARE denied boolean := false;
BEGIN
  BEGIN
    INSERT INTO gc_personal.notes (owner_sub, title, content)
    VALUES ('ci-person-b', 'attempted-forgery', 'must-never-write');
  EXCEPTION WHEN insufficient_privilege THEN
    denied := true;
  END;
  IF NOT denied THEN
    RAISE EXCEPTION 'RLS INSERT policy accepted a forged owner subject';
  END IF;
END $$;

RESET ROLE;
DO $$
DECLARE idx integer;
        denied boolean := false;
        got_constraint text;
BEGIN
  FOR idx IN 1..99 LOOP
    INSERT INTO gc_personal.notes (owner_sub, title, content)
    VALUES ('ci-person-a', 'quota-demo', 'disposable');
  END LOOP;
  BEGIN
    INSERT INTO gc_personal.notes (owner_sub, title, content)
    VALUES ('ci-person-a', 'over-limit', 'must be denied');
  EXCEPTION WHEN check_violation THEN
    GET STACKED DIAGNOSTICS got_constraint = CONSTRAINT_NAME;
    IF got_constraint <> 'gc_personal_notes_quota' THEN RAISE; END IF;
    denied := true;
  END;
  IF NOT denied THEN RAISE EXCEPTION 'Per-owner notes quota did not reject 101st note'; END IF;
END $$;
ROLLBACK;
SQL
echo "Per-subject PostgreSQL RLS and per-owner note quota verified (transaction rolled back)."
