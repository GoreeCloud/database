"""Migration integrity manifest enforces ordering and detects drift without SQL execution."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.check_migrations import MigrationIntegrityError, verified_manifest


class MigrationInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.migrations = self.root / "infra/postgres/migrations"
        self.migrations.mkdir(parents=True)
        (self.root / "infra/postgres/init").mkdir()
        self.one = self.migrations / "002-readonly.sql"
        self.two = self.migrations / "003-more.sql"
        self.one.write_text("CREATE SCHEMA test_one;\n")
        self.two.write_text("CREATE SCHEMA test_two;\n")
        self.bootstrap = self.root / "infra/postgres/init/001-bootstrap.sh"
        self.bootstrap.write_text(
            "psql -X --set=ON_ERROR_STOP=1 --file=/migrations/002-readonly.sql\n"
            "psql -X --set=ON_ERROR_STOP=1 --file=/migrations/003-more.sql\n"
        )
        self.manifest = self.migrations / "manifest.json"
        self.write_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_manifest(self) -> None:
        self.manifest.write_text(json.dumps({
            "format": "goreecloud-database-migrations-v1",
            "sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                       for path in [self.one, self.two]},
        }))

    def test_verified_source_inventory(self):
        records = verified_manifest(self.root)
        self.assertEqual([v["file"] for v in records], ["002-readonly.sql", "003-more.sql"])
        self.assertTrue(all(len(v["sha256"]) == 64 for v in records))

    def test_rejects_mutated_sql_after_review(self):
        self.one.write_text("DROP SCHEMA test_one CASCADE;\n")
        with self.assertRaisesRegex(MigrationIntegrityError, "checksum changed"):
            verified_manifest(self.root)

    def test_rejects_missing_invocation(self):
        self.bootstrap.write_text("psql -X --file=/migrations/002-readonly.sql\n")
        with self.assertRaisesRegex(MigrationIntegrityError, "invoke every migration"):
            verified_manifest(self.root)

    def test_rejects_reordered_calls(self):
        self.bootstrap.write_text(
            "psql -X --file=/migrations/003-more.sql\n"
            "psql -X --file=/migrations/002-readonly.sql\n"
        )
        with self.assertRaisesRegex(MigrationIntegrityError, "invoke every migration"):
            verified_manifest(self.root)

    def test_rejects_duplicate_calls(self):
        with self.bootstrap.open("a") as out:
            out.write("psql --file=/migrations/002-readonly.sql\n")
        with self.assertRaises(MigrationIntegrityError):
            verified_manifest(self.root)

    def test_rejects_sequence_gap(self):
        (self.migrations / "003-more.sql").rename(self.migrations / "004-more.sql")
        with self.assertRaisesRegex(MigrationIntegrityError, "sequence"):
            verified_manifest(self.root)

    def test_rejects_unreviewed_file(self):
        (self.migrations / "004-surprise.sql").write_text("SELECT 1;\n")
        with self.assertRaises(MigrationIntegrityError):
            verified_manifest(self.root)

    def test_rejects_missing_manifest(self):
        self.manifest.unlink()
        with self.assertRaises(MigrationIntegrityError):
            verified_manifest(self.root)

    def test_rejects_invalid_manifest_format(self):
        self.manifest.write_text('{"format": "unknown","sha256":{}}')
        with self.assertRaisesRegex(MigrationIntegrityError, "format"):
            verified_manifest(self.root)

    def test_rejects_blank_sql(self):
        self.two.write_bytes(b"")
        self.write_manifest()
        with self.assertRaisesRegex(MigrationIntegrityError, "empty"):
            verified_manifest(self.root)


if __name__ == "__main__":
    unittest.main()
