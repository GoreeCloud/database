#!/usr/bin/env python3
"""Exercise the authenticated catalog SSE feed and a disposable test insert."""
from __future__ import annotations

import json
import os
import urllib.request
from uuid import uuid4


def main() -> int:
    admin = os.environ["GC_ADMIN_TOKEN"]
    viewer = os.environ["GC_READ_TOKEN"]
    base = "http://127.0.0.1:" + os.environ.get("WEB_PORT", "4173") + "/api"
    request = urllib.request.Request(
        base + "/v1/events/catalog",
        headers={"Authorization": "Bearer " + viewer, "Accept": "text/event-stream"},
    )
    with urllib.request.urlopen(request, timeout=15) as feed:
        first = feed.readline().decode("utf-8").strip()
        second = feed.readline().decode("utf-8").strip()
        assert first == "retry: 3000" and second == "event: ready", "SSE did not initialize"
        # Trigger after listener has registered; no credentials enter URLs or logs.
        slug = "ci-event-" + uuid4().hex[:16]
        body = json.dumps({"slug": slug, "description": "Disposable CI catalog event"}).encode("utf-8")
        insert = urllib.request.Request(
            base + "/v1/tables/app/catalog/rows", data=body, method="POST",
            headers={"Authorization": "Bearer " + admin, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(insert, timeout=15) as response:
            assert response.status == 201
        # Stream may contain empty and comment lines. Only accept strict event+data.
        got_event = False
        for _ in range(16):
            line = feed.readline().decode("utf-8").strip()
            if line == "event: catalog":
                data_line = feed.readline().decode("utf-8").strip()
                if data_line.startswith("data: "):
                    event = json.loads(data_line[6:])
                    got_event = event.get("schema") == "app" and event.get("table") == "catalog" and event.get("operation") == "INSERT"
                    if got_event:
                        break
        assert got_event, "No valid catalog event received after committed INSERT"
    print("Authenticated SSE catalog-insert smoke passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
