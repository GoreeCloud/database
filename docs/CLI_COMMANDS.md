# GoreeCloud Database — Source CLI runbook

**Status:** Source-side command contracts (not the canonical Google Drive registry).  
**Canonical command registry destination:** `GoreeCloud/CLI Commands/GoreeCloud/Database.md` under the authorized `goreecloud@gmail.com` Google Drive. Source and scripts are maintained here; canonical Drive synchronization requires an authenticated, raw Markdown-capable writer and must be verified separately.

## Context, provenance and scope

- **Product:** original GoreeCloud Database, source: https://github.com/GoreeCloud/database
- **Supported preliminary context:** development/CI Linux shell, Python 3.12+, Node 24+, JDK 17+, Gradle 8.14.3 wrapper, Docker Engine with Compose plugin, PostgreSQL 17.12 / PostgREST 16.6 Compose images. Version support is based on source and tests, not deployment qualification.
- **Observed evidence:** isolated GitHub Actions jobs `api`, `web`, `android`, `config`, `integration` passed at the protected baseline. Exact test outcomes belong to GitHub, not this document.
- **Host:** any separately authorized, reviewed local development or CI Docker host; this runbook is **not** authorization to deploy on the production VPS.
- **Secrets:** use only the local untracked `.env` created by the setup helper. Never place secret values in Git, Drive, terminal history, screenshots, or publicly accessible logs. All examples below use placeholders.

## Opt-in trusted OIDC verifier configuration

The protected management API supports operator-controlled, read-only OIDC access-token verification as described in [OIDC reader runbook](OIDC_READER.md). The variables `GC_OIDC_ISSUER`, `GC_OIDC_AUDIENCE`, and **exactly one** of `GC_OIDC_JWKS_JSON` (trusted public key set, works without egress) or `GC_OIDC_JWKS_URL` (trusted same-origin HTTPS key endpoint, requires an approved egress path) are optional. A partial or invalid set causes startup failure. No access token or private signing key belongs in this document, CLI history, GitHub, or public logs.

- **Safety:** configuration mutation requiring approval, trust assessment, backup and restart; static JWKS rotation requires explicit operator action. Do not relax the isolated network just for a test.
- **Verification:** local ephemeral RSA-signature/claim tests and protected CI, not a live provider integration. All OIDC tokens have global reader scope only and cannot write or enforce PostgreSQL RLS.
- **Rollback:** restore prior reviewed configuration, restart the API, verify legacy shared tokens still work and OIDC tokens fail after removing the trusted key.

## Native and web OIDC notes client verification

```sh
# Read-only source/build verification, no database mutation:
npm --prefix apps/web ci
npm --prefix apps/web run build
cd apps/android && ./gradlew :app:assembleDebug --no-daemon
```

- **Risk:** local dependency downloads and build outputs, no database writes. These steps do not install or distribute an APK.
- **Verification:** TypeScript/Vite production bundle and native debug compile; no live identity provider/device acceptance is claimed. See [personal clients runbook](PERSONAL_CLIENTS.md).
- **Prerequisites:** suitable Node/npm, Android SDK, Gradle/JDK. The native app still requires operator-provisioned OIDC tokens and an authorized HTTPS gateway.

## Operational liveness and readiness

The local-only gateway provides two deliberately distinct, unauthenticated health probes:

```sh
curl --fail --silent --show-error http://127.0.0.1:4173/api/healthz
curl --fail --silent --show-error http://127.0.0.1:4173/api/readyz
```

- **Risk:** read-only, but connection status is observable; do not expose the developer gateway to public networks.
- `healthz` is process liveness, **not** proof of database access.
- `readyz` checks a real SELECT-only PostgreSQL connection and returns HTTP 503 on failure, without leaking connection strings.
- Compose monitors the API `readyz` check using Python's standard library; only the privately networked API service is probed. See [architecture](ARCHITECTURE.md).
- **Verification:** source/API tests and disposable Compose integration; this is not a full readiness guarantee for S3, Identity, Mesh, or external dependencies.

## Create and inspect a development stack

