# Validation and release gates

Local checks:

```sh
python3 -m compileall -q apps/api/gc_database scripts
python3 -m pip install -e './apps/api[test]'
python3 -m pytest apps/api/tests -q
cd apps/web && npm ci && npm run build
cd ../android && ./gradlew :app:assembleDebug
```

Container smoke (only on an authorized Docker host):

```sh
python3 scripts/init_env.py
docker compose config --quiet
docker compose up --build -d
docker compose ps
curl -fsS http://127.0.0.1:4173/rest/catalog
# With generated .env exported and the disposable stack running:
set -a; . ./.env; set +a
sh scripts/smoke.sh
python3 scripts/realtime_smoke.py
# Against disposable local stack only:
python3 scripts/backup.py --output /tmp/gcdb-test.backup --apply
python3 scripts/restore_check.py --archive /tmp/gcdb-test.backup --apply
```

No tests claim live host hardening, TLS, data recovery, multiuser authentication, production approval or Android device acceptance. The Android debug APK is debug-signed only, not a signed or device-accepted production release artifact.

## Planned acceptance

- Verified PostgreSQL init roles, separate API liveness/readiness probes, psql/REST read, authenticated bounded CSV export, read-only schema inspection, administrator-only metadata audit, and management token rejection.
- Concurrent data reads and writes with restrictive roles, migrations rollback and extensions compatibility.
- Signed OIDC subject/scoped-write unit fixtures, and transaction-rolled-back PostgreSQL RLS ownership, delete-confirmation, cross-user deletion denial and per-owner quota checks for `gc_personal.notes` (not live Identity, platform-wide RLS or real-user consent acceptance); mobile TLS and certificate verification, configuration transitions and authorization expiry.
- Logical dump and isolated-restore smoke through CI, including disposable NOLOGIN policy-role stubs and RLS-policy-preservation checks (not yet an off-host encrypted backup, PITR or measured RPO/RTO).
- Ordered source migration SHA-256 manifest verification, no duplicate/gapped first-boot SQL invocations; not a verified existing-volume migration state or automated runner.
- Optional Wasmtime 51.0.0 signed-source-hash and pure `run(i32)->i32` development CLI checks: rejected host imports, fake modules, unbounded input, excessive memory and fuel consumption. No production runtime/provenance certification.
- Opt-in SeaweedFS S3 protocol integration (separate `s3-preview` CI job) tests private SigV4 LIST/PUT/GET/DELETE and unsigned bucket-list rejection, not the production object API, replication, tenant policies or backup recovery.
- Dependency/license audit, source SBOM and reproducible pinned image digests.
- React private-notes view and native Kotlin notes browser production/debug builds; physical-device, accessibility, signed-APK distribution and live IdP acceptance remain unverified.
- Accessibility and device-specific QA; signer and APK distribution provenance.
