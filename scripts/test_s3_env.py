"""S3 preview env mutation is explicit, private and never overwrites credentials."""
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.init_s3_env import add_preview_credentials


class S3EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / ".env"
        self.path.write_text("# Generated locally. DO NOT COMMIT OR SHARE.\nPOSTGRES_DB=goreecloud\n")
        self.path.chmod(0o600)

    def tearDown(self):
        self.temp.cleanup()

    def test_append_once_with_private_mode_and_unique_values(self):
        with patch("scripts.init_s3_env.secrets.token_urlsafe", side_effect=["test-secret-1", "test-admin-2"]):
            add_preview_credentials(self.path)
        data = self.path.read_text()
        self.assertIn("GC_S3_ACCESS_KEY=", data)
        self.assertIn("GC_S3_SECRET_KEY=test-secret-1", data)
        self.assertIn("GC_S3_ADMIN_PASSWORD=test-admin-2", data)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(data.count("GC_S3_ACCESS_KEY="), 1)

    def test_refuses_to_overwrite_existing_keys(self):
        add_preview_credentials(self.path)
        original = self.path.read_bytes()
        with self.assertRaises(ValueError):
            add_preview_credentials(self.path)
        self.assertEqual(original, self.path.read_bytes())

    def test_refuses_public_env_permissions(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "mode 0600"):
            add_preview_credentials(self.path)
        self.assertNotIn("GC_S3_", self.path.read_text())

    def test_refuses_symlink(self):
        alias = self.path.parent / "link.env"
        alias.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "regular private"):
            add_preview_credentials(alias)

    def test_refuses_invalid_origin_marker(self):
        self.path.write_text("POSTGRES_DB=changed\n")
        with self.assertRaisesRegex(ValueError, "provenance"):
            add_preview_credentials(self.path)

    def test_refuses_partial_existing_s3_credentials(self):
        with self.path.open("a") as file:
            file.write("GC_S3_ACCESS_KEY=already-supplied\n")
        with self.assertRaisesRegex(ValueError, "already exist"):
            add_preview_credentials(self.path)


if __name__ == "__main__":
    unittest.main()
