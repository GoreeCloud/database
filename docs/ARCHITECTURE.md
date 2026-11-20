# Architecture and trust boundaries

```text
Browser (loopback) -----> web/nginx:8080 ----- /api/ ----> FastAPI
                                                          |
                                                          | gc_api non-superuser
                                                          v
                                                     PostgreSQL 17
                                                          ^
                                                          | gc_rest -> gc_anon (read-only)
Local REST client ------> PostgREST:3000 -----------------/
Android (HTTPS only) --> externally authenticated TLS gateway --> /api/ (proposed, NOT deployed)
```

Current network is Docker Compose `internal:true`; only web and PostgREST bind `127.0.0.1`. Database data persists in named volume `pg_data`. `GC_ADMIN_TOKEN` gates the management API; database roles differ for API, REST and privileged bootstrap. REST anonymous role has only SELECT for the non-sensitive seeded catalog, never arbitrary user tables.

## API contract (preview)

- `GET /healthz` — process liveness, unauthenticated; not a full DB readiness guarantee.
- `GET /v1/tables` — list user tables in `app` schema.
- `GET /v1/tables/app/{table}/rows?limit=25&offset=0` — read first 1–100 rows, no caller SQL.
- `POST /v1/tables/app/{table}/rows` — insert flat JSON object using bound parameters; DB constraints enforce integrity.

`Authorization: Bearer <GC_ADMIN_TOKEN>` is mandatory for `/v1/*`. The `app` schema only is permitted. Errors intentionally omit database traces and credentials. HTTPS for mobile is a **deployment dependency**, not bundled by this stack.

## Roadmap

1. CI validation, secured branch workflow and real local container integration tests.
2. Per-user OIDC identity via GoreeCloud Identity (or a reviewed GoTrue integration), tenant-aware PostgreSQL RLS.
3. Object storage integration using SeaweedFS S3 with object ACLs, malware policy and private buckets.
4. Realtime via PostgreSQL logical decoding and a reviewed streaming service (no unrestricted replication slots).
5. Edge functions sandbox, migrations tooling, backups, tested restore, metrics and structured audit log.
6. Signed Android artifact, real device tests, accessible design review, production gateway hardening and remote access gates.

Deployment must not be presented as production-ready until these gates are fulfilled.
