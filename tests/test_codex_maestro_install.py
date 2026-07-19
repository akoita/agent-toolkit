from __future__ import annotations

import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = (
    ROOT
    / "platforms"
    / "codex"
    / "skills"
    / "codex-maestro"
    / "scripts"
    / "install.py"
)


class CodexMaestroInstallerTests(unittest.TestCase):
    def test_agent_install_uses_capability_based_templates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"

            result = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--agent-only",
                    "--codex-home",
                    str(codex_home),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            implementation = tomllib.loads(
                (codex_home / "agents" / "implementation-worker.toml").read_text(
                    encoding="utf-8"
                )
            )
            exploration = tomllib.loads(
                (codex_home / "agents" / "exploration-worker.toml").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(implementation["model"], "gpt-5.6")
            self.assertEqual(implementation["model_reasoning_effort"], "medium")
            self.assertEqual(exploration["model"], "gpt-5.6-terra")
            self.assertEqual(exploration["sandbox_mode"], "read-only")
            self.assertNotIn("Luna", result.stdout)
            self.assertFalse((codex_home / "agents" / "luna-worker.toml").exists())

    def test_legacy_agent_is_reported_but_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            legacy = codex_home / "agents" / "luna-worker.toml"
            legacy.parent.mkdir(parents=True)
            legacy.write_text("user-owned legacy agent\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--agent-only",
                    "--codex-home",
                    str(codex_home),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("legacy custom agent remains in place", result.stdout)
            self.assertEqual(
                legacy.read_text(encoding="utf-8"), "user-owned legacy agent\n"
            )


if __name__ == "__main__":
    unittest.main()
