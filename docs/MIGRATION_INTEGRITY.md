# Ordered SQL migration source integrity — development guard

This repository maintains PostgreSQL migration SQL in `infra/postgres/migrations/`, with a first-install invocation sequence in `infra/postgres/init/001-bootstrap.sh`. An additional **read-only** source checker rejects accidental drift:

```sh
python3 scripts/check_migrations.py
python3 scripts/check_migrations.py --json
```

The checker enforces numbered, contiguous migration filenames beginning at `002`, exact matching bootstrap invocation order, no omissions or duplicates, and SHA-256 agreement with `infra/postgres/migrations/manifest.json`. CI runs it under the protected `config` job, and the unit suite exercises changed SQL, duplicate/omitted/reordered calls, unreviewed migrations, corrupt/missing manifest and empty files. The JSON output is machine-readable with `applied_database_state: unverified` and never contains credentials, data rows or user identities.

## Adding a migration

1. Confirm the existing PostgreSQL schema, grants, migration state and independently verified backups on the target; preserve data and comply with the governed SQL authoring and approval process.
2. Add a **new** numbered SQL file in the repo; **never silently edit** existing migration bytes. Include explicit safety, idempotence, role privilege and rollback considerations.
3. Add the matching `psql --file=/migrations/NNN-name.sql` invocation to the **end** of `infra/postgres/init/001-bootstrap.sh` in numeric order, so a fresh volume receives it.
4. Recalculate the SHA-256 entry for the new SQL file in `manifest.json` after source review. This must be an independently reviewed PR change—not an automatic acceptance of arbitrary SQL.
5. Add a guarded, explicit `--apply` existing-volume migration runbook and regression tests against a **disposable** PostgreSQL database, including rollback and role-restriction checks.
6. Validate the source checker and all protected CI jobs before merging. The checker is a *source consistency gate*; it is **not** evidence that an existing volume was migrated. Validate existing volumes separately using PostgreSQL catalog queries and owner-approved migration history.

**Risk:** SQL migrations may cause data loss, privilege changes, locks, or inaccessible backups. This checker never applies a migration, opens a connection, starts containers, or modifies the manifest; it only reads its existing files and prints source paths and checksums. A manifest SHA-256 is not a trusted signature, hardware attestation or supply-chain provenance. Malicious changes to both SQL and manifest remain possible until independently reviewed.

## Remaining controls

No approved automatic migration runner, persisted applied-version ledger, multi-project provisioning, versioned rollback framework, online DDL planner, migration approvals, or secrets/tenant configuration management exists yet. Do not conflate first-boot scripts with safe existing-volume migration orchestration.

Canonical CLI documentation must eventually be synchronized to `GoreeCloud/CLI Commands/GoreeCloud/Database.md` in the authorized Google Drive; [issue #14](https://github.com/GoreeCloud/database/issues/14) remains open because no approved raw Markdown Drive writer was verified.
