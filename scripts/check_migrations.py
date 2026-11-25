#!/usr/bin/env python3
"""Read-only integrity and ordering checks for SQL migration source files.

This verifies source consistency, NOT applied database revisions or production
approval. It never connects to PostgreSQL, launches containers, or runs SQL.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILENAME = re.compile(r"^[0-9]{3}-[a-z0-9]+(?:-[a-z0-9]+)*\.sql$")
CALL = re.compile(r"/migrations/([0-9]{3}-[a-z0-9-]+\.sql)")
LOCKFILE = Path("infra/postgres/migrations/manifest.json")


class MigrationIntegrityError(ValueError):
    pass


def verified_manifest(root: Path) -> list[dict[str, str]]:
    directory = root / "infra/postgres/migrations"
    bootstrap = root / "infra/postgres/init/001-bootstrap.sh"
    lockfile = root / LOCKFILE
    if not directory.is_dir() or not bootstrap.is_file() or not lockfile.is_file():
        raise MigrationIntegrityError("Migration directory, bootstrap, or integrity manifest missing")

    paths = sorted(directory.glob("*.sql"))
    if not paths:
        raise MigrationIntegrityError("No SQL migrations found")
    names = [p.name for p in paths]
    if any(not FILENAME.fullmatch(name) for name in names):
        raise MigrationIntegrityError("Unsupported SQL migration filename")
    numbers = [int(name[:3]) for name in names]
    if numbers != list(range(2, 2 + len(names))):
        raise MigrationIntegrityError("SQL migration sequence must start at 002 without gaps or duplicates")

    found = CALL.findall(bootstrap.read_text(encoding="utf-8"))
    if found != names:
        raise MigrationIntegrityError("Fresh-volume bootstrap does not invoke every migration exactly once, in order")

    try:
        lock = json.loads(lockfile.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise MigrationIntegrityError("Invalid migration integrity manifest") from exc
    if not isinstance(lock, dict) or lock.get("format") != "goreecloud-database-migrations-v1":
        raise MigrationIntegrityError("Unknown migration manifest format")
    approved = lock.get("sha256")
    if not isinstance(approved, dict) or set(approved) != set(names):
        raise MigrationIntegrityError("Manifest must cover exactly the present migrations")

    results = []
    for path in paths:
        data = path.read_bytes()
        if not data or len(data) > 131072:
            raise MigrationIntegrityError("Migration SQL is empty or exceeds review size bound")
        actual = hashlib.sha256(data).hexdigest()
        if approved[path.name] != actual:
            raise MigrationIntegrityError(f"Migration checksum changed: {path.name}")
        results.append({"file": path.name, "sha256": actual})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print validated source-only migration inventory")
    args = parser.parse_args()
    try:
        inventory = verified_manifest(ROOT)
    except MigrationIntegrityError as exc:
        print(f"Migration source integrity: FAIL — {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"scope": "source-only", "applied_database_state": "unverified",
                          "migrations": inventory}, indent=2))
    else:
        print(f"Migration source integrity: OK ({len(inventory)} immutable-reviewed SQL files, ordered first-boot calls).")
        print("Applied database revisions: NOT CHECKED. No migration was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
