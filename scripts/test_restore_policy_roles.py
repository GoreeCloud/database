"""Isolated recovery verifies NOLOGIN role placeholders for RLS policies."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts import restore_check


class RestorePolicyRoleTests(unittest.TestCase):
    def test_disposable_restore_prepares_policy_roles_without_secrets(self):
        with TemporaryDirectory() as folder:
            archive = Path(folder) / "dummy.backup"
            archive.write_bytes(b"dummy archive bytes")
            calls: list[list[str]] = []

            def fake_run(cmd: list[str], **_kwargs):
                calls.append(cmd)
                return subprocess.CompletedProcess(cmd, 0)

            with (
                patch.object(restore_check, "run", side_effect=fake_run),
                patch.object(restore_check.time, "sleep"),
                patch.object(sys, "argv", ["restore_check.py", "--archive", str(archive), "--apply"]),
            ):
                self.assertEqual(restore_check.main(), 0)

        role_commands = [cmd for cmd in calls if "CREATE ROLE gc_reader NOLOGIN" in " ".join(cmd)]
        self.assertEqual(len(role_commands), 1)
        self.assertIn("gc_api NOLOGIN", " ".join(role_commands[0]))
        self.assertFalse(any("GC_ADMIN_TOKEN" in str(cmd) for cmd in calls))
        self.assertTrue(any("--network" in cmd and "none" in cmd for cmd in calls))
        self.assertTrue(any(cmd[1:3] == ["rm", "-f"] for cmd in calls))

    def test_role_setup_failure_fails_closed_and_cleans_up(self):
        with TemporaryDirectory() as folder:
            archive = Path(folder) / "dummy.backup"
            archive.write_bytes(b"dummy archive bytes")
            calls: list[list[str]] = []

            def fake_run(cmd: list[str], **_kwargs):
                calls.append(cmd)
                if any("CREATE ROLE gc_reader NOLOGIN" in arg for arg in cmd):
                    return subprocess.CompletedProcess(cmd, 1)
                return subprocess.CompletedProcess(cmd, 0)

            with (
                patch.object(restore_check, "run", side_effect=fake_run),
                patch.object(restore_check.time, "sleep"),
                patch.object(sys, "argv", ["restore_check.py", "--archive", str(archive), "--apply"]),
            ):
                self.assertEqual(restore_check.main(), 1)

        self.assertFalse(any("pg_restore" in cmd for cmd in calls))
        self.assertTrue(any(cmd[1:3] == ["rm", "-f"] for cmd in calls))


if __name__ == "__main__":
    unittest.main()
