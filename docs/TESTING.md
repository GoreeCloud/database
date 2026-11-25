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
- Signed OIDC subject/scoped-write unit fixtures, and transaction-rolled-back PostgreSQL RLS ownership/quota integration checks for `gc_personal.notes` (not live Identity, platform-wide RLS or real-user consent acceptance); mobile TLS and certificate verification, configuration transitions and authorization expiry.
- Logical dump and isolated-restore smoke through CI, including disposable NOLOGIN policy-role stubs and RLS-policy-preservation checks (not yet an off-host encrypted backup, PITR or measured RPO/RTO).
- Dependency/license audit, source SBOM and reproducible pinned image digests.
- Accessibility and device-specific QA; signer and APK distribution provenance.
