# GoreeCloud Database

**Status: early development preview. Not production ready.** A self-hosted, open-source PostgreSQL developer platform with a first-party management API, React web console and native Android client.

This is an independently developed GoreeCloud integration. It does **not** claim to be Supabase, reproduce all Supabase features or operate as a hosted service.

## Implemented in this repository

- PostgreSQL 17.12 persistent database, private container network, role-scoped bootstrap and separate API liveness/readiness probes with Docker Compose health reporting.
- PostgREST 16.6 read-only sample REST endpoint, proxied through the loopback-only web console.
- Authenticated, bounded PostgreSQL LISTEN/NOTIFY SSE stream for metadata-only `app.catalog` changes; React refreshes the catalog view on events, Android supports manual refresh.
- Private, authenticated small-object API in a distinct PostgreSQL schema, with strict 1 MiB per-object and [512-object / 128 MiB total quotas](docs/OBJECT_QUOTA.md), safe download headers and SHA256 validation. This is **not S3-compatible storage**.
- FastAPI management API with distinct administrator and read-only bearer tokens, an **opt-in, cryptographically verified [OIDC read-only access-token adapter](docs/OIDC_READER.md)** (not multiuser RLS), a [30-per-minute single-process administrator write throttle](docs/WRITE_THROTTLE.md), separate PostgreSQL roles, allowlisted `app` schema, table discovery, read-only column/primary-key/index inspection, bounded spreadsheet-safe [CSV page export](docs/CSV_EXPORT.md), paginated row reads and parameterized inserts.
- React/TypeScript browser console using the verified GoreeCloud UI alpha semantic palette, including safe current-page CSV export, schema inspection and authenticated small-object browsing, bounded administrator upload and download.
- Kotlin/Jetpack Compose Android app for HTTPS management API table browsing, [read-only native schema inspection and bounded CSV saving](docs/ANDROID_SCHEMA.md), and private small-object listing/saving through Android's Storage Access Framework, with in-memory credentials.
- Container configuration, secret generation, guarded custom-format PostgreSQL backup, network-isolated restore drill, tests, GitHub Actions, architecture and security guidance.

**Not implemented:** user signup/SSO/auth sessions, general-purpose or durable realtime subscriptions, S3-compatible object storage, edge functions, multi-tenant project orchestration, project provisioning, arbitrary SQL editor, migrations UI, certified full backup recovery/PITR, managed hosting, signed APK or production device validation. PostgreSQL roles, shared development bearer tokens and local-only networking are *not* a multiuser identity service.

## Quick start (local development)

Requirements: Python 3.12+, Docker Engine with Compose plugin, container images available for your architecture. Prefer a verified suitable GoreeCloud Containers instance when available; Docker Compose is the documented alternative.

```sh
python3 scripts/init_env.py
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The console is at http://127.0.0.1:4173 (or `WEB_PORT`). Copy `GC_ADMIN_TOKEN` (read/write) or `GC_READ_TOKEN` (read-only) privately from your local `.env` and enter it in the console; tokens remain in memory, not localStorage. The console fetches `/api/v1/session` to disable mutation controls for viewers. The read-only demonstration REST endpoint is `http://127.0.0.1:4173/rest/catalog` (only the seeded `app.catalog` table is granted anonymous SELECT). No PostgreSQL port is published.

The sample catalog table is created **only on first database volume initialization**. Changing `.env` after initialization does not rotate database role passwords. Existing PostgreSQL volumes require the additive [read-only role migration](docs/READ_ONLY_ACCESS.md) after an independently verified backup; this migration does not rotate existing credentials. Never erase persistent volumes to solve a credentials problem.

```sh
docker compose logs --tail=60
curl -fsS http://127.0.0.1:4173/rest/catalog
# Never run docker compose down -v against data you want to preserve.
```

For web-only development: `cd apps/web && npm install && npm run dev`; Vite proxies `/api` to the locally running management API when enabled. For backend tests: `python3 -m pip install -e './apps/api[test]' && pytest apps/api/tests`. Android source is in `apps/android` and requires Android SDK, JDK 17+ and Gradle wrapper; production builds need signing and TLS.

## Repository map

- `infra/postgres/init`: first-install schema and least-privilege database roles.
- `apps/api`: authenticated control API.
- `apps/web`: browser management console.
- `apps/android`: Kotlin/Jetpack Compose Android management client.
- `scripts`: local secret setup, explicit read-role/catalog-event migrations, guarded logical backup and isolated restore drill. See [access upgrade](docs/READ_ONLY_ACCESS.md), [realtime preview](docs/REALTIME_PREVIEW.md), [small-object storage](docs/SMALL_OBJECTS.md), [web/Android object clients](docs/OBJECT_CLIENTS.md), and [recovery runbook](docs/BACKUP_AND_RECOVERY.md).
- `docs`: architecture, security, threat modeling, roadmap, dependency and licensing reviews, recovery limitations, plus the [source CLI command runbook](docs/CLI_COMMANDS.md). Canonical command references are governed in Google Drive `GoreeCloud/CLI Commands/`.

## Dependency update governance

The [dependency review runbook](docs/SUPPLY_CHAIN.md) describes weekly, PR-only version-update proposals for the Python API, React web app, Android Gradle, Docker and GitHub Actions. Changes still require protected CI and review; no source update auto-deploys or certifies production readiness.

## Security boundaries

The only published port is the web console on **127.0.0.1**, routing REST through `/rest/` and management through `/api/`. Management endpoints require a randomly generated bearer secret. This **preview must not be exposed directly to the public Internet**. Android requires HTTPS: terminate TLS with approved authentication and secure network routing before mobile connections. Do not put the management token in source, query strings or third-party services. Back up PostgreSQL volumes before important changes, rehearse restores in isolation and follow [SECURITY.md](SECURITY.md). Do not use with sensitive or irreplaceable data until authentication, monitoring, restore testing and operational hardening pass.

## Integrated platform systems

GoreeCloud UI: alpha semantic tokens taken from verified `GoreeCloud/gc-ui` (not declared stable). GoreeCloud Mesh: candidate API contract only, **not connected**. GoreeCloud Identity: distinct shared admin/viewer bearer tokens as a preview fallback, **not** an integrated user identity platform. GoreeShield: data minimization and local-only defaults; policy enforcement is partial. Wardveil: threat boundaries and CI checks; no integration or formal security certification.

## Open-source attribution

First-party code is under [Apache License 2.0](LICENSE). Upstream components are **not copied or relicensed**. Their runtime images and package dependencies retain their original license terms; see [third-party components](docs/THIRD_PARTY.md). When shipping binaries/images, verify the exact artifact version, license notices and SBOM before distribution.

Contributions and security issues: see [SECURITY.md](SECURITY.md). Development status is tracked in GitHub, not inferred from this README.
