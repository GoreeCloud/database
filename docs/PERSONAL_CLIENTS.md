# Personal notes clients — signed OIDC preview

The React web console and native Android Jetpack Compose client can read and create notes in the separately isolated `gc_personal.notes` PostgreSQL table, using the verified subject in a short-lived OIDC access token. The [underlying RLS contract](PERSONAL_RLS.md) is enforced by PostgreSQL, **not** by client filtering.

## Web console

The authenticated console has a **Personal notes** panel below the general table explorer. Select **Open private notes** to attempt an authenticated read; it makes **no note request before explicit opening**. Only a signed OIDC token accepted by the API can see notes; using a shared admin or viewer token produces a clear access message instead of returning data.

A validated reader sees up to 25 notes per page and can browse with Previous/Next or Refresh. Create note accepts a title (1–120 characters) and content (1–2048 Unicode characters, at most 8192 UTF-8 bytes), and requires an additional OIDC `goreecloud.database.write` scope. The server computes the note owner from the verified JWT; there is no owner input in the form or POST body.

**Clear and close**, disconnect, token replacement and component unmount clear note values and pending drafts from React state. GET requests are aborted on token changes or closure; successful POST attempts use no-store caching. The UI renders note strings as React text, not raw HTML. No localStorage, IndexedDB, service worker, analytics, or browser-side SQL is added.

## Android app

From the connected Tables view, choose **Personal notes (signed OIDC)**. The native Compose view loads up to 25 notes over the existing TLS-only `DatabaseClient`; creating a note uses `POST /v1/me/notes` with `application/json`. Both operations use the manually entered in-memory bearer token, 8-second timeouts, and redirect refusal. Android does not obtain token values from an external provider, embed private keys or authorize itself to set owner IDs.

The personal-note editor and loaded content use ordinary Compose `remember`, **not** `rememberSaveable`, preferences, filesystem caches, system logs, notifications or a background worker. Returning to Tables or disconnecting clears the visible notes/drafts. The app does not request broad Android storage permissions.

## Authorization and limitations

- The existing global catalog, object, and audit endpoints retain their separate shared token semantics. A personal-note write scope does **not** allow administrator writes elsewhere.
- Both clients require an already provisioned, operator-approved, signed OIDC access token, which the user enters manually. **OAuth authorization-code + PKCE sign-in, refresh and logout are not implemented.**
- A read-only signed token may browse but cannot create a note. Shared admin/viewer tokens cannot browse private notes. The backend's `gc_personal.notes` RLS policies prevent cross-subject reads and owner-forgery inserts.
- There is no content encryption at rest beyond the host's separately configured storage protection, no offline cache or sync, no retention/delete export, no actor audit, no user-specific rate limiter, and no certified live provider integration.
- The preview is not approved for production personal/family information. GoreeShield must govern consent/minimization/retention, Wardveil the security acceptance, and GoreeCloud Identity real OAuth lifecycle and access policies.

## Validation and release status

The React TypeScript production build and Android `./gradlew :app:assembleDebug --offline --no-daemon` are local development validations. The PR must also pass the five protected GitHub CI checks. **A debug-signed APK build is not a production release or real-device acceptance.** Client interactions with a real OIDC provider and physical Android device remain unverified.
