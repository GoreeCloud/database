# GoreeCloud MIPS integration state

This document records **interfaces and future work**, not integrated operating systems.

| System | Current behavior | Needed for verified integration |
| --- | --- | --- |
| GoreeCloud UI | Web CSS uses verified alpha semantic tokens; Android matches the verified dark semantic palette | Consume versioned design assets and pass visual/a11y QA |
| GoreeCloud Mesh | API contract defined at `/api/v1` with bearer authorization | Review Mesh discovery, identity propagation, event schema and signed service contract |
| GoreeCloud Identity | Shared admin/viewer tokens plus opt-in short-lived RS256 OIDC verification; a separate `gc_personal.notes` table uses signed-subject RLS and requires explicit note-write scope, but **no** verified platform-wide Identity integration | Approved live Identity integration, PKCE login, project roles, per-person RLS across real products, revocation and session lifecycle |
| GoreeShield | Local-only bindings and no analytics by default | Retention settings, auditable consent, redaction and portability |
| Wardveil | Secret hygiene, restricted network/configuration defaults and a single-process administrator mutation burst limit; no verified Wardveil service integration | Approved identity-scoped throttling, vulnerability scanning, incident events, audit log, backups and monitoring |

Never share service access tokens through public GitHub issues, Android bundles, front-end build variables or browser local storage. Inter-product requests require explicit policy and identity acceptance.
