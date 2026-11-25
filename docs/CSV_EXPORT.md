# Bounded CSV table export — development preview

## Contract

`GET /api/v1/tables/app/{table}/export.csv?limit=100&offset=0` returns a UTF-8 CSV attachment, using an authenticated administrator or viewer bearer token. It is **read-only**: the SQL executes with the separate SELECT-only PostgreSQL role, and only the existing `app` schema and conservative identifier format are permitted.

- Default 100 rows; maximum 500 rows per request, up to 100 columns and a hard 2 MiB encoded response bound. The web table explorer exports **the current 25-row page**, matching its displayed offset.
- Null values serialize to an empty CSV cell; strings, dates, decimals, byte fields, and JSON-shaped records use safe textual representations.
- CSV headers and data are escaped through Python's CSV writer. Values beginning with spreadsheet formula operators (`=`, `+`, `-`, `@`) even after whitespace, or starting with control characters, are prefixed with an apostrophe to avoid formula execution when opened in common spreadsheet programs. This is defense in depth rather than a universal guarantee across all viewers.
- All response content is returned with attachment disposition, `nosniff`, no-store caching, and sandbox CSP. The browser fetches with an in-memory bearer token, makes a local download URL and revokes it after initiation.
- Exports intentionally contain **only the requested page**, not a snapshot-consistent or scheduled full-backup dataset. Page ordering is not guaranteed during concurrent modifications. The existing database recovery tooling remains the authoritative bulk recovery path.

## CLI verification on disposable local development

From the repository root, with the test stack started and `.env` provisioned:

```sh
set -a
. ./.env
set +a
sh scripts/smoke.sh
```

The smoke checks viewer CSV read, the `app.catalog` seeded row and anonymous export denial. The endpoint does not accept caller-authored SQL, file paths, S3 URLs, query programs or shell commands.

## Security limitations

**The shared viewer token can read and export every table exposed through the development `app` schema.** Do not use this as a tenant-scoped GDPR export or a production data export. Per-person GoreeCloud Identity permissions, row-level security, export audit trails, user-specific minimization, long-running snapshot jobs, encrypted archives and retention controls remain pending.

Use the separate [backup/recovery runbook](BACKUP_AND_RECOVERY.md) for database continuity and [security policy](../SECURITY.md) for current deployment restrictions.
