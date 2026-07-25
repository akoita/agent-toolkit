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
    / "plugins"
    / "codex"
    / "codex-maestro"
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
            self.assertEqual(implementation["model"], "gpt-5.6-sol")
            self.assertEqual(implementation["model_reasoning_effort"], "medium")
            self.assertEqual(exploration["model"], "gpt-5.6-terra")
            self.assertEqual(exploration["sandbox_mode"], "read-only")
            self.assertNotIn("Luna", result.stdout)
            self.assertFalse((codex_home / "agents" / "luna-worker.toml").exists())

    def test_uninstall_removes_skill_and_unmodified_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            skills_root = Path(directory) / "skills"
            common = [
                "--codex-home",
                str(codex_home),
                "--skills-root",
                str(skills_root),
            ]

            subprocess.run(
                [sys.executable, str(INSTALLER), *common],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertTrue((skills_root / "codex-maestro" / "SKILL.md").is_file())

            subprocess.run(
                [sys.executable, str(INSTALLER), "--uninstall", *common],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertFalse((skills_root / "codex-maestro").exists())
            for filename in ("implementation-worker.toml", "exploration-worker.toml"):
                self.assertFalse((codex_home / "agents" / filename).exists())

    def test_uninstall_keeps_modified_agent_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            common = ["--agent-only", "--codex-home", str(codex_home)]
            worker = codex_home / "agents" / "implementation-worker.toml"

            subprocess.run(
                [sys.executable, str(INSTALLER), *common],
                check=True,
                capture_output=True,
                text=True,
            )
            worker.write_text("model = \"custom\"\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(INSTALLER), "--uninstall", *common],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("Kept modified custom agent", result.stdout)
            self.assertTrue(worker.is_file())
            self.assertFalse((codex_home / "agents" / "exploration-worker.toml").exists())

            subprocess.run(
                [sys.executable, str(INSTALLER), "--uninstall", "--force", *common],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertFalse(worker.exists())

    def test_uninstall_reports_missing_installation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    sys.executable,
                    str(INSTALLER),
                    "--uninstall",
                    "--codex-home",
                    str(Path(directory) / "codex"),
                    "--skills-root",
                    str(Path(directory) / "skills"),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("Skill not installed", result.stdout)
            self.assertIn("Custom agent not installed", result.stdout)

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
