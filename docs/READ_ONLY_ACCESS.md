# Read-only access and upgrade contract

**Development preview only.** This adds a lower-privilege, shared read-only API token and a dedicated PostgreSQL role. It is **not** GoreeCloud Identity, OIDC, per-person accounts, tenant separation or complete RLS.

## Fresh installations

1. Run `python3 scripts/init_env.py` only when `.env` is absent. This creates `GC_ADMIN_TOKEN`, `GC_READ_TOKEN`, `GC_API_DB_PASSWORD`, `GC_REST_DB_PASSWORD`, `GC_READ_DB_PASSWORD` and the database superuser secret with restrictive file permissions.
2. Run `docker compose config --quiet`, then `docker compose up -d --build` on an authorized development host.
3. The first-boot bootstrap runs `infra/postgres/migrations/002-readonly.sql` after creating the schema. The role `gc_reader` gets CONNECT and schema USAGE and SELECT on `app` tables, **not INSERT/UPDATE/DELETE**. `gc_api` keeps its explicit write grants.
4. `GET /api/v1/tables` and `GET /api/v1/tables/app/{table}/rows` accept either admin or read-only bearer tokens. `POST .../rows` requires admin. Anonymous `/rest/catalog` remains a read-only demo.

Tokens are long-lived shared secrets for *local development only*. They must remain private, be served only over trusted TLS outside loopback and not be committed or logged.

## Existing volumes (additive upgrade)

**Do not delete or reinitialize volumes.** The role and grants will not be created by a first-install script once a PostgreSQL data volume exists.

1. Before changing service configuration, create and verify an independently restorable database backup. Stop here if no reliable recovery point exists.
2. Generate unique random values for the two **new** keys `GC_READ_TOKEN` and `GC_READ_DB_PASSWORD` (at least 32 characters each). Add them securely to the existing `.env`, without changing any old passwords.
3. Update/recreate the Compose **postgres** service so it receives `GC_READ_DB_PASSWORD` and mounts `infra/postgres/migrations` read-only. This must be planned carefully on any existing host.
4. Review `infra/postgres/migrations/002-readonly.sql` and run `sh scripts/apply_readonly_migration.sh --apply`. The script intentionally needs an explicit `--apply`; it runs SQL inside the private PostgreSQL container and never prints secrets.
5. Rebuild/recreate the API service after setting its read-token/read-role env vars; run authenticated viewer GET and denied POST checks. `sh scripts/smoke.sh` is for disposable local stacks.
6. Verify role grants before accepting data-sensitive workloads. Record migration time and recovery point outside public source.

This migration adds a role if missing and grants SELECT on the `app` schema. It does **not** rotate an existing `gc_reader` password; coordinate explicit `ALTER ROLE` with the secret owner for rotation. If migration fails, do not reset or delete persistent data; preserve logs (without credentials) and restore only through an authorized recovery plan.

## Deliberate limits and next gates

- Auth is shared token-based, not named-user identity. The read-only token can read **all allowed `app` tables**; do not place sensitive per-user tables in that schema without verified RLS and identity boundaries.
- There is no token expiry, revocation list, per-project claims or OIDC integration yet.
- Separate PostgreSQL roles reduce blast radius even if application route permissions regress, but they do not replace security testing.
- A full OIDC/JWKS adapter with identity-scoped permissions and RLS migrations must be reviewed and tested before any multiuser access.
