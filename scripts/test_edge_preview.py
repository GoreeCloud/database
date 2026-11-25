"""No-import, hash-pinned, bounded fuel/memory Wasmtime development preview."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from scripts.edge_preview import EdgeDenied, approved_source, run_pure

HAS_WASMTIME = importlib.util.find_spec("wasmtime") is not None


class ApprovedSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.root.joinpath("infra/edge/modules").mkdir(parents=True)
        self.module = self.root / "infra/edge/modules/double.wat"
        self.module.write_bytes(b'(module (func (export "run") (param i32) (result i32) local.get 0))')
        self.manifest = self.root / "infra/edge/approved.json"
        self.manifest.write_text(json.dumps({
            "format": "gc-edge-approved-v1",
            "modules": {"double": hashlib.sha256(self.module.read_bytes()).hexdigest()},
        }))

    def tearDown(self):
        self.temp.cleanup()

    def test_explicit_approval(self):
        self.assertEqual(approved_source("double", self.root), self.module.read_bytes())

    def test_rejects_traversal_and_arbitrary_paths(self):
        for name in ("../../etc/passwd", "unlisted", "", "double.wat", "Double", "a" * 65):
            with self.subTest(name=name):
                with self.assertRaises(EdgeDenied):
                    approved_source(name, self.root)

    def test_rejects_source_tampering(self):
        self.module.write_bytes(self.module.read_bytes() + b"\x00")
        with self.assertRaisesRegex(EdgeDenied, "checksum"):
            approved_source("double", self.root)

    def test_rejects_symlink(self):
        origin = self.root / "outside"
        origin.write_bytes(self.module.read_bytes())
        self.module.unlink()
        self.module.symlink_to(origin)
        with self.assertRaises(EdgeDenied):
            approved_source("double", self.root)

    def test_rejects_invalid_manifest(self):
        self.manifest.write_text('{"format":"bad","modules":{"double":"x"}}')
        with self.assertRaises(EdgeDenied):
            approved_source("double", self.root)

    def test_rejects_oversized_module(self):
        self.module.write_bytes(b"X" * 8193)
        with self.assertRaises(EdgeDenied):
            approved_source("double", self.root)


@unittest.skipUnless(HAS_WASMTIME, "Optional Wasmtime dependency is installed in the edge-preview CI job")
class PureExecutionTests(unittest.TestCase):
    def test_checked_in_approved_example(self):
        self.assertEqual(run_pure(approved_source("double"), 7), 14)
        self.assertEqual(run_pure(approved_source("double"), -13), -26)

    def test_rejects_host_imports_before_instantiation(self):
        wat = b'''(module
          (import "wasi_snapshot_preview1" "fd_write" (func (param i32 i32 i32 i32) (result i32)))
          (func (export "run") (param i32) (result i32) local.get 0))'''
        with self.assertRaisesRegex(EdgeDenied, "imports are forbidden"):
            run_pure(wat, 1)

    def test_rejects_wrong_function_signature(self):
        with self.assertRaisesRegex(EdgeDenied, "pure i32"):
            run_pure(b'(module (func (export "run") (result i64) i64.const 1))', 1)

    def test_rejects_surprise_exports(self):
        wat=b'(module (func (export "run") (param i32) (result i32) local.get 0) (global (export "other") i32 (i32.const 1)))'
        with self.assertRaisesRegex(EdgeDenied, "one run export"):
            run_pure(wat, 1)

    def test_out_of_fuel_loop(self):
        wat=b'(module (func (export "run") (param i32) (result i32) (loop br 0) i32.const 0))'
        with self.assertRaisesRegex(EdgeDenied, "fuel"):
            run_pure(wat, 1)

    def test_memory_over_budget_denied(self):
        wat=b'(module (memory 192) (func (export "run") (param i32) (result i32) local.get 0))'
        with self.assertRaisesRegex(EdgeDenied, "limits"):
            run_pure(wat, 1)

    def test_argument_and_source_bounds(self):
        source=approved_source("double")
        for value in (True, None, "2", 1_000_001, -1_000_001):
            with self.subTest(value=value):
                with self.assertRaises(EdgeDenied):
                    run_pure(source,value)
        with self.assertRaises(EdgeDenied):
            run_pure(b'X'*8193,0)


if __name__ == "__main__":
    unittest.main()
