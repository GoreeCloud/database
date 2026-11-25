# Personal notes clients — signed OIDC preview

The React web console and native Android Jetpack Compose client can read and create notes in the separately isolated `gc_personal.notes` PostgreSQL table, using the verified subject in a short-lived OIDC access token. The [underlying RLS contract](PERSONAL_RLS.md) is enforced by PostgreSQL, **not** by client filtering.

## Web console

The web console first verifies the supplied bearer token through `/v1/session`. For a `personal` identity, it displays a **dedicated notes-only workspace** and never requests shared catalog, storage, CSV or audit endpoints. Shared management tokens continue to the general table explorer, which also has a Personal notes panel that cannot use the shared secret as an individual identity. Select **Open private notes** to request note content; no notes are requested until opened. See [OIDC access matrix](OIDC_ACCESS_BOUNDARIES.md).

A validated reader sees up to 25 notes per page and can browse with Previous/Next or Refresh. Create note accepts a title (1–120 characters) and content (1–2048 Unicode characters, at most 8192 UTF-8 bytes), and requires an additional OIDC `goreecloud.database.write` scope. The server computes the note owner from the verified JWT; there is no owner input in the form or POST body.

**Clear and close**, disconnect, token replacement and component unmount clear note values and pending drafts from React state. GET requests are aborted on token changes or closure; successful POST attempts use no-store caching. The UI renders note strings as React text, not raw HTML. No localStorage, IndexedDB, service worker, analytics, or browser-side SQL is added.

## Android app

The Android client first requests `/v1/session` over HTTPS. A `personal` scope directly opens **Personal notes** without requesting global tables; shared admin/viewer sessions retain the Tables view and its optional notes panel. The native Compose notes view loads up to 25 notes over the TLS-only `DatabaseClient`; creating a note uses `POST /v1/me/notes` with `application/json`. Both operations use the manually entered in-memory bearer token, 8-second timeouts, and redirect refusal. Android does not obtain token values from an external provider, embed private keys or authorize itself to set owner IDs.

Both clients now provide a **two-step note deletion confirmation**: first choose a note, then explicitly confirm; only a signed OIDC token with read and write scopes can delete that subject's note. The API responds 204 on a verified owned-row deletion, 404 for an absent/cross-user UUID, and 428 when the exact confirmation header is missing. This removes only the live-table row, not backups/WAL. The web and Android dialogs do not store deleted notes in persistent client storage.

The personal-note editor and loaded content use ordinary Compose `remember`, **not** `rememberSaveable`, preferences, filesystem caches, system logs, notifications or a background worker. Returning to Tables or disconnecting clears the visible notes/drafts. The app does not request broad Android storage permissions.

## Authorization and limitations

- The existing global catalog, object, and audit endpoints retain their separate shared token semantics. A personal-note write scope does **not** allow administrator writes elsewhere.
- Both clients require an already provisioned, operator-approved, signed OIDC access token, which the user enters manually. **OAuth authorization-code + PKCE sign-in, refresh and logout are not implemented.**
- A read-only signed token may browse its private notes but cannot create or delete a note. By default, it has no global catalog/object access. Shared admin/viewer tokens cannot browse private notes. The backend's `gc_personal.notes` RLS policies prevent cross-subject reads, deletion and owner-forgery inserts. Legacy global reader access requires an explicit operator opt-in.
- There is no content encryption at rest beyond the host's separately configured storage protection, no offline cache or sync, no governed retention/account-level erasure, no actor audit, no user-specific rate limiter, and no certified live provider integration. Individual note DELETE is supported but does not purge backups.
- The preview is not approved for production personal/family information. GoreeShield must govern consent/minimization/retention, Wardveil the security acceptance, and GoreeCloud Identity real OAuth lifecycle and access policies.

## Validation and release status

The React TypeScript production build and Android `./gradlew :app:assembleDebug --offline --no-daemon` are local development validations. The PR must also pass the five protected GitHub CI checks. **A debug-signed APK build is not a production release or real-device acceptance.** Client interactions with a real OIDC provider and physical Android device remain unverified.
