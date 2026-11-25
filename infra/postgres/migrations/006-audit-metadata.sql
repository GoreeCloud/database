-- Minimal metadata-only audit of the two explicitly supported mutable tables.
-- No row contents, tokens, network addresses, account claims, or object IDs.
\set ON_ERROR_STOP on
BEGIN;
CREATE SCHEMA IF NOT EXISTS gc_audit;
REVOKE ALL ON SCHEMA gc_audit FROM PUBLIC;
CREATE TABLE IF NOT EXISTS gc_audit.events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_schema text NOT NULL CHECK (source_schema IN ('app', 'gc_storage')),
    source_table text NOT NULL CHECK (source_table IN ('catalog', 'objects')),
    operation text NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    occurred_at timestamptz NOT NULL DEFAULT now()
);
REVOKE ALL ON gc_audit.events FROM PUBLIC;
REVOKE ALL ON SEQUENCE gc_audit.events_id_seq FROM PUBLIC;
GRANT USAGE ON SCHEMA gc_audit TO gc_api;
GRANT SELECT ON gc_audit.events TO gc_api;
CREATE INDEX IF NOT EXISTS gc_audit_events_recent ON gc_audit.events (occurred_at DESC, id DESC);

CREATE OR REPLACE FUNCTION gc_audit.record_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    -- Only bounded, trusted server-selected metadata. No NEW or OLD data stored.
    INSERT INTO gc_audit.events (source_schema, source_table, operation)
    VALUES (TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP);
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION gc_audit.record_change() FROM PUBLIC;
DROP TRIGGER IF EXISTS gc_audit_catalog_change ON app.catalog;
CREATE TRIGGER gc_audit_catalog_change
AFTER INSERT OR UPDATE OR DELETE ON app.catalog
FOR EACH ROW EXECUTE FUNCTION gc_audit.record_change();
DROP TRIGGER IF EXISTS gc_audit_object_change ON gc_storage.objects;
CREATE TRIGGER gc_audit_object_change
AFTER INSERT OR UPDATE OR DELETE ON gc_storage.objects
FOR EACH ROW EXECUTE FUNCTION gc_audit.record_change();
COMMIT;
