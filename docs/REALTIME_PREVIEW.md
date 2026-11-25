# Catalog change stream — preview

The first realtime capability is an authenticated PostgreSQL LISTEN/NOTIFY feed over server-sent events (SSE). It is **not** a Supabase Realtime replacement, durable message queue, cross-tenant subscription service, or replayable change-data-capture log.

## Scope and security

- PostgreSQL trigger `app.gc_catalog_change_notice` publishes only `schema=app`, `table=catalog`, the operation type and the catalog's integer `id`. **No row contents, descriptions or secrets** are broadcast.
- SQL notifications are delivered **after commit** to currently connected listeners; offline listeners miss them. Clients should always re-fetch current rows after reconnect. No cursor, replay, tenant routing, resume or ordering guarantees exist.
- GET `/api/v1/events/catalog` requires the administrator or read-only bearer token. Listener connections use the SELECT-only PostgreSQL role and an eight-connection-per-worker limit. Only the localhost web gateway is exposed by default.
- nginx disables response buffering for the stream, and the API sends periodic heartbeat comments.
- The server validates and JSON-encodes every received payload before emitting SSE framing. Arbitrary `NOTIFY` inputs are not passed through.
- As with the rest of the preview, **never expose directly to the public Internet**; a trusted authenticated TLS gateway is required for remote access.

## Existing data volumes

First installation runs `003-catalog-events.sql` during database initialization. Existing database volumes require an independently verified backup, review of the migration, then:

```sh
sh scripts/apply_catalog_events_migration.sh --apply
```

It is idempotent but changes the trigger and function attached to `app.catalog`. Do not run during risky schema transitions. Migration verification requires a committed catalog INSERT and an already listening authenticated SSE client.

## Client contract

SSE sends `event: ready` on successful subscription; catalog changes arrive as `event: catalog` followed by a compact JSON `data:` line. Heartbeat comments do not carry data. The browser console may use the event to refresh the current catalog table. The Android preview remains manual-refresh only.

A future per-project realtime design requires user and project authorization, PostgreSQL RLS, scoped subscriptions, reconnection/resume mechanics, resource limits and durable event indexing where necessary.
