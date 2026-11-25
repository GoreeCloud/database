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
python3 scripts/realtime_smoke.py
set -a; . ./.env; set +a
sh scripts/smoke.sh
```

No tests claim live host hardening, TLS, data recovery, multiuser authentication, production approval or Android device acceptance. The Android debug APK is unsigned for distribution and not an accepted release artifact.

## Planned acceptance

- Verified PostgreSQL init roles, psql/REST read and management token rejection.
- Concurrent data reads and writes with restrictive roles, migrations rollback and extensions compatibility.
- Mobile TLS and certificate verification, configuration transitions, authorization expiry.
- Restore from separate verified backup into isolated database, integrity and RPO/RTO measurement.
- Dependency/license audit, source SBOM and reproducible pinned image digests.
- Accessibility and device-specific QA; signer and APK distribution provenance.
