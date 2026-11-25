# Explicit small-object deletion — development preview

## API contract

The administrator-only `DELETE /api/v1/objects/{uuid}` permanently removes **one** private object from the live `gc_storage.objects` table. It requires both:

- `X-GC-Confirm-Delete: permanently-delete` — an exact, deliberate action gate.
- `X-GC-Expected-SHA256: <64-lowercase-hex-digest>` — a previously verified checksum from the authenticated object-listing metadata. The SQL matches **both** UUID and checksum to refuse stale or confused deletions.

The endpoint executes the single parameterized `DELETE ... WHERE id=%s AND sha256=%s RETURNING id` under the non-superuser `gc_api` role. A 204 response proves that row was deleted and transaction committed. An invalid or missing confirmation is rejected with HTTP 428; malformed checksums/UUIDs are rejected; an unmatched object/checksum returns 404 without divulging which condition failed. A reader/OIDC token cannot delete objects. The existing 30-per-minute shared-admin write throttle applies.

The `gc_audit` metadata-only trigger records a DELETE event without content, filename or object ID. **It does not make deletion tamper-proof**. This endpoint does not expose arbitrary SQL, external URLs, user-defined object paths, recursive deletes or bulk operations.

## Web user confirmation

The administrator console shows a **Delete** action for existing objects. Selecting it first opens an explicit confirmation with the exact filename and checksum. A second action confirms permanent deletion. Reads and downloads are unaffected.

**Deletion is irreversible from the live table.** It does not guarantee physical removal from database WAL, logical/off-site backups, storage snapshots, logs or device caches. A GoreeShield retention/erasure standard, backup expiration controls and independently verified deletion/restore drills remain unimplemented.

## Existing database volumes

Fresh PostgreSQL volumes apply the additive `008-small-object-delete.sql` privileges migration. Existing volumes must **not** be wiped for migration. Back up and verify recovery on the intended target before explicitly running:

```sh
# Usage guard, no mutation:
sh scripts/apply_object_delete_migration.sh
# Authorized and reviewed only:
sh scripts/apply_object_delete_migration.sh --apply
```

The SQL grants DELETE only on the private object table to `gc_api` and explicitly revokes DELETE from common reader/anonymous roles. It does not give the API write access to audit or personal schemas.

## Disposable CI verification

`python3 scripts/object_deletion_smoke.py --disposable` uploads an ephemeral 1-byte object, confirms viewer deletion denial, rejects insufficient confirmation and incorrect expected checksum, deletes it with the two safety headers, then verifies a 404 on read and a recorded metadata-only DELETE audit entry. Use **only** on confirmed disposable test volumes; this script changes data.

## Known limitations

No undo/soft-delete, per-user ownership, tenant-scoped retention, independent authorizer, permission delegation, storage quota releases monitoring, secure destruction guarantees, signed deletion receipt, or restore from independently managed backups is present. This is a limited development administration action, not production personal-data erasure compliance.
