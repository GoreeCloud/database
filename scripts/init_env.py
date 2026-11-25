#!/usr/bin/env python3
"""Create a local-only secrets file without printing any generated credentials."""
from pathlib import Path
from secrets import token_urlsafe
import os

ROOT = Path(__file__).resolve().parents[1]
target = ROOT / ".env"
if target.exists():
    raise SystemExit(".env already exists: refusing to overwrite credentials")
lines = [
    "# Generated locally. DO NOT COMMIT OR SHARE.",
    "POSTGRES_DB=goreecloud",
    "POSTGRES_USER=postgres",
]
for name in ("POSTGRES_PASSWORD", "GC_API_DB_PASSWORD", "GC_REST_DB_PASSWORD", "GC_READ_DB_PASSWORD", "GC_ADMIN_TOKEN", "GC_READ_TOKEN"):
    lines.append(f"{name}={token_urlsafe(48)}")
lines += ["WEB_PORT=4173"]
fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write("\n".join(lines) + "\n")
print("Created .env with private, unique secrets (file mode 0600).")
print("Use GC_ADMIN_TOKEN in your local web or Android console. Keep it private.")
