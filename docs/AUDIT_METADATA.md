# Metadata-only change trail — development preview

The `gc_audit` PostgreSQL schema now records a deliberately minimal append-only record for `INSERT`, `UPDATE`, and `DELETE` events on **`app.catalog` and `gc_storage.objects` only**.

A row records a generated event ID, source schema, source table, operation, and PostgreSQL timestamp. **It does not record row content, row IDs, object identifiers or bytes, tokens, IP addresses, external identity subjects, JWT claims, or user profiles.**

## Security design

- The audit schema is outside the anonymous PostgREST `app` exposure. The separate `gc_reader` role has no access. The management role `gc_api` receives SELECT only.
- A PostgreSQL `SECURITY DEFINER` trigger function with a fixed `pg_catalog` search path inserts server-chosen metadata. PUBLIC execute privileges are revoked; no application or viewer SQL can set the event fields.
- The authenticated `GET /api/v1/audit/events?limit=25&offset=0` route permits the **shared administrator secret only**. It runs a `READ ONLY` transaction and returns up to 100 metadata records, not any payloads.
- The trigger captures changes even when the allowed table is modified outside the FastAPI route, but this is **not an exhaustive database audit**. It does not capture changes to other `app` tables, SELECTs, failed transactions, schema changes, identity events or the identity of the actor.
- The trail is ordinary PostgreSQL data, **not tamper-evident or immutable against DB superusers**. A database owner can alter/delete it. It must not be described as independent security telemetry or complete Wardveil integration.

## First boot and existing volumes

Fresh PostgreSQL volumes apply `006-audit-metadata.sql` after object quota initialization. For an existing, independently backed-up volume, review the SQL and deliberately run:

```sh
sh scripts/apply_audit_migration.sh
# Only after verifying target, compatible roles, backups and change authority:
sh scripts/apply_audit_migration.sh --apply
```

Migration is additive and idempotently reinstalls the two triggers, without deleting records. The SQL creates an index for recent-event reads; on busy existing tables, trigger installation may acquire locks, so schedule a maintenance window where relevant.

## Disposable CI

CI executes `scripts/audit_smoke.py` after catalog SSE/object upload smoke; it verifies both metadata event kinds, rejects the read-only token and checks the response exposes only approved fields. Unit tests verify endpoint authorization, response bounds and no caller-controlled SQL parameters.

## Privacy and remaining acceptance

**There is no enforced event retention, pruning, per-user actor attribution, tamper evidence, signed logs, detection/alerts, or managed backup.** This preview is not appropriate for regulated logging, sensitive personal datasets, or a public service. Define a GoreeShield retention policy, then implement separately reviewed bounded retention and Wardveil monitoring before production. Manual deletions and truncations are deliberately not exposed by this API.
