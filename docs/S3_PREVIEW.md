# Opt-in signed SeaweedFS S3 protocol sandbox — development preview

This is a **separate, opt-in** S3-compatible object store using upstream open-source **SeaweedFS 4.54**, included via `compose.s3.yaml`. It is **not** wired to the current `/api/v1/objects` PostgreSQL-backed object API or the React/Android object clients. No data is automatically migrated or copied. Do not treat this as S3 production acceptance, backup storage, or multi-tenant bucket isolation.

## Isolation and credentials

- The overlay starts **only** if the `s3-preview` Compose profile and overlay are explicitly selected. The normal `docker compose up` and web/Android interfaces do not start SeaweedFS.
- Its S3 API binds to **127.0.0.1:8333 only**, configurable via `GC_S3_PORT`; there are **no host bindings** for master, filer, WebDAV, or Admin UI.
- The service uses separate generated **S3 access/secret credentials** (SigV4) and a separate Admin password; it refuses partial/duplicate credential initialization. A signed client may access a single preview bucket `goreecloud-preview`.
- `weed mini` Admin and WebDAV insecure binds are disabled with documented 4.54 flags. A readonly root FS, private persistent data volume, `no-new-privileges` and a temporary `/tmp` filesystem reduce unintended writes and privileges.
- The container joins the project `data` internal network and `access` bridge to allow loopback port forwarding. **The access bridge can permit outbound network access**; this is not equivalent to an egress-isolated enclave. A production overlay must implement separate audited TLS, service/network policy and authorization.
- The one-node mini service is **not replicated**, is **not an encrypted/backed-up storage guarantee**, has no tenant-scoped IAM/STS policy design accepted by GoreeShield or Wardveil, and must not hold sensitive or irreplaceable data.

## Local development instructions

From an authorized test checkout with a generated private `.env`:

```sh
# No-op usage; does not append secrets
python3 scripts/init_s3_env.py

# One-time explicit action: append independent high-entropy private credentials
python3 scripts/init_s3_env.py --apply

# Compose config inspection
docker compose -f compose.yaml -f compose.s3.yaml --profile s3-preview config --quiet

# Starts only optional signed object-storage sandbox, not the API stack
docker compose -f compose.yaml -f compose.s3.yaml --profile s3-preview up -d seaweedfs

# On a disposable test volume ONLY, with boto3 installed and private .env loaded:
set -a; . ./.env; set +a
python3 scripts/s3_preview_smoke.py --disposable

# Stops test service; persistent volume is retained, NOT deleted
docker compose -f compose.yaml -f compose.s3.yaml --profile s3-preview stop seaweedfs
```

Never paste the generated credentials, `.env`, S3 authorization headers, or signed requests into public commands or tickets. The helper file remains local and mode 0600. No `down -v`, bucket wipe, deletion of existing persistent data, or upload of private user data is required.

## Disposable CI acceptance

The optional `s3-preview` GitHub Actions job creates a **new disposable** private `.env`, starts only the SeaweedFS overlay on loopback, uses Python boto3 with SigV4 to verify bucket listing, PUT, GET, LIST and DELETE of a randomly named test object, and asserts that an unsigned listing is rejected. After verification it stops containers without removing named volumes. GitHub-hosted job storage is ephemeral; this is not a production backup/recovery test.

The test does not claim a live Android/web integration, per-user bucket ACL, data lifecycle, encryption-at-rest, MFA, public ingress security or full S3 API compatibility matrix.

## Upstream and licensing

SeaweedFS is an independent Apache-2.0-licensed open-source project: https://github.com/seaweedfs/seaweedfs. Its [documented single-node `weed mini` S3 quickstart](https://github.com/seaweedfs/seaweedfs#quick-start) supports access/secret key environment variables, a `S3_BUCKET` and the S3 gateway on port 8333. Source is not copied or relicensed in this repository; a version-tagged upstream container image runs only when explicitly enabled. Production-grade decisions should verify the exact immutable image digest/signature, storage durability, tenant policies and disaster recovery before deployment.

## Remaining integration

Move `gc_storage` from PostgreSQL-inline payloads to properly authorized S3 bucket objects only after an approved storage-schema migration with reliable dual-write/rollback, object ownership/ACL mapping, checksum validation, quota enforcement, background reconciliation, encrypted offsite backups and client acceptance. That design is tracked in [issue #7](https://github.com/GoreeCloud/database/issues/7).
