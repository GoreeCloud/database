#!/usr/bin/env python3
"""Exercise the shared-admin mutation throttle on a disposable CI stack only."""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def main() -> int:
    if sys.argv[1:] != ["--disposable"]:
        print("Usage: python3 scripts/admin_write_smoke.py --disposable", file=sys.stderr)
        print("This intentionally writes disposable catalog rows. Never run on real data.", file=sys.stderr)
        return 2
    base = "http://127.0.0.1:" + os.environ.get("WEB_PORT", "4173") + "/api"
    admin = os.environ["GC_ADMIN_TOKEN"]
    reader = os.environ["GC_READ_TOKEN"]
    successes = 0
    blocked = 0
    for number in range(36):
        slug = "ci-throttle-" + uuid4().hex[:20]
        payload = json.dumps({"slug": slug, "description": "Disposable rate-limit test"}).encode()
        req = Request(
            base + "/v1/tables/app/catalog/rows", data=payload, method="POST",
            headers={"Authorization": "Bearer " + admin, "Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=12) as response:
                assert response.status == 201
                successes += 1
        except HTTPError as exc:
            if exc.code != 429:
                raise
            assert 1 <= int(exc.headers.get("Retry-After", "0")) <= 60
            blocked += 1
            break
    assert successes >= 1 and blocked == 1, "Admin rate limit not enforced"
    with urlopen(Request(base + "/v1/tables",
                         headers={"Authorization": "Bearer " + reader}), timeout=12) as res:
        assert res.status == 200, "Read-only activity blocked by admin throttle"
    print("Admin write throttle passed: 429 after bounded writes; reader remains available")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