| Command | Risk / authentication | Verification |
| --- | --- | --- |
| `python3 scripts/init_env.py` | Creates an exclusive private `.env` (0600); refuses overwrite. No elevated rights. | Verify file exists and is ignored; never print its contents. CI config check passed. |
| `docker compose config --quiet` | Read-only configuration check, consumes `.env`; do not print substituted config containing secrets. | Exit 0, configuration accepted. CI verified. |
| `docker compose up --build -d` | **State-changing:** creates/start containers and PostgreSQL volume. Development-only, requires authorized Docker Engine host. | `docker compose ps` and authenticated API smoke; recover using retained data volume and approved backup. |
| `docker compose ps` | Read-only status report. | Check service state and health, never infer public readiness. |
| `docker compose logs --tail=60` | Read-only but **logs may contain private data**. Bound/sanitize output; do not share raw publicly. | Compare nonsecret startup errors; service checks via `scripts/smoke.sh`. |

```sh
# Run from repository root on an authorized disposable development host.
python3 scripts/init_env.py
docker compose config --quiet
docker compose up --build -d
docker compose ps
```

**Important:** Do not use `docker compose down -v` as a reset: it removes persistent data. Changing credentials in `.env` does not rotate database role passwords in existing volumes.

## API, web and Android source validation

```sh
python3 -m compileall -q apps/api/gc_database scripts
python3 -m pip install -e './apps/api[test]'
python3 -m pytest apps/api/tests -q
cd apps/web
npm ci
npm run build
cd ../android
./gradlew :app:assembleDebug --no-daemon
```

- **Risk:** local development dependency installation, compilation and generated artifacts; not host privileged. npm and Gradle require appropriately reviewed dependency sources and disk space.
- **Observed:** Python API tests, React production build, Android debug assemble and package artifact passed in GitHub Actions; builds do **not** establish a signed APK, device installation or public release.

## Disposable integration smoke tests

Run only against an independently authorized local/dev stack whose PostgreSQL volume can safely receive disposable records. The scripts require `GC_ADMIN_TOKEN`, `GC_READ_TOKEN`, and local web port variables loaded from the **existing** `.env`.

```sh
set -a
. ./.env
set +a
sh scripts/smoke.sh
python3 scripts/realtime_smoke.py
python3 scripts/object_storage_smoke.py
```

- **Risk:** **state-changing** demo inserts into `app.catalog` and the bounded `gc_storage.objects` table. CI runs only on its disposable stack.
- **Expected:** authorization rejects anonymous/readonly mutation, authenticated table reads succeed, a committed catalog event arrives, a small file can be uploaded/listed/downloaded with SHA256 integrity. Re-test on each relevant change.
- **Rollback:** development-test database disposal only after backing up anything important and verifying correct target. Do not erase real volumes.

## Bounded CSV page export

Authenticated `GET /api/v1/tables/app/catalog/export.csv?limit=25&offset=0` reads through the PostgreSQL `gc_reader` role and returns a spreadsheet-safe, 2 MiB maximum UTF-8 CSV attachment. It is limited to 500 rows per request and is not a consistent full export. Use the in-memory-authenticated browser **Export page CSV** action or the disposable `sh scripts/smoke.sh` test above; do not place bearer tokens in shell history, query strings or shared download URLs. See [CSV export runbook](CSV_EXPORT.md).

- **Risk:** read-only database access, but output is potentially sensitive and must be saved on approved, private storage.
- **Verification:** disposable CI checks a seeded catalog row and rejects anonymous CSV access.
- **Gap:** user-scoped export, retention, auditing and durable snapshot export are unimplemented.

## Existing-volume SQL migrations

The three scripts require explicit `--apply` and a **verified independent backup**, current compatible Compose PostgreSQL service, properly configured private roles and review of the SQL file. Dry-run invocation without `--apply` exits without executing a mutation.

```sh
sh scripts/apply_readonly_migration.sh
sh scripts/apply_catalog_events_migration.sh
sh scripts/apply_small_object_migration.sh

# After authorized backup and precise existing-volume preflight only:
sh scripts/apply_readonly_migration.sh --apply
sh scripts/apply_catalog_events_migration.sh --apply
sh scripts/apply_small_object_migration.sh --apply
```

- **Risk:** **database schema and privilege mutations**, not mere reads; use the actual reviewed target and correct order. Do not apply to unverified hosts.
- **Verification:** inspect role permissions, trigger event output and small-object read/write restrictions. Verify protected CI smoke.
- **Rollback:** there is no automatic destructive reverse migration. Restore safely using the product's independently verified recovery plan. Do not drop roles or tables as a reflexive rollback.

### Aggregate small-object quota migration

The developer preview caps the private small-object schema at **512 objects / 128 MiB combined content** with a transactional PostgreSQL trigger.

