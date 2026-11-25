# Small-object browser client support

**Status:** development source, not a signed or device-qualified release.

## Browser console

The React console includes an "Small objects" panel. After authentication, the viewer or administrator can choose **Refresh objects** to list up to 50 recent attachment metadata records. The administrator alone can upload one file of 1 byte–1 MiB through the existing authenticated API; the browser validates a safe ASCII basename and the server checks MIME type and size again. Supported MIME types are `text/plain`, `image/png`, `image/jpeg`, `application/pdf` and `application/octet-stream`.

Object downloads go through the authenticated API, are size-checked against returned metadata and trigger a browser Save operation. The server verifies SHA256, sends `Content-Disposition: attachment` and `nosniff`; a browser object URL is revoked after download initiation. The browser does not store credentials or object payloads in persistent browser storage.

## Native Android client

The Jetpack Compose Android management app adds a "Small objects" view listing up to 50 recent metadata records and a user-selected Save action. A file is read over standard Android TLS with redirect refusal and a 1 MiB stream limit; the native client verifies size and SHA256 before writing to the destination selected through Android's Storage Access Framework. No broad filesystem permissions, background file sync or token persistence are introduced. Only the server's shared admin/viewer token model is presently supported.

## Security caveats and gaps

- **All viewer credentials can read all objects**; this is intentionally not a per-user sharing system.
- MIME types are checked by declared media type but **there is no server-side content sniffing or malware scanning**.
- The PostgreSQL storage subsystem has a global 512-object/128 MiB quota and an administrator-only [two-step single-object deletion UI](OBJECT_DELETION.md), but **no per-tenant ACL, governed retention, reversible erasure, revision history or object encryption key management**.
- Real device TLS, file saving, backup/restore of large object sets, accessibility, memory pressure and browser behaviour must be tested beyond compilation before any stable Android/web release.
- A production S3-compatible backend and independently verified identity enforcement remain on [issue #7](https://github.com/GoreeCloud/database/issues/7).

Use the [small-object API contract](SMALL_OBJECTS.md) and [security policy](../SECURITY.md) as the source for backend restrictions.
