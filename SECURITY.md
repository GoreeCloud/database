# Security policy — GoreeCloud Database

**Development preview. Do not deploy on an Internet-facing host.** No production SLA, audit or vulnerability-response guarantee is established.

- Report suspected vulnerabilities privately using GitHub's private vulnerability-reporting feature if enabled, rather than publishing exploit steps or secrets.
- Generated `.env` must remain local and uncommitted. `scripts/init_env.py` never prints secrets and refuses to overwrite them.
- Database, API and REST services are isolated on a private data network; only the nginx gateway is published on localhost. REST is available via /rest/ on that gateway. External access requires a separately evaluated, identity-aware TLS proxy.
- Backend authorization is a single shared token, not fine-grained identity. Rotate by coordinated env and service updates; DB roles require separate SQL password rotation.
- Use a non-superuser `gc_api` for the management API. SQL identifiers are allowlisted and quoted; values are parameterized.
- Android refuses plaintext HTTP. No persistence of administrator tokens is implemented.
- This service does not yet offer tested disaster recovery, RLS tenant separation, auditing, rate limiting, or multi-factor identity.
