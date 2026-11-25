#!/bin/sh
# PostgreSQL executes this exactly once for an empty data directory.
set -eu
: "${GC_API_DB_PASSWORD:?missing}"
: "${GC_REST_DB_PASSWORD:?missing}"
psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv api_password GC_API_DB_PASSWORD
\getenv rest_password GC_REST_DB_PASSWORD
\getenv db_name POSTGRES_DB
SELECT format('CREATE ROLE gc_api LOGIN PASSWORD %L', :'api_password')
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gc_api') \gexec
SELECT format('CREATE ROLE gc_rest LOGIN PASSWORD %L', :'rest_password')
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gc_rest') \gexec
SELECT 'CREATE ROLE gc_anon NOLOGIN'
  WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'gc_anon') \gexec
GRANT gc_anon TO gc_rest;
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.catalog (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  slug text NOT NULL UNIQUE CHECK (length(slug) BETWEEN 1 AND 120),
  description text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO app.catalog (slug, description)
VALUES ('welcome', 'Your GoreeCloud Database is ready for local development')
ON CONFLICT (slug) DO NOTHING;
GRANT CONNECT ON DATABASE :"db_name" TO gc_api, gc_rest;
GRANT USAGE ON SCHEMA app TO gc_api, gc_anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA app TO gc_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA app TO gc_api;
GRANT SELECT ON app.catalog TO gc_anon;
ALTER DEFAULT PRIVILEGES IN SCHEMA app
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gc_api;
ALTER DEFAULT PRIVILEGES IN SCHEMA app
  GRANT USAGE, SELECT ON SEQUENCES TO gc_api;
SQL
psql -X --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file=/migrations/002-readonly.sql
