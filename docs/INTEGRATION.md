# GoreeCloud MIPS integration state

This document records **interfaces and future work**, not integrated operating systems.

| System | Current behavior | Needed for verified integration |
| --- | --- | --- |
| GoreeCloud UI | Web CSS uses verified alpha semantic tokens; Android uses the verified dark semantic palette. Both clients have development-only OIDC personal-note views; no certified stable component integration | Consume versioned design assets and pass visual/a11y QA |
| GoreeCloud Mesh | API contract at `/api/v1`, plus a separate opt-in signed SeaweedFS S3 protocol sandbox; **not** Mesh discovery or a Database API storage integration | Review Mesh discovery, identity propagation, storage event/ACL schema and signed service contract |
| GoreeCloud Identity | Shared admin/viewer tokens plus opt-in short-lived RS256 OIDC verification; a separate `gc_personal.notes` table uses signed-subject RLS and requires explicit note-write scope, but **no** verified platform-wide Identity integration | Approved live Identity integration, PKCE login, project roles, per-person RLS across real products, revocation and session lifecycle |
| GoreeShield | Local-only bindings and no analytics by default | Retention settings, auditable consent, redaction and portability |
| Wardveil | Secret hygiene, restricted network/configuration defaults, single-process admin mutation throttle, and PostgreSQL metadata-only change trail for two development tables; **not** Wardveil integration or tamper-evident auditing | Approved identity-scoped throttling, vulnerability scanning, actor-aware audit, event retention, incident alerts, backups and monitoring |

Never share service access tokens through public GitHub issues, Android bundles, front-end build variables or browser local storage. Inter-product requests require explicit policy and identity acceptance.
