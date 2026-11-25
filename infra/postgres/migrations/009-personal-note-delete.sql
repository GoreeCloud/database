-- Owner-scoped private note deletion. No generic table/attachment permissions.
-- Repeatable additive migration; requires version 007 notes/RLS first.
\set ON_ERROR_STOP on
BEGIN;
REVOKE DELETE ON gc_personal.notes FROM PUBLIC, gc_reader, gc_rest, gc_anon;
GRANT DELETE ON gc_personal.notes TO gc_api;
ALTER TABLE gc_personal.notes ENABLE ROW LEVEL SECURITY;
ALTER TABLE gc_personal.notes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS gc_personal_notes_owner_delete ON gc_personal.notes;
CREATE POLICY gc_personal_notes_owner_delete ON gc_personal.notes
FOR DELETE TO gc_api
USING (owner_sub = current_setting('gc.request_subject', true));
COMMIT;
