#!/usr/bin/env python3
"""Run hash-approved pure Wasm i32->i32 code without WASI, imports, or network."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = re.compile(r"[a-z][a-z0-9-]{0,32}\Z")
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
MAX_SOURCE = 8192
MAX_INPUT = 1_000_000
MAX_MEMORY = 8 * 1024 * 1024
MAX_FUEL = 100_000


class EdgeDenied(ValueError):
    pass


def approved_source(name: str, root: Path = ROOT) -> bytes:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise EdgeDenied("Unapproved module ID")
    manifest_path = root / "infra/edge/approved.json"
    directory = root / "infra/edge/modules"
    if manifest_path.is_symlink() or directory.is_symlink() or not manifest_path.is_file():
        raise EdgeDenied("Untrusted approval manifest location")
    try:
        if manifest_path.stat().st_size > 65536:
            raise EdgeDenied("Manifest exceeds size bound")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or set(manifest) != {"format", "modules"} or manifest["format"] != "gc-edge-approved-v1":
            raise EdgeDenied("Unknown approval manifest format")
        modules = manifest["modules"]
        if not isinstance(modules, dict) or not 1 <= len(modules) <= 32:
            raise EdgeDenied("Invalid approved module set")
        digest = modules.get(name)
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise EdgeDenied("Module ID not approved")
        candidate = directory / (name + ".wat")
        if candidate.is_symlink() or not candidate.is_file() or candidate.stat().st_size > MAX_SOURCE:
            raise EdgeDenied("Missing or oversized approved source")
        content = candidate.read_bytes()
        if not content or hashlib.sha256(content).hexdigest() != digest:
            raise EdgeDenied("Approved source checksum mismatch")
        return content
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, EdgeDenied):
            raise
        raise EdgeDenied("Invalid approval manifest or source") from exc


def run_pure(source: bytes, value: int) -> int:
    if type(value) is not int or not -MAX_INPUT <= value <= MAX_INPUT:
        raise EdgeDenied("Input must be a bounded signed integer")
    if not isinstance(source, bytes) or not 0 < len(source) <= MAX_SOURCE:
        raise EdgeDenied("Source exceeds reviewed size budget")
    try:
        import wasmtime
    except ImportError as exc:
        raise EdgeDenied("Pinned wasmtime==51.0.0 is required") from exc

    config = wasmtime.Config()
    config.consume_fuel = True
    config.max_wasm_stack = 1_048_576
    engine = wasmtime.Engine(config)
    try:
        module = wasmtime.Module(engine, wasmtime.wat2wasm(source))
    except (wasmtime.WasmtimeError, ValueError) as exc:
        raise EdgeDenied("Invalid WebAssembly source") from exc
    if module.imports:
        raise EdgeDenied("Host imports are forbidden (no WASI, file or network access)")
    exports = module.exports
    if len(exports) != 1 or exports[0].name != "run":
        raise EdgeDenied("Only one run export is permitted")
    typ = exports[0].type
    if not isinstance(typ, wasmtime.FuncType) or list(typ.params) != [wasmtime.ValType.i32()] or list(typ.results) != [wasmtime.ValType.i32()]:
        raise EdgeDenied("run must be a pure i32 -> i32 function")
    store = wasmtime.Store(engine)
    store.set_limits(memory_size=MAX_MEMORY, table_elements=0, instances=1, tables=0, memories=0)
    store.set_fuel(MAX_FUEL)
    try:
        instance = wasmtime.Instance(store, module, [])
        result = instance.exports(store)["run"](store, value)
    except (wasmtime.Trap, wasmtime.WasmtimeError) as exc:
        raise EdgeDenied("Wasm execution denied: trap, fuel or resource limits exceeded") from exc
    if type(result) is not int:
        raise EdgeDenied("Unexpected Wasm output")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module-id", required=True, help="Committed, reviewed module ID")
    parser.add_argument("--input", required=True, type=int, help="One bounded signed integer")
    args = parser.parse_args()
    try:
        value = run_pure(approved_source(args.module_id), args.input)
    except EdgeDenied as exc:
        print("Edge preview denied: " + str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"module": args.module_id, "result": value, "status": "local-preview"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
