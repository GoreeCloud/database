#!/usr/bin/env python3
"""Exercise metadata-only audit contracts on an independently disposable stack."""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> int:
    base = "http://127.0.0.1:" + os.environ.get("WEB_PORT", "4173") + "/api/v1/audit/events"
    admin = os.environ["GC_ADMIN_TOKEN"]
    viewer = os.environ["GC_READ_TOKEN"]
    with urlopen(Request(base, headers={"Authorization": "Bearer " + admin}), timeout=15) as response:
        assert response.status == 200
        body = json.load(response)
    events = body["events"]
    assert len(events) >= 2, "Expected catalog and object smoke writes to be audited"
    assert any(e["source_schema"] == "app" and e["source_table"] == "catalog" and e["operation"] == "INSERT" for e in events)
    assert any(e["source_schema"] == "gc_storage" and e["source_table"] == "objects" and e["operation"] == "INSERT" for e in events)
    assert all(set(e) == {"id", "source_schema", "source_table", "operation", "occurred_at"} for e in events)
    try:
        urlopen(Request(base, headers={"Authorization": "Bearer " + viewer}), timeout=15)
        raise AssertionError("Viewer was allowed to read audit metadata")
    except HTTPError as exc:
        assert exc.code == 401
    print("Metadata-only admin audit passed: writes recorded, reader denied, no payload fields.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
