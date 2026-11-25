"""Pinned SeaweedFS 4.54 Compose exposure/flag guard; no Docker required."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent


class S3ComposeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.overlay = (ROOT / "compose.s3.yaml").read_text(encoding="utf-8")

    def test_opt_in_and_tag(self):
        self.assertIn("chrislusf/seaweedfs:4.54", self.overlay)
        self.assertIn("profiles: [s3-preview]", self.overlay)

    def test_disable_unused_services_at_source(self):
        self.assertIn("- -webdav=false", self.overlay)
        self.assertIn("- -admin.ui=false", self.overlay)
        self.assertIn("- -admin.allowInsecureBind=false", self.overlay)
        self.assertNotIn("- -webdav.allowInsecureBind", self.overlay)

    def test_only_loopback_ingress(self):
        self.assertIn('"127.0.0.1:${GC_S3_PORT:-8333}:8333"', self.overlay)
        self.assertNotIn('"0.0.0.0:', self.overlay)
        self.assertIn("read_only: true", self.overlay)
        self.assertIn("no-new-privileges:true", self.overlay)

    def test_separate_networks_from_postgres(self):
        self.assertIn("networks: [s3_private, s3_ingress]", self.overlay)
        self.assertIn("s3_private:\n    internal: true", self.overlay)
        self.assertNotIn("networks: [data, access]", self.overlay)

    def test_independent_credentials_and_volume(self):
        for key in ("GC_S3_ACCESS_KEY", "GC_S3_SECRET_KEY", "GC_S3_ADMIN_PASSWORD", "gc_s3_preview_data:"):
            self.assertIn(key, self.overlay)


if __name__ == "__main__":
    unittest.main()
