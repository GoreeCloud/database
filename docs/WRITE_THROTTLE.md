# Administrative write throttle — development preview

The FastAPI management API now enforces a deliberately small **30 successful administrator write attempts per 60-second sliding window**, shared across administrator operations. Requests are authenticated **before** entering the quota. A denied operation receives HTTP **429 Too Many Requests** and a `Retry-After` header.

## Properties

- The limiter uses a thread-safe in-memory deque protected by a lock and monotonic time.
- Both catalog row inserts and small-object uploads call the same existing `require_admin` dependency and consume the same bucket. Operations that later fail validation may still count because they consume application resources.
- Unauthenticated and read-only callers cannot fill the administrator write bucket. Read routes, schema inspection, CSV downloads, and viewer object listing are not subject to this write quota.
- No IP address, access token, user subject, request body or account identifier is stored or logged by the limiter.
- OIDC-scoped personal note INSERTs and confirmed owner DELETEs are **not** covered by the shared-administrator write throttle. Inserts have a database-enforced 100-notes-per-subject capacity limit, not an identity-scoped request rate limiter.
- The default of 30/min is fixed in source for this preview. Restarts reset it. Each API worker/process maintains a separate bucket. There is no Redis dependency.

## What this does NOT do

This is **not** a real distributed, per-user, per-IP or abuse-prevention solution. The admin token is still shared, so all administrators share one limit. This is not a replacement for an identity-aware reverse proxy, circuit breakers, network access controls, login throttling, body size limits, audit events, alerting or production rate limiting. The service must remain loopback-only pending full policy/Identity/Wardveil acceptance.

## Tests

Unit tests simulate monotonic time and concurrent operations, and confirm one shared quota across both mutation endpoints. GitHub disposable integration runs `python3 scripts/admin_write_smoke.py --disposable` **after backup/recovery smoke tests**; it inserts ephemeral catalog rows until the API returns HTTP 429 and verifies the read-only viewer remains functional. This script intentionally changes its target database and must not run on any important volume.

## Future

Adopt authorized identity-scoped quotas, a trusted client boundary, configurable limits, distributed coordination, metrics and Wardveil alerts only after the dedicated Identity and platform security acceptance. Do not treat a local 429 as user isolation.
