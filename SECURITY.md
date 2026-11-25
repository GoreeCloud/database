# Security policy — GoreeCloud Database

**Development preview. Do not deploy on an Internet-facing host.** No production SLA, audit or vulnerability-response guarantee is established.

- Report suspected vulnerabilities privately using GitHub's private vulnerability-reporting feature if enabled, rather than publishing exploit steps or secrets.
- Generated `.env` must remain local and uncommitted. `scripts/init_env.py` never prints secrets and refuses to overwrite them.
- Database, API and REST services are isolated on a private data network; only the nginx gateway is published on localhost. REST is available via /rest/ on that gateway. External access requires a separately evaluated, identity-aware TLS proxy.
- Backend authorization uses two **independent shared** bearer tokens: admin (read/write) and viewer (read-only). These are not personal user identities or per-project scopes. Reads use a separate PostgreSQL role granted SELECT only. Rotate tokens by coordinated env/service updates; database-role passwords require separate SQL rotation.
- Use a non-superuser `gc_api` for the management API. SQL identifiers are allowlisted and quoted; values are parameterized.
- Android refuses plaintext HTTP. No persistence of administrator tokens is implemented.
- This service does not yet offer tested disaster recovery, RLS tenant separation, auditing, rate limiting, or multi-factor identity. Read-only tokens can read the entire exposed `app` schema; never interpret them as per-user scopes. Catalog SSE notifications are metadata-only and lossy; authorization is a shared preview token, not tenant-scoped.
