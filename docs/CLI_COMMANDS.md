# GoreeCloud Database — Source CLI runbook

**Status:** Source-side command contracts (not the canonical Google Drive registry).  
**Canonical command registry destination:** `GoreeCloud/CLI Commands/GoreeCloud/Database.md` under the authorized `goreecloud@gmail.com` Google Drive. Source and scripts are maintained here; canonical Drive synchronization requires an authenticated, raw Markdown-capable writer and must be verified separately.

## Context, provenance and scope

- **Product:** original GoreeCloud Database, source: https://github.com/GoreeCloud/database
- **Supported preliminary context:** development/CI Linux shell, Python 3.12+, Node 24+, JDK 17+, Gradle 8.14.3 wrapper, Docker Engine with Compose plugin, PostgreSQL 17.12 / PostgREST 16.6 Compose images. Version support is based on source and tests, not deployment qualification.
- **Observed evidence:** isolated GitHub Actions jobs `api`, `web`, `android`, `config`, `integration` passed at the protected baseline. Exact test outcomes belong to GitHub, not this document.
- **Host:** any separately authorized, reviewed local development or CI Docker host; this runbook is **not** authorization to deploy on the production VPS.
- **Secrets:** use only the local untracked `.env` created by the setup helper. Never place secret values in Git, Drive, terminal history, screenshots, or publicly accessible logs. All examples below use placeholders.

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

## Disposable administrator write throttle verification

```sh
# Only after disposable environment, data volume and credentials are verified:
set -a; . ./.env; set +a
python3 scripts/admin_write_smoke.py --disposable
```

- **Risk:** state-changing; the script deliberately creates temporary catalog rows and tests a 30-per-minute admin write ceiling. It must not target real or irreplaceable records.
- **Expected:** the API eventually returns HTTP 429 with Retry-After for admin writes; anonymous and reader writes remain unauthorized, while viewer reads remain available.
- **Limit:** resets per process/restart, no per-user/tenant protection. See [write throttle runbook](WRITE_THROTTLE.md).

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
