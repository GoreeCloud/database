# Opt-in OIDC read-only token verification — preview

**Status:** an API authorization adapter, not a complete GoreeCloud Identity integration. This does **not** create user accounts, handle login redirects, refresh tokens, revoke individual sessions, implement tenant isolation or PostgreSQL row-level security.

## Purpose

The development API retains its existing random shared administrator and viewer tokens. Operators may additionally configure a trusted OpenID Connect issuer and accept short-lived **asymmetrically signed access tokens for READ ONLY**. A verified token maps to the same shared `reader` capability, never `admin`. Every reader can still read every accessible `app` table, export CSV, read objects and receive permitted catalog metadata events. **Do not expose personal or family data on that basis.**

For a verified trusted provider, set:

- `GC_OIDC_ISSUER`: exact HTTPS issuer claim, e.g., `https://identity.example.org/realms/goreecloud`.
- `GC_OIDC_AUDIENCE`: dedicated API audience; the token must carry one exact string-valued audience.
- Exactly one trusted key source:
  - `GC_OIDC_JWKS_JSON`: trusted **public-only** RSA JWKS content captured and reviewed by the operator; supported even inside the default egress-blocked private Docker network. Review provenance, key rotation, retention and configuration exposure. **Never** put an RSA private key in this value.
  - `GC_OIDC_JWKS_URL`: trusted HTTPS JWKS endpoint under the exact issuer's hostname, port, and URL path. This mode requires separately reviewed network reachability. **The default `data` Docker network is internal and does not provide Internet egress**; merely setting a public URL does not make it reachable.

All other OIDC settings empty means **disabled**. Any partial/mismatched or malformed key configuration fails at process startup, not an implicit insecure fallback.

## Verification policy

- Only **RS256** JWTs signed by a trusted RSA public key of at least 2048 bits are accepted. `alg`, `jku` and similar untrusted JWT header URLs never configure key sources; a header `kid` only selects an operator-approved key.
- Checks include exact issuer, exact dedicated audience, nonempty subject, `iat`, `exp`, signature, expiry, and an explicit `goreecloud.database.read` claim in the whitespace-delimited OAuth `scope` field.
- Maximum accepted token lifetime: **one hour**. A 15-second leeway permits modest clock skew; larger issuer drift is not supported.
- Public JWKS JSON has a size/key-count cap, rejects duplicate kids, non-RSA keys, non-RS256 algorithms, weak keys and any private key fields. URL mode is same-origin and path-scoped; PyJWT version is constrained to a patched minimum.
- No raw access token, personal subject or other user claim is recorded in logs, response payloads or persistent session storage. Bad tokens produce generic authentication failures. Outbound key fetches use a 4-second timeout and a short-lived bounded cache.
- A valid OIDC token does **not** permit `POST` uploads/inserts or administrative operations. Existing shared administrator credentials remain independently protected.

## Operating guidance

When a trusted key is rotated, refresh the configured public JWKS or allow the trusted URL client to refresh. A static JWKS configuration requires an explicit approved config update and API service restart; its cached key set is not an automatic revocation mechanism. Revoke the actual account/token at the identity provider. For immediately removing an accepted static signing key, remove it from configured JWKS and restart the API. Check clocks and TLS trust before connecting clients.

Existing React and Android clients accept a bearer token in memory after manual entry; **they do not yet implement browser/mobile authorization-code + PKCE login**. External OIDC compatibility must be separately tested against the chosen real issuer, mobile TLS, and a deployment-specific network policy. Do not expose this developer stack directly to the Internet.

### Verification

The repository tests RSA cryptographic signature verification with ephemeral test keys, wrong signatures, unsupported algorithms, malicious/missing claims, weak/private JWKS entries, and rejection of all OIDC writes. Test fixtures do not call an actual provider or network; a passing unit suite is **not** live SSO certification.

Reference: [PyJWT API](https://pyjwt.readthedocs.io/en/latest/api.html), [PyJWT usage](https://pyjwt.readthedocs.io/en/latest/usage.html) and [OWASP JWT cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_Cheat_Sheet.html).

## Still outstanding

- GoreeCloud Identity provider discovery/consent, authorization-code + PKCE, session lifecycle and explicit sign-out.
- Verified per-user claims, least-privilege table policies, PostgreSQL RLS, object ownership ACL and tenant boundaries.
- Wardveil authentication/audit events, user-specific rate limiting and threat telemetry.
- GoreeShield consent, data minimization, export and retention policies; GoreeCloud Mesh trusted service identity propagation.

Track the production identity/RLS implementation separately in [issue #6](https://github.com/GoreeCloud/database/issues/6).
