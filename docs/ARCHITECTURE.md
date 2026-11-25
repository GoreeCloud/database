# Architecture and trust boundaries

```text
Browser (127.0.0.1) --> web/nginx:8080 -- /api/* -----> FastAPI:8000
                              |                           | gc_api
                              | /rest/*                    v
                              +-----------> PostgREST    PostgreSQL:5432
                                          gc_rest            ^
                                            |                 |
                                            +-----gc_anon-----+
Android (HTTPS) --> separately approved identity-aware TLS gateway --> web /api
```

The **only host-published port** is the web console, bound by default to `127.0.0.1:4173`. `/rest/catalog` is the explicitly public read-only demo endpoint via nginx; `/api/v1/*` requires the administration bearer token. There are two Docker networks: isolated `data` (`internal:true`) for Postgres, API, PostgREST and nginx, and host-facing `access` for nginx only. The databases/services have no directly host-published ports; nginx on `access` is not an internet-ready edge gateway. Any external access, particularly Android, requires a separately reviewed HTTPS and authenticated proxy.

Database data persists in named volume `pg_data`. The `GC_ADMIN_TOKEN` is the shared management secret, *not* a user identity system. Database roles differ for privileged first boot, `gc_api` for app-table writes, `gc_reader` with SELECT-only rights for authenticated viewer/admin reads, and `gc_rest` -> `gc_anon` for read-only sample-table access.

## API contract (preview)

- `GET /api/healthz` — process liveness only, unauthenticated; not a full DB readiness guarantee.
- `GET /api/readyz` — unauthenticated, minimal read-only `SELECT 1` connectivity probe through the `gc_reader` PostgreSQL role; 503 on database failure, no SQL or credential disclosure. Docker Compose monitors this probe for API container health.
- `GET /api/v1/session` — authenticate and return `admin` or `reader` capability information without disclosing credentials.
- `GET /api/v1/events/catalog` — bounded SSE notifications for catalog INSERT/UPDATE/DELETE metadata only; no replay or user authorization beyond shared preview tokens.
- `POST /api/v1/objects?filename=...` — administrator-only binary upload, 1 MiB maximum; PostgreSQL enforces a global 512-object/128 MiB capacity bound with safe 507 responses for quota exhaustion.
- `GET /api/v1/objects` — authenticated object metadata listing; `GET /api/v1/objects/{uuid}` returns checksum-verified attachment bytes under the shared viewer/admin token boundary. The objects table lives in separate private `gc_storage` schema, never the generic `app` or public PostgREST schemas.
- `GET /api/v1/tables` — list user tables in `app` schema.
- `GET /api/v1/tables/app/{table}/schema` — read-only `information_schema`/PostgreSQL catalog metadata: columns, types, nullability, defaults, primary keys and index definitions. No caller-authored SQL.
- `GET /api/v1/tables/app/{table}/rows?limit=25&offset=0` — read first 1–100 rows per page, no caller SQL.
- `GET /api/v1/tables/app/{table}/export.csv?limit=100&offset=0` — authenticated, SELECT-only spreadsheet-safe CSV page; max 500 rows/100 columns/2 MiB. No cross-user privacy boundary or full snapshot consistency.
- `POST /api/v1/tables/app/{table}/rows` — insert a flat JSON object using bound parameters; DB constraints enforce integrity.
- `GET /rest/catalog` — anonymous SELECT on the intentionally non-sensitive seeded `app.catalog` table only.

`Authorization: Bearer <GC_ADMIN_TOKEN>` is required for write actions. Authenticated read routes accept the independent `GC_READ_TOKEN` as well; neither token is a user identity or multi-tenant policy. The `app` schema only is permitted. Errors intentionally omit SQL traces and credentials. HTTPS for mobile remains a **deployment dependency**, not bundled by this stack.

## Roadmap

1. Real local Compose smoke, secured branch workflow and reproducible images.
2. Per-user OIDC identity via GoreeCloud Identity or a reviewed GoTrue integration; project-scoped authorization and PostgreSQL RLS.
3. Object storage integration with SeaweedFS S3, private bucket ACLs and malware/retention policy.
4. Realtime via PostgreSQL logical decoding with scoped subscriptions and controlled replication-slot lifetime.
5. Edge functions sandbox, migrations tooling, backups, tested restore, metrics and audit logs.
6. Signed Android artifact, real device tests, accessibility QA and production gateway hardening.

Deployment must not be presented as production-ready until these gates are fulfilled.
