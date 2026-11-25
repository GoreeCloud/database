-- Separate, nonpublic small-object schema; explicitly limits each value to 1 MiB.
-- This is not an S3-compatible store or complete tenant-aware object storage.
\set ON_ERROR_STOP on
CREATE SCHEMA IF NOT EXISTS gc_storage;
REVOKE ALL ON SCHEMA gc_storage FROM PUBLIC;
CREATE TABLE IF NOT EXISTS gc_storage.objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    filename text NOT NULL CHECK (filename ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,119}$'),
    media_type text NOT NULL CHECK (media_type IN (
        'application/octet-stream', 'text/plain',
        'image/png', 'image/jpeg', 'application/pdf'
    )),
    size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 1048576),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    contents bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT object_exact_size CHECK (octet_length(contents) = size_bytes)
);
REVOKE ALL ON TABLE gc_storage.objects FROM PUBLIC;
GRANT USAGE ON SCHEMA gc_storage TO gc_api, gc_reader;
GRANT SELECT, INSERT ON gc_storage.objects TO gc_api;
GRANT SELECT ON gc_storage.objects TO gc_reader;
