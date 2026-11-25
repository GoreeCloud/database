#!/usr/bin/env python3
"""Offline CI action commit-pin and reviewed lockfile integrity verification."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHA = re.compile(r"[0-9a-f]{40}\Z")
REPO = re.compile(r"[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\Z")
USES = re.compile(r"^\s*-\s*uses:\s*(\S+)(?:\s+#\s*(\S+))?\s*$", re.M)


class ActionPinError(ValueError):
    pass


def verify_actions(root: Path = ROOT) -> dict[str, int]:
    workflow = root / ".github/workflows/ci.yml"
    manifest = root / "infra/ci/actions-lock.json"
    if workflow.is_symlink() or manifest.is_symlink():
        raise ActionPinError("CI reference files must not be symlinks")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        content = workflow.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        raise ActionPinError("Missing or invalid GitHub Actions lockfile/workflow") from exc
    if not isinstance(data, dict) or set(data) != {"format", "actions"} or data["format"] != "gc-actions-locked-v1":
        raise ActionPinError("Unknown action lockfile format")
    locked = data["actions"]
    if not isinstance(locked, dict) or not 1 <= len(locked) <= 32:
        raise ActionPinError("Invalid action inventory")
    for name, details in locked.items():
        if not REPO.fullmatch(name) or not isinstance(details, dict) or set(details) != {"sha", "version"}:
            raise ActionPinError("Invalid action identity or fields")
        if not isinstance(details["sha"], str) or not SHA.fullmatch(details["sha"]):
            raise ActionPinError("Only exact 40-character commit digests allowed")
        if not isinstance(details["version"], str) or not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+", details["version"]):
            raise ActionPinError("Invalid documented upstream tag")
    matches = USES.findall(content)
    if not matches:
        raise ActionPinError("No GitHub Actions references present")
    observed: dict[str, int] = {}
    for value, comment in matches:
        if value.count("@") != 1:
            raise ActionPinError("Action must include exactly one immutable @sha")
        repo, digest = value.split("@")
        expected = locked.get(repo)
        if expected is None or digest != expected["sha"] or comment != expected["version"]:
            raise ActionPinError(f"Unreviewed action reference, digest or version comment for {repo}")
        observed[repo] = observed.get(repo, 0) + 1
    if set(observed) != set(locked):
        raise ActionPinError("Action inventory differs from locked source")
    return observed


def main() -> int:
    try:
        recorded = verify_actions()
    except ActionPinError as error:
        print("Pinned GitHub Actions source: FAIL — " + str(error))
        return 1
    print(f"Pinned GitHub Actions source: OK ({len(recorded)} fixed upstream actions, {sum(recorded.values())} references).")
    print("SHA values verified against upstream tags at authoring time; no live supply-chain or provenance proof.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
