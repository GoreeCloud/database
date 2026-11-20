#!/usr/bin/env python3
"""Fast static sanity check of the source tree without network or services."""
from pathlib import Path
import re

root = Path(__file__).resolve().parent.parent
assert not (root / ".env").is_file(), "Do not execute repository verification with a real secrets file in repo root"
expected = [
    "README.md", "LICENSE", "SECURITY.md", ".github/workflows/ci.yml",
    "apps/api/gc_database/main.py", "apps/web/src/App.tsx",
    "apps/android/app/src/main/java/com/goreecloud/database/MainActivity.kt",
    "infra/postgres/init/001-bootstrap.sh",
]
for path in expected:
    assert (root / path).is_file(), f"Missing {path}"
manifest = (root / "apps/android/app/src/main/AndroidManifest.xml").read_text()
assert 'android:usesCleartextTraffic="false"' in manifest
compose = (root / "compose.yaml").read_text()
assert "127.0.0.1:" in compose
assert not re.search(r"^\s+-\s+\"?(?:5432):5432", compose, re.M)
print("GoreeCloud Database static contract: OK")
