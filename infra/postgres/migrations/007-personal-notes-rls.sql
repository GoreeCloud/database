-- Isolated demonstration of real per-subject PostgreSQL RLS.
-- The existing public app schema and shared-token APIs are NOT modified.
\set ON_ERROR_STOP on
BEGIN;
CREATE SCHEMA IF NOT EXISTS gc_personal;
REVOKE ALL ON SCHEMA gc_personal FROM PUBLIC;
CREATE TABLE IF NOT EXISTS gc_personal.notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_sub text NOT NULL CHECK (length(owner_sub) BETWEEN 1 AND 256),
    title text NOT NULL CHECK (length(title) BETWEEN 1 AND 120),
    content text NOT NULL CHECK (length(content) BETWEEN 1 AND 2048 AND octet_length(content) <= 8192),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS gc_personal_notes_owner_recent
ON gc_personal.notes (owner_sub, created_at DESC, id DESC);
REVOKE ALL ON SCHEMA gc_personal FROM PUBLIC;
REVOKE ALL ON TABLE gc_personal.notes FROM PUBLIC;
GRANT USAGE ON SCHEMA gc_personal TO gc_reader, gc_api;
GRANT SELECT ON gc_personal.notes TO gc_reader, gc_api;
GRANT INSERT ON gc_personal.notes TO gc_api;
ALTER TABLE gc_personal.notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE gc_personal.notes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gc_personal_notes_owner_select ON gc_personal.notes;
CREATE POLICY gc_personal_notes_owner_select ON gc_personal.notes
FOR SELECT TO gc_reader, gc_api
USING (owner_sub = current_setting('gc.request_subject', true));
DROP POLICY IF EXISTS gc_personal_notes_owner_insert ON gc_personal.notes;
CREATE POLICY gc_personal_notes_owner_insert ON gc_personal.notes
FOR INSERT TO gc_api
WITH CHECK (owner_sub = current_setting('gc.request_subject', true));

CREATE OR REPLACE FUNCTION gc_personal.enforce_note_quota()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    -- Prevent concurrent inserts for the same subject from bypassing the cap.
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(NEW.owner_sub, 73019));
    IF (SELECT count(*) FROM gc_personal.notes WHERE owner_sub = NEW.owner_sub) >= 100 THEN
        RAISE EXCEPTION USING
          ERRCODE = '23514',
          CONSTRAINT = 'gc_personal_notes_quota',
          MESSAGE = 'Private note capacity reached';
    END IF;
    RETURN NEW;
END
$$;
REVOKE ALL ON FUNCTION gc_personal.enforce_note_quota() FROM PUBLIC;
DROP TRIGGER IF EXISTS gc_personal_notes_quota ON gc_personal.notes;
CREATE TRIGGER gc_personal_notes_quota
BEFORE INSERT ON gc_personal.notes
FOR EACH ROW EXECUTE FUNCTION gc_personal.enforce_note_quota();
COMMIT;
