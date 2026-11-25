# Native Android schema-inspection preview

The Android Jetpack Compose database client can now inspect table metadata through the existing **read-only**, authenticated `GET /api/v1/tables/app/{table}/schema` endpoint.

From a table's row viewer, select **Inspect schema** to see columns, PostgreSQL data types, nullable/primary-key status, default expressions and index definitions. Choose **Refresh schema** to reread metadata; **Table rows** returns to the previous view. This is display-only: no schema migration, DDL execution or arbitrary SQL UI is added.

## Privacy and security boundaries

- Uses the same `DatabaseClient` as table row reads. That client requires HTTPS, refuses redirects, sets a bearer token in request headers and does not persist credentials in Android preferences or logcat.
- The backend restricts identifiers to the `app` schema and serves metadata with the SELECT-only role. Shared admin/viewer tokens are development credentials; they do not provide named-user or tenant isolation.
- Metadata values are rendered as text; default expressions and index definitions are **never executed** in Android.
- No local SQLite/offline metadata cache or background synchronization is created. Inspection may fail without an authorized reachable HTTPS gateway; no HTTP fallback is provided.
- The screens reuse the existing Android Material 3 semantic theme, without asserting a verified stable `GoreeCloud UI` component library integration.

## Validation

Local Gradle `./gradlew :app:assembleDebug --offline --no-daemon` succeeded on an authorized developer laptop on November 25, 2026. GitHub protected CI must pass after PR creation. A debug build does **not** establish device compatibility, accessibility acceptance, production signing or deployment. Check these independently before a release.

## Future

Authenticated per-user schema visibility, safe migration planning and rollback, schema-editor UX, versioned API contracts, and production Identity/Shield/Wardveil/Mesh policy enforcement remain future work.
