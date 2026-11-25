# GoreeCloud MIPS integration state

This document records **interfaces and future work**, not integrated operating systems.

| System | Current behavior | Needed for verified integration |
| --- | --- | --- |
| GoreeCloud UI | Web CSS uses verified alpha semantic tokens; Android matches the verified dark semantic palette | Consume versioned design assets and pass visual/a11y QA |
| GoreeCloud Mesh | API contract defined at `/api/v1` with bearer authorization | Review Mesh discovery, identity propagation, event schema and signed service contract |
| GoreeCloud Identity | Distinct generated shared admin/viewer tokens; opt-in RS256 OIDC short-lived, READ-ONLY JWT verification with an explicit audience and scope (not a platform integration or RLS) | Approved live Identity integration, PKCE login, project roles, per-person row policies, revocation and session lifecycle |
| GoreeShield | Local-only bindings and no analytics by default | Retention settings, auditable consent, redaction and portability |
| Wardveil | Secret hygiene, restricted network/configuration defaults, and a PostgreSQL metadata-only change trail for two development tables (not Wardveil integration or tamper-evident auditing) | Approved vulnerability scanning, identity-aware audit trail, incident events, log retention, backups and monitoring |

Never share service access tokens through public GitHub issues, Android bundles, front-end build variables or browser local storage. Inter-product requests require explicit policy and identity acceptance.
