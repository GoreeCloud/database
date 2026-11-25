-- Permit only the private management role to delete a named small-object row.
-- Requires the API's independent strict confirmation and expected checksum.
\set ON_ERROR_STOP on
BEGIN;
REVOKE DELETE ON gc_storage.objects FROM PUBLIC, gc_reader, gc_rest, gc_anon;
GRANT DELETE ON gc_storage.objects TO gc_api;
COMMIT;