```sh
# No-action usage check:
sh scripts/apply_object_quota_migration.sh
# After independently verified backup, schema review and correct target approval:
sh scripts/apply_object_quota_migration.sh --apply

# Only on an independently verified disposable CI stack:
sh scripts/quota_smoke.sh --disposable
```

- **Risk:** quota migration changes database trigger behavior; requires reviewed credentials, target/backup verification and a rollback plan. The disposable smoke performs inserts inside a rolled-back transaction and must **never** run on production.
- **Verification:** CI validates the 513th small-object insertion is rejected by `gc_storage_total_quota`; the database retains records unchanged after rollback. This is global safety, not a tenant or per-user quota.
- **Limits:** no production storage monitoring, quota enforcement for PostgreSQL WAL overhead, retention/deletion or object encryption certification.

## Governed metadata-audit migration and smoke

```sh
# Safe usage check (does not modify database):
sh scripts/apply_audit_migration.sh
# After independent backup validation and authorization of the exact target:
sh scripts/apply_audit_migration.sh --apply

# On an independently confirmed disposable stack only, with .env loaded:
python3 scripts/audit_smoke.py
```

- **Risk:** audit migration changes PostgreSQL triggers and grants, and may briefly lock tables; review SQL, backups, change window and rollback.
- **Verification:** CI checks catalog/small-object INSERT metadata, rejection of the viewer token, and fixed response fields.
- **Limits:** two source tables only; no actor attribution, retention, tamper evidence or full Wardveil integration. See [audit runbook](AUDIT_METADATA.md).

## Disposable administrator write throttle verification

```sh
# Only after disposable environment, data volume and credentials are verified:
set -a; . ./.env; set +a
python3 scripts/admin_write_smoke.py --disposable
```

- **Risk:** state-changing; intentionally inserts disposable catalog rows, never use on real/irreplaceable records.
- **Expected:** HTTP 429 Retry-After on excess admin writes while viewer reads continue.
- **Limit:** per-process quota reset on restart, no user/tenant protection. See [write throttle runbook](WRITE_THROTTLE.md).

## Isolated per-subject RLS notes migration

```sh
# Safe usage / preflight:
sh scripts/apply_personal_rls_migration.sh
# Only after independently verified backup, issuer policy and target authorization:
sh scripts/apply_personal_rls_migration.sh --apply

# Disposable CI database ONLY; inserts records and rolls them back:
sh scripts/personal_rls_smoke.sh --disposable
```

- **Risk:** adds private PostgreSQL table, RLS policies and a quota trigger; do not use on unreviewed sensitive datasets.
- **Verification:** RLS fails closed with no signed subject, isolates Alice and Bob, rejects forged owner INSERT, limits to 100 notes and rolls back disposable test rows.
- **Limit:** a private preview notes table only, not platform-wide RLS. See [RLS demonstration](PERSONAL_RLS.md).

## Safe single-object deletion privilege and disposable contract

```sh
# Read-only usage check:
sh scripts/apply_object_delete_migration.sh
# Only after independently verified backup, SQL and authorization:
sh scripts/apply_object_delete_migration.sh --apply

# **Disposable database only**, changes one ephemeral test object:
set -a; . ./.env; set +a
python3 scripts/object_deletion_smoke.py --disposable
```

- **Risk:** migration changes DELETE privileges on private objects; the API deletion endpoint is irreversible from the live database. Verify backup/rollback and never run the disposable contract script against important volumes.
- **Verification:** viewer deletion denied, explicit confirmation and expected SHA-256 required, one-row DELETE returns 204, subsequent GET returns 404, metadata-only DELETE audit event verified.
- **Limit:** no soft-delete, per-user object ownership or erasure from backups/WAL. See [object deletion runbook](OBJECT_DELETION.md).

## Explicit per-subject note DELETE policy and disposal test

```sh
# Safe usage check (no mutation):
sh scripts/apply_personal_note_delete_migration.sh
# Reviewed and authorized target only, after verifying backups:
sh scripts/apply_personal_note_delete_migration.sh --apply
# Disposable CI PostgreSQL only; all fixtures are transaction-rolled-back:
sh scripts/personal_rls_smoke.sh --disposable
```

- **Risk:** additive RLS DELETE grant and policy for the private notes table; verify OIDC subject-binding and backups before authorized migration. Do not run against important data without change approval.
- **Verification:** the CI RLS smoke confirms Alice cannot delete Bob's note, can delete Alice's note, and the viewer role lacks DELETE. API tests verify exact explicit confirmation and signed scopes.
- **Limit:** no erasure from WAL/backups, no production consent/retention guarantee. See [privacy limits](PERSONAL_ERASURE.md).

