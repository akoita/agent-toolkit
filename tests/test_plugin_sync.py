from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SYNC_SCRIPT = ROOT / "scripts" / "sync_plugin_packages.py"


class PluginSyncTests(unittest.TestCase):
    def test_generated_plugin_payloads_are_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SYNC_SCRIPT), "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("match their canonical", result.stdout)


if __name__ == "__main__":
    unittest.main()
