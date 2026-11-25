#!/usr/bin/env python3
"""Explicit deletion contract on a disposable CI database only."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "http://127.0.0.1:" + os.environ.get("WEB_PORT", "4173") + "/api/v1"


def send(url: str, token: str, *, method: str = "GET", payload: bytes | None = None,
         headers: dict[str, str] | None = None):
    return urlopen(Request(
        BASE + url, data=payload, method=method,
        headers={"Authorization": "Bearer " + token, **(headers or {})},
    ), timeout=15)


def expect_http(code: int, url: str, token: str, *, headers: dict[str, str] | None = None) -> None:
    try:
        with send(url, token, method="DELETE", headers=headers):
            raise AssertionError(f"Expected HTTP {code}")
    except HTTPError as error:
        assert error.code == code, f"Expected HTTP {code}, got {error.code}"


def main() -> int:
    if sys.argv[1:] != ["--disposable"]:
        print("Usage: python3 scripts/object_deletion_smoke.py --disposable", file=sys.stderr)
        print("This writes and deletes an ephemeral object; never run against important data.", file=sys.stderr)
        return 2

    admin, reader = os.environ["GC_ADMIN_TOKEN"], os.environ["GC_READ_TOKEN"]
    content = b"temporary-ci-object-deletion-test"
    checksum = hashlib.sha256(content).hexdigest()
    with send("/objects?filename=ci-delete-test.txt", admin, method="POST", payload=content,
              headers={"Content-Type": "text/plain"}) as response:
        assert response.status == 201
        object_id = json.load(response)["object"]["id"]
    path = "/objects/" + object_id
    valid_headers = {
        "X-GC-Confirm-Delete": "permanently-delete",
        "X-GC-Expected-SHA256": checksum,
    }
    expect_http(401, path, reader, headers=valid_headers)
    expect_http(428, path, admin)
    expect_http(404, path, admin, headers={**valid_headers, "X-GC-Expected-SHA256": "0" * 64})

    with send(path, admin, method="DELETE", headers=valid_headers) as response:
        assert response.status == 204
    try:
        with send(path, reader):
            raise AssertionError("Deleted object still readable")
    except HTTPError as error:
        assert error.code == 404

    with send("/audit/events?limit=25", admin) as response:
        audit = json.load(response)["events"]
    assert any(e["source_schema"] == "gc_storage" and e["source_table"] == "objects" and
               e["operation"] == "DELETE" for e in audit), "Missing metadata-only deletion audit"
    print("Disposable object deletion passed (admin two-step/checksum, reader denial, metadata-only audit).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
