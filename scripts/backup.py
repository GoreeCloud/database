#!/usr/bin/env python3
"""Create a non-overwriting, permission-restricted PostgreSQL custom archive.

Uses the authorized Docker Compose postgres service. The script does not
modify the running database and never prints secret material or dump rows.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New destination archive path (must not exist)")
    parser.add_argument("--apply", action="store_true", help="Actually capture a backup")
    args = parser.parse_args()

    destination = args.output.expanduser().absolute()
    if not args.apply:
        print(f"DRY RUN: would create an exclusive 0600 custom dump at {destination}")
        return 0
    if not destination.parent.is_dir():
        print("Output parent directory must already exist.", file=sys.stderr)
        return 2
    if destination.exists() or destination.is_symlink():
        print("Destination exists or is a symbolic link: refusing overwrite.", file=sys.stderr)
        return 2
    os.umask(0o077)
    created = False
    cmd = [
        "docker", "compose", "exec", "-T", "postgres", "sh", "-c",
        'exec pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom --no-owner --no-acl',
    ]
    try:
        with destination.open("xb") as handle:
            created = True
            result = subprocess.run(cmd, stdout=handle, stderr=subprocess.DEVNULL, check=False)
        if result.returncode:
            raise RuntimeError("pg_dump returned a failure")
        with destination.open("rb") as archive:
            verified = subprocess.run(
                ["docker", "compose", "exec", "-T", "postgres", "pg_restore", "--list"],
                stdin=archive, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
        if verified.returncode:
            raise RuntimeError("pg_restore archive listing validation failed")
        if destination.stat().st_size < 100:
            raise RuntimeError("Archive unexpectedly small")
    except (OSError, RuntimeError) as exc:
        if created:
            destination.unlink(missing_ok=True)
        print(f"Backup failed ({type(exc).__name__}); output is not trustworthy.", file=sys.stderr)
        return 1
    with destination.open("rb") as archive:
        digest = hashlib.file_digest(archive, "sha256").hexdigest()
    print(f"Backup written: {destination.name}")
    print(f"Bytes: {destination.stat().st_size}")
    print(f"SHA256: {digest}")
    print("Archive list validated; complete isolated restore verification remains separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
