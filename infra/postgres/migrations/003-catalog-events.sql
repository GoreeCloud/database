-- Metadata-only change notifications. No row payload or personal content is sent.
-- For existing volumes, apply only after an independently verified backup.
\set ON_ERROR_STOP on
CREATE OR REPLACE FUNCTION app.gc_catalog_change_notice()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    changed_id bigint;
BEGIN
    IF TG_OP = 'DELETE' THEN
        changed_id := OLD.id;
    ELSE
        changed_id := NEW.id;
    END IF;
    PERFORM pg_catalog.pg_notify(
        'gc_catalog_changes',
        pg_catalog.json_build_object(
            'schema', 'app', 'table', 'catalog',
            'operation', TG_OP, 'id', changed_id
        )::text
    );
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION app.gc_catalog_change_notice() FROM PUBLIC;
DROP TRIGGER IF EXISTS gc_catalog_change_notice ON app.catalog;
CREATE TRIGGER gc_catalog_change_notice
AFTER INSERT OR UPDATE OR DELETE ON app.catalog
FOR EACH ROW EXECUTE FUNCTION app.gc_catalog_change_notice();
