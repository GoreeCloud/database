# GoreeCloud Database

**Status: early development preview. Not production ready.** A self-hosted, open-source PostgreSQL developer platform with a first-party management API, React web console and native Android client.

This is an independently developed GoreeCloud integration. It does **not** claim to be Supabase, reproduce all Supabase features or operate as a hosted service.

## Implemented in this repository

- PostgreSQL 17.12 persistent database, private container network and role-scoped bootstrap.
- PostgREST 16.6 read-only sample REST endpoint, proxied through the loopback-only web console.
- FastAPI management API with required bearer token, allowlisted `app` schema, table discovery, paginated row reads and parameterized inserts.
- React/TypeScript browser console using the verified GoreeCloud UI alpha semantic palette (no copied stable design claims).
- Kotlin/Jetpack Compose Android app for HTTPS management API table browsing, with in-memory credentials.
- Container configuration, secret generation, guarded custom-format PostgreSQL backup, network-isolated restore drill, tests, GitHub Actions, architecture and security guidance.

**Not implemented:** user signup/SSO/auth sessions, realtime subscriptions, object storage, edge functions, multi-tenant project orchestration, project provisioning, arbitrary SQL editor, migrations UI, certified full backup recovery/PITR, managed hosting, signed APK or production device validation. PostgreSQL roles, a shared bearer admin secret and local-only networking are *not* a multiuser identity service.

## Quick start (local development)

Requirements: Python 3.12+, Docker Engine with Compose plugin, container images available for your architecture. Prefer a verified suitable GoreeCloud Containers instance when available; Docker Compose is the documented alternative.

```sh
python3 scripts/init_env.py
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The console is at http://127.0.0.1:4173 (or `WEB_PORT`). Copy `GC_ADMIN_TOKEN` privately from your local `.env` and enter it in the console; it is held in memory, not localStorage. The read-only demonstration REST endpoint is `http://127.0.0.1:4173/rest/catalog` (only the seeded `app.catalog` table is granted anonymous SELECT). No PostgreSQL port is published.

The sample catalog table is created **only on first database volume initialization**. Changing `.env` after initialization does not rotate database role passwords. Use explicit SQL role rotation and update secrets together; never erase persistent volumes to solve a credentials problem.

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
- `scripts`: local secret setup, guarded logical backup, isolated recovery drill and tests. See [recovery runbook](docs/BACKUP_AND_RECOVERY.md).
- `docs`: architecture, threat model, roadmap, component licenses, recovery limitations.

## Security boundaries

The only published port is the web console on **127.0.0.1**, routing REST through `/rest/` and management through `/api/`. Management endpoints require a randomly generated bearer secret. This **preview must not be exposed directly to the public Internet**. Android requires HTTPS: terminate TLS with approved authentication and secure network routing before mobile connections. Do not put the management token in source, query strings or third-party services. Back up PostgreSQL volumes before important changes, rehearse restores in isolation and follow [SECURITY.md](SECURITY.md). Do not use with sensitive or irreplaceable data until authentication, monitoring, restore testing and operational hardening pass.

## Integrated platform systems

GoreeCloud UI: alpha semantic tokens taken from verified `GoreeCloud/gc-ui` (not declared stable). GoreeCloud Mesh: candidate API contract only, **not connected**. GoreeCloud Identity: admin bearer token placeholder pending real identity integration. GoreeShield: data minimization and local-only defaults; policy enforcement is partial. Wardveil: threat boundaries and CI checks; no integration or formal security certification.

## Open-source attribution

First-party code is under [Apache License 2.0](LICENSE). Upstream components are **not copied or relicensed**. Their runtime images and package dependencies retain their original license terms; see [third-party components](docs/THIRD_PARTY.md). When shipping binaries/images, verify the exact artifact version, license notices and SBOM before distribution.

Contributions and security issues: see [SECURITY.md](SECURITY.md). Development status is tracked in GitHub, not inferred from this README.
