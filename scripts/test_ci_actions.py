"""Pinned action lockfile must reject mutable refs and unreviewed new steps."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.check_ci_actions import ActionPinError, ROOT, verify_actions


class ActionPinIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / ".github/workflows").mkdir(parents=True)
        (self.root / "infra/ci").mkdir(parents=True)
        self.workflow = self.root / ".github/workflows/ci.yml"
        self.manifest = self.root / "infra/ci/actions-lock.json"
        shutil.copyfile(ROOT / ".github/workflows/ci.yml", self.workflow)
        shutil.copyfile(ROOT / "infra/ci/actions-lock.json", self.manifest)

    def tearDown(self):
        self.temp.cleanup()

    def test_verified_locked_actions(self):
        observed = verify_actions(self.root)
        self.assertIn("actions/checkout", observed)
        self.assertGreaterEqual(sum(observed.values()), 6)

    def test_rejects_mutable_action_tag(self):
        self.workflow.write_text(self.workflow.read_text().replace(
            "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683",
            "actions/checkout@v4",
        ))
        with self.assertRaises(ActionPinError):
            verify_actions(self.root)

    def test_rejects_mismatched_digest(self):
        self.workflow.write_text(self.workflow.read_text().replace(
            "11bd71901bbe5b1630ceea73d27597364c9af683",
            "0" * 40,
        ))
        with self.assertRaises(ActionPinError):
            verify_actions(self.root)

    def test_rejects_unlisted_action(self):
        with self.workflow.open("a") as out:
            out.write("\n      - uses: random/vendor@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa # v1.0.0\n")
        with self.assertRaises(ActionPinError):
            verify_actions(self.root)

    def test_rejects_wrong_comment_version(self):
        self.workflow.write_text(self.workflow.read_text().replace("# v4.2.2", "# v4.2.1"))
        with self.assertRaises(ActionPinError):
            verify_actions(self.root)

    def test_rejects_lockfile_mutation(self):
        j = json.loads(self.manifest.read_text())
        j["actions"]["actions/checkout"]["sha"] = "1" * 40
        self.manifest.write_text(json.dumps(j))
        with self.assertRaises(ActionPinError):
            verify_actions(self.root)

    def test_rejects_symlink_workflow(self):
        target = self.root / "other.yml"
        target.write_text(self.workflow.read_text())
        self.workflow.unlink()
        self.workflow.symlink_to(target)
        with self.assertRaises(ActionPinError):
            verify_actions(self.root)


if __name__ == "__main__":
    unittest.main()