## Read-only SQL migration source integrity check

```sh
python3 scripts/check_migrations.py
python3 scripts/check_migrations.py --json
```

- **Risk:** read-only; does not connect to a database, apply SQL, start containers, modify a manifest or read secrets. JSON reports source-only checksums, **not** applied migration versions.
- **Verification:** protected CI asserts SHA256 manifest entries, contiguous order and exact fresh-volume bootstrap calls. Changed SQL requires a new reviewed migration and a reviewed manifest update.
- **Limit:** an existing volume still needs separately verified migration state, backups, SQL review, explicit authorized `--apply` actions and rollback. See [migration integrity runbook](MIGRATION_INTEGRITY.md).

## Opt-in signed SeaweedFS S3 development sandbox

```sh
# Safe preflight (no writes):
python3 scripts/init_s3_env.py
# Once, with approved local .env and intended storage volume:
python3 scripts/init_s3_env.py --apply
# Read-only overlay config check:
docker compose -f compose.yaml -f compose.s3.yaml --profile s3-preview config --quiet
# Explicit isolated local-only storage start:
docker compose -f compose.yaml -f compose.s3.yaml --profile s3-preview up -d seaweedfs
# Disposable test bucket and generated credentials only, with boto3 installed:
set -a; . ./.env; set +a
python3 scripts/s3_preview_smoke.py --disposable
# Stop without deleting persistent storage:
docker compose -f compose.yaml -f compose.s3.yaml --profile s3-preview stop seaweedfs
```

- **Risk:** opt-in state-changing storage service and secret generation; never run against important data or expose outside loopback. Generate secrets privately, verify your target and consult [S3 preview architecture](S3_PREVIEW.md).
- **Verification:** separate CI job exercises signed S3 protocol PUT/GET/LIST/DELETE, unsigned-denial and safe cleanup. It does **not** change the PostgreSQL object API or enable production S3 storage.
- **Gaps:** no real bucket ACL/tenant Identity integration, TLS release, data migration, encrypted backup or real Android/web object-client S3 acceptance.

## Personal-note write throttle regression tests

```sh
# Local, ephemeral JWT fixtures; no live database writes:
PYTHONPATH=apps/api python3 -m pytest apps/api/tests/test_personal_rate_limits.py -q
```

- **Risk:** local developer test only; no live OIDC provider, VPS, production data or credential file mutation. Requires installed test dependencies.
- **Verification:** parallel signed-subject quota admission, 429/Retry-After, no plaintext subject retention and unaffected personal reads. See [throttle runbook](PERSONAL_WRITE_THROTTLE.md).
- **Limit:** not a global or distributed per-identity quota, no Wardveil alerts or GoreeShield approval.

## Backup and isolated recovery drill

```sh
# Guarded dry runs (no database action):
python3 scripts/backup.py --output /secure/backups/database-YYYYMMDD.backup
python3 scripts/restore_check.py --archive /secure/backups/database-YYYYMMDD.backup

# Approved test host only; output must not exist:
python3 scripts/backup.py --output /secure/backups/database-YYYYMMDD.backup --apply
python3 scripts/restore_check.py --archive /secure/backups/database-YYYYMMDD.backup --apply
```

- **Risk:** `backup.py` reads source data and writes a potentially sensitive **unencrypted** logical archive, exclusive 0600; never use an unapproved shared directory. The restore drill starts a disposable PostgreSQL `--network none` container with no exposed port and removes it after the test.
- **Verification:** printed SHA256/byte count and `pg_restore --list` check, followed by a real isolated schema integrity probe. CI passes this sequence on disposable synthetic data.
- **Limitations:** does not include cluster roles, encrypted off-host recovery, complete WAL/PITR, key recovery, or measured production RPO/RTO. See [recovery documentation](BACKUP_AND_RECOVERY.md).

## Maintenance and command ownership

Command syntax is authoritative in the corresponding repository scripts and `--help`/official Docker, Python, npm, Gradle, and PostgreSQL tools. Change these references alongside the source; reconcile updates into the canonical Drive `CLI Commands` registry when the authorized writer is available. For state-changing commands verify the target host, dependencies, backups, scope and rollback before running. Do not confuse documenting a command with permission to execute it.

**Verification level:** Source/CI-evidenced on 2026-11-25; **host-specific command entry remains not yet centrally synchronized**. No CLI activity was executed on the production VPS to author this document.
