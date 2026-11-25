# Owner-scoped private note deletion — development preview

**Feature:** `DELETE /api/v1/me/notes/{uuid}` deletes one private note that belongs to the current **signature-verified OIDC subject**, never a caller-supplied owner. It requires both OIDC `goreecloud.database.read` and `goreecloud.database.write` scopes and the exact `X-GC-Confirm-Delete: delete-my-note` header. A shared global administrator/viewer token is not an individual identity and cannot delete private notes.

The API parses the target UUID strictly, sets `gc.request_subject` using a bound, **transaction-local** value, and uses a single parameterized SQL DELETE with `WHERE id=%s AND owner_sub=%s`. **PostgreSQL FORCE ROW LEVEL SECURITY** independently enforces the same signed-subject policy for DELETE. Missing confirmation fails with HTTP 428, invalid UUID with HTTP 400, and a non-existent or cross-subject note returns identical HTTP 404.

This does not allow deleting arbitrary `app` rows, another user’s notes, whole tables, backups, or objects.

## Migration

A fresh database volume applies `009-personal-note-delete.sql` after `007-personal-notes-rls.sql`. The additive SQL grants DELETE on **only** `gc_personal.notes` to non-superuser `gc_api`, revokes it from viewer/anonymous roles, and reinstalls the owner-equality RLS policy. It never changes existing note ownership, contents or the public `app` schema.

For an existing volume, independently verify backup recoverability, SQL roles, consent and the target before explicitly applying:

```sh
sh scripts/apply_personal_note_delete_migration.sh
sh scripts/apply_personal_note_delete_migration.sh --apply
```

Do not remove persistent volumes to force initialization.

## CI validation

The rollback-contained `scripts/personal_rls_smoke.sh --disposable` exercises note fixtures for two distinct subjects, confirms Bob cannot be deleted under Alice’s PostgreSQL role/context, confirms Alice can delete her own note, and rolls all changes back. API regression tests validate signed-token scope separation, missing confirmation, malformed UUID handling, and bound SQL parameters. No real user notes are touched by CI.

## Privacy limits

This is a **live-table deletion only**: note content may remain in database WAL, snapshots, encrypted backups, external exports, device/browser caches or infrastructure backups. It is not certified secure physical destruction, GDPR erasure, account closure or a complete GoreeShield retention policy. There is no undo, actor audit trail, deletion receipts, full lifecycle, offline conflict resolution or independently measured RPO/RTO. Do not store sensitive family notes until these controls and a real GoreeCloud Identity login are accepted.
