# Signed OIDC access boundaries — fail-closed preview

GoreeCloud Identity owns authentication and authorization design; this repository implements only the locally verified RS256/JWKS token adapter and a narrowly isolated PostgreSQL RLS personal notes example. There is **no** live IdP, OAuth authorization-code + PKCE login, refresh/revocation, user lifecycle or production tenant security certification.

## Default access matrix

| Credential | `GET /api/v1/session` scope | Global catalog/CSV/objects/SSE | `/api/v1/me/notes` |
| --- | --- | --- | --- |
| Shared administrator secret | `admin` | Shared administrator access under existing API rules | **Denied**: not an individual signed identity |
| Shared viewer secret | `reader` | Existing shared global read-only access | **Denied**: not an individual signed identity |
| Verified RS256 OIDC access token + `goreecloud.database.read` | `personal` | **Denied** (401), even with a valid read scope | Subject-owned SELECT only, PostgreSQL FORCE RLS |
| Verified RS256 token + read **and** write scopes | `personal` | **Denied** by default (401) | Subject-owned SELECT, INSERT, explicitly confirmed DELETE |
| Verified RS256 token, with **operator opt-in** `GC_OIDC_GLOBAL_READ_ENABLED=true` | `reader` | Shared global reader across `app`/object APIs, not per-user-filtered | Same owner-scoped notes capability determined by scopes |
| Invalid, expired, missing or incorrectly scoped token | None | Denied | Denied |

**Default:** `GC_OIDC_GLOBAL_READ_ENABLED=false`; no separate initialization is necessary. The environment setting accepts only the lowercase literal `true` or `false`. Invalid values fail process startup; enabling broad OIDC reads without a fully configured trusted issuer and public JWKS also fails. A signed token is never equivalent to a global admin token.

The `/v1/session` endpoint reveals only the generic `personal` scope and `personal.read` permission to an authenticated individual, not their subject identifier, email, profile, token claims or stored notes. It is **not** a general-purpose login endpoint.

## Enabling legacy global reader access (high risk)

Do not enable on hosts holding or about to hold private or family information. Legacy consumers expecting signed OIDC to read `app.catalog` or global attachments must first be audited for per-user data exposure and may only be reenabled with explicit authorization and a reviewed migration plan.

```sh
# Read-only check of currently declared file and option:
grep -n 'GC_OIDC_GLOBAL_READ_ENABLED' compose.yaml
# Documentation-only example: set GC_OIDC_GLOBAL_READ_ENABLED=true in
# the privately managed authorized .env; never commit the file.
# Do NOT execute a restart against a production database as a test.
```

When operating a reviewed isolated test stack, inspect the exact Compose service environment and perform `GET /api/v1/session` and catalog/objects authorization tests for both settings. A configuration change requires a reviewed API service restart. Restore `false` on rollback, verify rejected global reads and successful personal notes, and inspect logs for unexpected access without exposing sensitive tokens.

## React and Android client behavior

Both clients verify `/v1/session` before requesting shared tables. A `personal` session opens a dedicated notes experience and never mounts the shared table, storage, CSV or audit components. A shared admin/viewer session continues into the database explorer. The manually supplied bearer token and notes remain transient in memory. The Android client requires HTTPS and refuses redirects. The web client does not persist token data in browser storage.

The clients do **not** automatically retrieve or refresh an OIDC token, prove enterprise SSO compatibility, verify a phone/device, or provide a production logout; the user must provision a valid authorized token and an approved TLS endpoint externally.

## Test and production acceptance

Unit regression tests create ephemeral RSA JWT signatures, assert default personal-only session boundaries, deny generic catalog/objects/audit/CSV/SSE access, ensure shared admin/viewer behavior remains intact, verify explicit global reader opt-in, reject invalid flags and confirm fail-closed OIDC startup. The existing real PostgreSQL smoke tests independently enforce Alice/Bob RLS note isolation.

**Unimplemented:** per-user RLS for `app` tables and S3 objects, identity-scoped quotas and rate limiting, tenant controls, consent and retention governance, actor-attributed auditing, PKCE login, refresh and revocation, encrypted mobile offline storage, and production Wardveil/GoreeShield acceptance.
