#!/usr/bin/env python3
"""Restore a custom PostgreSQL archive into a temporary network-isolated container.

This is a non-production recovery drill. The program never connects to an
existing database endpoint, never maps a host port and always removes its
own ephemeral restore container.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

IMAGE = "postgres:17.12-alpine3.23"


def run(command: list[str], *, stdin=None, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(command, stdin=stdin, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path, help="Existing custom-format pg_dump archive")
    parser.add_argument("--apply", action="store_true", help="Launch a disposable isolated restore database")
    args = parser.parse_args()
    path = args.archive.expanduser().absolute()
    if not path.is_file() or path.is_symlink():
        print("Input must be an existing regular archive, not a symbolic link.", file=sys.stderr)
        return 2
    if not args.apply:
        print(f"DRY RUN: would restore {path.name} to a new disposable network-isolated container only.")
        return 0

    name = "gcdb-restore-" + secrets.token_hex(8)
    password = secrets.token_urlsafe(32)
    created = False
    try:
        started = run([
            "docker", "run", "--rm", "-d", "--network", "none", "--name", name,
            "-e", "POSTGRES_PASSWORD", IMAGE,
        ], env={**os.environ, "POSTGRES_PASSWORD": password})
        if started.returncode:
            raise RuntimeError("Could not launch isolated database")
        created = True
        # The official PostgreSQL entrypoint starts a temporary bootstrap server
        # before the final server. Do not restore into that short-lived process.
        ready = False
        consecutive_ready = 0
        for _ in range(40):
            if run(["docker", "exec", name, "pg_isready", "-U", "postgres"]).returncode == 0:
                consecutive_ready += 1
                if consecutive_ready >= 4:
                    ready = True
                    break
            else:
                consecutive_ready = 0
            time.sleep(1)
        if not ready:
            raise RuntimeError("Isolated database did not become ready")
        with path.open("rb") as archive:
            restored = run([
                "docker", "exec", "-i", name, "pg_restore", "--username", "postgres",
                "--dbname", "postgres", "--no-owner", "--no-acl", "--exit-on-error",
            ], stdin=archive)
        if restored.returncode:
            raise RuntimeError("Restoration failed")
        # The developer preview's seeded catalog is an explicit integrity probe.
        probe = run([
            "docker", "exec", name, "psql", "-U", "postgres", "-d", "postgres",
            "-X", "-v", "ON_ERROR_STOP=1", "-c", "SELECT count(*) FROM app.catalog",
        ])
        if probe.returncode:
            raise RuntimeError("Post-restore schema integrity probe failed")
        print(f"Restore verified in disposable, disconnected PostgreSQL {IMAGE}; container removed.")
        return 0
    except (OSError, RuntimeError) as exc:
        # Only internally authored RuntimeError strings are displayed, never raw
        # Docker output, SQL content, credentials or exception path details.
        detail = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        print(f"Restore verification failed: {detail}; source database untouched.", file=sys.stderr)
        return 1
    finally:
        if created:
            run(["docker", "rm", "-f", name])


if __name__ == "__main__":
    raise SystemExit(main())
