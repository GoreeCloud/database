#!/usr/bin/env python3
"""Append private, random S3-preview credentials to an existing generated .env.

Explicit --apply required. No credentials are printed or overwritten.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import secrets
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
KEYS = ("GC_S3_ACCESS_KEY", "GC_S3_SECRET_KEY", "GC_S3_ADMIN_PASSWORD")


def add_preview_credentials(path: Path) -> None:
    if path.is_symlink() or not path.exists():
        raise ValueError("Expected a preexisting, regular private .env; run init_env.py first")
    descriptor = os.open(path, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        record = os.fstat(descriptor)
        if not stat.S_ISREG(record.st_mode) or (stat.S_IMODE(record.st_mode) & 0o077):
            raise ValueError("Refusing unsafe .env file type or permissions (must be private mode 0600)")
        if record.st_size > 131072:
            raise ValueError("Unexpectedly large .env; refusing partial-read append")
        existing = os.read(descriptor, record.st_size).decode("utf-8")
        if not existing.startswith("# Generated locally.") or not existing.endswith("\n"):
            raise ValueError("Unexpected .env provenance or newline; refuses to modify")
        if any(line.startswith(("GC_S3_", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"))
               for line in existing.splitlines()):
            raise ValueError("S3 credentials or settings already exist; refusing overwrite or duplication")
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        access = "".join(secrets.choice(alphabet) for _ in range(24))
        additions = [
            "GC_S3_ACCESS_KEY=" + access,
            "GC_S3_SECRET_KEY=" + secrets.token_urlsafe(48),
            "GC_S3_ADMIN_PASSWORD=" + secrets.token_urlsafe(48),
            "GC_S3_PORT=8333",
        ]
        os.lseek(descriptor, 0, os.SEEK_END)
        pending = memoryview(("\n".join(additions) + "\n").encode("utf-8"))
        while pending:
            count = os.write(descriptor, pending)
            if count <= 0:
                raise OSError("Unable to append private preview credentials")
            pending = pending[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Append once to the existing private .env")
    options = parser.parse_args()
    if not options.apply:
        parser.print_usage()
        print("Explicit --apply required; no credentials were generated.")
        return 2
    try:
        add_preview_credentials(ENV)
    except (OSError, UnicodeError, ValueError) as error:
        print("S3 preview credentials NOT created: " + str(error))
        return 1
    print("S3 preview credentials appended to existing private .env (mode unchanged).")
    print("Credentials were not printed. Review local network/retention and backup policy first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
