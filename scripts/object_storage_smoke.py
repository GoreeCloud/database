#!/usr/bin/env python3
"""Verify the bounded private-schema object API on disposable CI stack only."""
from __future__ import annotations

import hashlib
import json
import os
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:" + os.environ.get("WEB_PORT", "4173") + "/api/v1/objects"


def request(url: str, secret: str, *, method: str = "GET", data: bytes | None = None, media: str = "application/octet-stream"):
    headers = {"Authorization": "Bearer " + secret, "Content-Type": media}
    return urlopen(Request(url, headers=headers, method=method, data=data), timeout=15)


def main() -> int:
    admin, viewer = os.environ["GC_ADMIN_TOKEN"], os.environ["GC_READ_TOKEN"]
    content = b"goreecloud private object store smoke\n"
    with request(BASE + "?filename=smoke.txt", admin, method="POST", data=content, media="text/plain") as response:
        assert response.status == 201
        result = json.load(response)
    object_id = result["object"]["id"]
    assert result["object"]["sha256"] == hashlib.sha256(content).hexdigest()
    with request(BASE, viewer) as response:
        listing = json.load(response)
        assert any(item["id"] == object_id for item in listing["objects"])
    with request(BASE + "/" + object_id, viewer) as response:
        assert response.status == 200
        assert response.headers["Content-Disposition"].startswith("attachment; filename=")
        assert response.read() == content
    print("Private-schema object store smoke passed (admin write, viewer read, checksum).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
