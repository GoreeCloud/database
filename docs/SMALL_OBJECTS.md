# Bounded small-object storage — development preview

This intentionally provides a tiny, self-hosted attachment API backed by PostgreSQL `bytea`, not a production S3-compatible object store. It is limited to **1 MiB per object**, a restricted MIME type set and a dedicated nonpublic `gc_storage` schema.

## Security and data model

- POST `/api/v1/objects?filename=example.txt`: administrator bearer token, raw request body, maximum 1 MiB enforced while streaming, no arbitrary SQL.
- GET `/api/v1/objects`: administrator or viewer bearer token, paginated metadata only.
- GET `/api/v1/objects/{uuid}`: administrator or viewer bearer token, checksum-verified binary download with attachment-only disposition and `nosniff`.
- `gc_storage.objects` is outside the generic `app` schema and the public PostgREST namespace; grant sets permit `gc_api` SELECT/INSERT and `gc_reader` SELECT only.
- The service validates ASCII basenames, media types, SHA256, exact byte counts and UUIDs. No public download URL, multipart parser, host file mount, path traversal or automatic egress is introduced.

**Important limits:** The viewer token can read **every** object. A fixed global capacity bound of 512 objects / 128 MiB is enforced with a database trigger (see [quota runbook](OBJECT_QUOTA.md)), but there are no individual users, ownership, per-tenant quotas or ACLs, access expiry, malware scanning, retention settings, deletion endpoint, CDN or S3 compatibility. Do not store sensitive or irreplaceable files in this development preview.

## First install / existing volumes

First-boot PostgreSQL initialization runs `004-small-objects.sql` followed by `005-object-quota.sql`. On an existing volume, **first verify an independent recoverable backup** and review the SQL. Then explicitly apply:

```sh
sh scripts/apply_small_object_migration.sh --apply
```

The script only applies additive schema and table grants; it cannot replace an established production migration mechanism. Never erase existing volumes to make the migration appear to work.

## Direction

Use this preview to verify the client/API shape and database metadata contract. Migrate large-scale private storage to a reviewed S3-compatible backend such as SeaweedFS only after immutable image pinning, authentication/bucket ACLs, integrity and recovery testing, virus-scan/retention enforcement and GoreeCloud Identity per-user scope acceptance. See [GitHub issue #7](https://github.com/GoreeCloud/database/issues/7).
