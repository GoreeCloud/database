# Backup and isolated recovery verification

**Development preview; not a certified production backup system.**

This repository provides two guarded CLIs. They support PostgreSQL logical database backup and a disposable restore drill. They do not replace encrypted off-host backups, PITR/WAL retention, tested RPO/RTO, disaster recovery, secrets escrow, or regulatory retention policies.

## Preconditions

- Use an authorized nonproduction Docker Compose host running the exact intended `GoreeCloud/database` stack.
- Confirm free space, database size, owner permissions, server health, image provenance and retention policy.
- A backup may contain personally sensitive records; use a protected destination (e.g. an approved encrypted volume). Never upload database dumps to this public repository or an unapproved cloud.
- Avoid creating a backup while schema migrations or dangerous operations are in progress.
- These commands do not modify the current database, but reading it adds I/O load.

## Create an archive

```sh
python3 scripts/backup.py --output /secure/backups/database-YYYYMMDD.backup
python3 scripts/backup.py --output /secure/backups/database-YYYYMMDD.backup --apply
```

The path must not already exist; the archive is created with `0600` permissions and incomplete files are removed on failure. `pg_dump` uses PostgreSQL's custom archive format (`-Fc`) with owners/ACLs omitted. On success, the archive table-of-contents is checked and the tool prints its size and SHA256, but **that listing is not proof of successful recovery**.

## Restore test to a new isolated container

```sh
python3 scripts/restore_check.py --archive /secure/backups/database-YYYYMMDD.backup
python3 scripts/restore_check.py --archive /secure/backups/database-YYYYMMDD.backup --apply
```

With `--apply`, this creates an ephemeral PostgreSQL 17.12 container using `--network none` and no published ports, waits for it to become ready, restores the archive, validates `app.catalog` and removes the temporary container even if the drill fails. It **never writes to the running source database**, and is limited to the repository's own `app.catalog` preview schema. It is not a generalized multi-database restore migration tool.

The temporary test container uses a randomly generated initialization password; its network is disabled. The Docker daemon and host operators remain trusted security boundaries.

## Gaps before production

- Export database global roles, extensions and configurations as applicable; the current custom dump excludes role definitions and ACLs.
- Encrypt backups with approved key custody; validate off-host replication and retention.
- Validate PITR via base backups and archived WAL chain on a separated recovery target.
- Test representative data volume, concurrent writes, resource limits, restore ordering, safe migrations and actual measured RPO/RTO.
- Pin immutable image digests and verify supply-chain provenance, licenses and privileges.
- Schedule recovery drills only after an explicitly configured and verified automation is authorized.
