-- Idempotent setup for the management API's strictly read-only PostgreSQL role.
-- Run on an existing volume only after an independently verified backup.
-- DATABASE ROLE PASSWORD IS NEVER HARDCODED.
\set ON_ERROR_STOP on
\getenv reader_password GC_READ_DB_PASSWORD
\getenv db_name POSTGRES_DB
SELECT format('CREATE ROLE gc_reader LOGIN PASSWORD %L', :'reader_password')
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gc_reader') \gexec
GRANT CONNECT ON DATABASE :"db_name" TO gc_reader;
GRANT USAGE ON SCHEMA app TO gc_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO gc_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT SELECT ON TABLES TO gc_reader;
