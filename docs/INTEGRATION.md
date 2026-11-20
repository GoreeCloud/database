# GoreeCloud MIPS integration state

This document records **interfaces and future work**, not integrated operating systems.

| System | Current behavior | Needed for verified integration |
| --- | --- | --- |
| GoreeCloud UI | Web CSS uses verified alpha semantic tokens; Android matches the verified dark semantic palette | Consume versioned design assets and pass visual/a11y QA |
| GoreeCloud Mesh | API contract defined at `/api/v1` with bearer authorization | Review Mesh discovery, identity propagation, event schema and signed service contract |
| GoreeCloud Identity | Single manually provisioned admin bearer secret only | OIDC-based user login, project roles, token scopes, revocation and short-lived access |
| GoreeShield | Local-only bindings and no analytics by default | Retention settings, auditable consent, redaction and portability |
| Wardveil | Secret hygiene and restricted network/configuration defaults | Approved vulnerability scanning, incident events, audit log, backups and monitoring |

Never share service access tokens through public GitHub issues, Android bundles, front-end build variables or browser local storage. Inter-product requests require explicit policy and identity acceptance.
