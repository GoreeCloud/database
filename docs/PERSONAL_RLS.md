# Isolated per-subject PostgreSQL RLS notes — development preview

**Scope:** A deliberately narrow **private notes example**, not conversion of the existing catalog/object APIs to tenant isolation, not a complete GoreeCloud Identity implementation, and not appropriate for sensitive family data until production security/recovery review.

## Data model and security boundaries

A new PostgreSQL `gc_personal.notes` table has an opaque row UUID, **verified OIDC subject** (`owner_sub`), title (1–120 characters), content (1–2048 characters / 8192 UTF-8 bytes) and creation timestamp. It is **not** included in the anonymous PostgREST `app` schema or generic management table explorer.

- `ENABLE ROW LEVEL SECURITY` and `FORCE ROW LEVEL SECURITY` are active.
- PostgreSQL SELECT policy requires `owner_sub = current_setting('gc.request_subject', true)`. With no subject, it returns no rows.
- INSERT policy requires the same signed subject; attempts to insert under another subject are rejected at the database layer.
- The app sets `gc.request_subject` using a SQL bind parameter and `set_config(..., true)`, **transaction-local only**, before every query. Connections are not pooled across requests.
- The `gc_reader` role has SELECT, no INSERT/UPDATE/DELETE. The `gc_api` role has SELECT/INSERT and now [confirmed subject-only DELETE](PERSONAL_ERASURE.md) with RLS enabled, but no UPDATE. Database owner/superuser access remains a trusted infrastructure boundary; anyone stealing database credentials could set arbitrary session variables.
- A PostgreSQL `SECURITY DEFINER` trigger provides an **atomic, per-subject maximum of 100 notes** using a transaction advisory lock, with a safe HTTP 507 on capacity exhaustion. Total disk space and WAL use are not capped by this feature.

The service does **not** store raw JWTs, IPs, access-token claims or external profile fields in the notes table. The verified `sub` is retained only as the necessary record owner and therefore **is personal data**; GoreeShield retention/deletion, export and explicit consent must be addressed before using real personal notes.

## OIDC scope separation

Operator-configured OIDC (see [OIDC verifier](OIDC_READER.md)) is mandatory for these two **person-specific** endpoints. Shared admin/viewer tokens are **not** identities and are rejected by both.

| Route | Minimum validated scopes | Behavior |
| --- | --- | --- |
| `GET /api/v1/me/notes?limit=25&offset=0` | `goreecloud.database.read` | Returns only the OIDC subject's rows, 1–50 per page |
| `POST /api/v1/me/notes` | **Both** `goreecloud.database.read` and `goreecloud.database.write` | Inserts title+content only; subject is taken from signature-verified JWT, never JSON |

Importantly, an OIDC token with both scopes **still maps to reader** for all existing global catalog/attachment APIs. It cannot call their administrative writes or inspect the audit metadata. The new `write` scope is not an administrator role.

## First installation and migration

A fresh database volume runs `007-personal-notes-rls.sql`. On an existing volume, first verify a recoverable backup, table-owner and role permissions, approved provider configuration and PostgreSQL version. Then explicitly apply the additive migration:

```sh
sh scripts/apply_personal_rls_migration.sh
# On the verified and authorized target, after backup and SQL review:
sh scripts/apply_personal_rls_migration.sh --apply
```

Do not remove volumes to force migration. Do not weaken existing anonymous read roles or install RLS on unrelated tables before independently validating their data models.

## Tests and limits

```sh
# **Disposable CI database only**, performs test inserts inside a rolled-back transaction:
sh scripts/personal_rls_smoke.sh --disposable
```

The [React and native Android notes clients](PERSONAL_CLIENTS.md) display and create subject-scoped notes using manually supplied approved OIDC tokens; neither implements PKCE login. The development API additionally uses a [bounded per-signed-subject note mutation limiter](PERSONAL_WRITE_THROTTLE.md) with process-local, privacy-preserving HMAC pseudonyms. The database smoke verifies absent-subject denial, Alice/Bob SELECT isolation, blocked forged owner INSERT, [owner-only DELETE](PERSONAL_ERASURE.md) and the 101st-note quota rejection, then rolls back all test rows. RSA JWT tests validate signed subject/scope binding. The isolated recovery drill uses disposable **NOLOGIN** role stubs, restores a custom archive and verifies that FORCE RLS and owner policies survive without copying live credentials.

**Not yet implemented:** production Keycloak/GoreeCloud Identity provisioning, OAuth authorization-code + PKCE clients, logout/revocation lifecycle, default tenant-wide RLS across all `app` tables, private object RLS, per-user rate limiting, persistent encrypted client/offline sync, searchable notes, governed retention and account-level erasure, actor attribution, independent security audit or protected production deployment.

The separate repository issue [#6](https://github.com/GoreeCloud/database/issues/6) remains open until real ecosystem-wide identity/RLS acceptance.
