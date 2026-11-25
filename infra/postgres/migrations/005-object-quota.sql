-- Global development safety bound for the private PostgreSQL small-object store.
-- Does not remove existing data; apply to existing volumes only after verified backup.
\set ON_ERROR_STOP on
BEGIN;
CREATE OR REPLACE FUNCTION gc_storage.enforce_object_quota()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    current_count bigint;
    current_bytes bigint;
BEGIN
    -- Serialize competing INSERT transactions before reading aggregate usage.
    -- Lock key is dedicated to this small-object database feature.
    PERFORM pg_catalog.pg_advisory_xact_lock(77123, 45101);
    SELECT count(*), COALESCE(sum(size_bytes), 0)
      INTO current_count, current_bytes
      FROM gc_storage.objects;
    IF current_count >= 512 OR current_bytes + NEW.size_bytes > 134217728 THEN
        RAISE EXCEPTION USING
          ERRCODE = '23514',
          CONSTRAINT = 'gc_storage_total_quota',
          MESSAGE = 'Small-object quota exceeded';
    END IF;
    RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION gc_storage.enforce_object_quota() FROM PUBLIC;
DROP TRIGGER IF EXISTS gc_storage_object_quota ON gc_storage.objects;
CREATE TRIGGER gc_storage_object_quota
BEFORE INSERT ON gc_storage.objects
FOR EACH ROW EXECUTE FUNCTION gc_storage.enforce_object_quota();
COMMIT;
