"""No server required: verify that recovery tooling fails closed."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class BackupCliSafetyTests(unittest.TestCase):
    def test_backup_dry_run_does_not_create_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "would-be.backup"
            proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "backup.py"), "--output", str(target)],
                                  capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0)
            self.assertFalse(target.exists())

    def test_existing_archive_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "already.backup"
            target.write_bytes(b"must stay untouched")
            proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "backup.py"),
                                   "--output", str(target), "--apply"], capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(target.read_bytes(), b"must stay untouched")

    def test_restore_dry_run_requires_existing_archive(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "restore_check.py"), "--archive", "/definitely/not-an-archive"],
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2)

    def test_restore_dry_run_never_starts_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "fake.backup"
            target.write_bytes(b"placeholder")
            proc = subprocess.run([sys.executable, str(ROOT / "scripts" / "restore_check.py"), "--archive", str(target)],
                                  capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0)
            self.assertIn("DRY RUN", proc.stdout)


if __name__ == "__main__":
    unittest.main()
