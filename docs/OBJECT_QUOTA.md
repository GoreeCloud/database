# Small-object global quota — preview guard

The dedicated PostgreSQL `gc_storage` schema now has an aggregate capacity guard protecting the development preview from indefinite repeated 1 MiB uploads. It does not turn the system into a production object store or per-user authorization service.

## Guardrails

- **512 objects total** and **128 MiB combined content bytes** are the built-in upper bounds.
- A PostgreSQL `BEFORE INSERT` trigger serializes capacity checks with a transaction-level advisory lock, counts existing rows, sums declared byte lengths, and rejects an over-capacity insert.
- The existing 1 MiB per-object check remains in the table constraint and upload API.
- The FastAPI upload operation maps only the named quota-check database violation to HTTP **507 Insufficient Storage**, without returning SQL or private data.
- A viewer token has only SELECT on the private schema and cannot override database-enforced limits.
- Existing records are **never deleted** by this migration. An existing volume already above the cap will retain its data but decline further object insertion until an authorized administrator uses the separately gated [single-object deletion path](OBJECT_DELETION.md) after verifying the correct target and backups.

These fixed caps are deliberately conservative and do not guarantee host-wide free space, quota isolation between users, encrypted storage, malware scanning, or safe production operation.

## First installation and existing volumes

Fresh installations invoke `005-object-quota.sql` after schema creation. On an existing volume, make and **verify an independent recovery point** first; inspect volume size and table count; then explicitly apply:

```sh
sh scripts/apply_object_quota_migration.sh
# Once reviewed and authorized, on the verified development target:
sh scripts/apply_object_quota_migration.sh --apply
```

The script is idempotent and wraps trigger replacement in one transaction. It is not a license to migrate production without a staged change window. Do not remove data or volumes to bypass the limit.

## Disposable CI verification only

```sh
sh scripts/quota_smoke.sh --disposable
```

This runs 512 one-byte test INSERTs plus one expected rejected INSERT inside a transaction rolled back at completion. It must run only on an independently confirmed disposable CI stack. The test reports failure if the quota is absent or a different constraint is violated. It does not establish a full load-test/backup policy or protect against superusers intentionally disabling database triggers.

**Future acceptance:** tenant-specific limits, an authenticated revocable user identity, governed retention and deletion, actual byte-usage monitoring and operationally verified S3-compatible storage (see issue #7).
