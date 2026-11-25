# Signed-subject personal-note write throttling — development preview

This repository applies a deliberately small **12 admitted mutation attempts per 60-second sliding window per signature-verified OIDC subject**. Both `POST /api/v1/me/notes` and `DELETE /api/v1/me/notes/{uuid}` use the same quota after required read+write scopes are verified. Invalid/missing OIDC signatures or scopes are denied with HTTP 401 **before** entering the quota.

Requests exceeding the quota receive **HTTP 429** with a bounded `Retry-After` response header. Valid personal-note reads are not throttled by this component; nor are shared administrator operations, which continue to use their separately scoped 30/minute bucket.

## Privacy and capacity

- The limiter retains **no plaintext OIDC subject IDs, account emails, bearer tokens, IP addresses, request payloads or note content**. It computes an HMAC-SHA-256 pseudonymous identity using a unique random per-process secret that is never logged or persisted.
- At most **512 distinct per-process subject buckets** are tracked at once, each capped at 12 time stamps. Expired buckets are reclaimed when a new subject would exceed capacity; if no bucket can be reclaimed, the new subject receives HTTP 429 and a `Retry-After` instead of increasing memory without bound.
- Access is serialized by a thread lock; timings use monotonic seconds. The limiter counts admitted attempts even if a subsequent body validation or database operation fails, to bound request resource use. A new process starts with empty counters and a new HMAC key.
- The HMAC pseudonymized identity is still security-sensitive transient data; this is not an identity directory, retention database, risk profiler, actor audit or GoreeShield user-consent mechanism.
- There is no query-string token, global cookie, client-side cache or browser telemetry added by this change.

## Tests and limitations

Unit tests cover separate subjects, rejected unscoped tokens, concurrent calls, cap overflow/expiry, malformed subject values, time-window expiration and HTTP 429 with `Retry-After` while reads remain available. Repository CI's API job runs these tests with ephemeral local signed RSA fixtures; no user identities or live OIDC provider are involved.

**This is not production abuse prevention.** Limits are local to each API worker and process, not coordinated through Redis/PostgreSQL or a trusted edge gateway. A restart resets counters, distributed replicas multiply the allowed rate, and a global credential thief still has other routes. Production integration must add approved per-identity and per-device controls, Wardveil event handling and alerts, server-side consent/retention enforcement, and upstream network-level denial.
