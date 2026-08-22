from __future__ import annotations

import importlib.util
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "setup-agent-toolkit"
    / "scripts"
    / "configure_policy.py"
)
SPEC = importlib.util.spec_from_file_location("configure_policy", SCRIPT)
assert SPEC and SPEC.loader
configure_policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(configure_policy)


class ConfigurePolicyTests(unittest.TestCase):
    def test_appends_managed_block_without_changing_existing_content(self) -> None:
        current = "# Existing instructions\n\nKeep this exactly.\n"

        updated = configure_policy.updated_text(current, "codex", "\n")

        self.assertTrue(updated.startswith(current + "\n"))
        self.assertEqual(updated.count(configure_policy.START), 1)
        self.assertEqual(updated.count(configure_policy.END), 1)

    def test_replaces_only_existing_managed_block(self) -> None:
        old = (
            "before\n\n"
            f"{configure_policy.START}\nold policy\n{configure_policy.END}"
            "\n\nafter\n"
        )

        updated = configure_policy.updated_text(old, "claude", "\n")

        self.assertTrue(updated.startswith("before\n\n"))
        self.assertTrue(updated.endswith("\n\nafter\n"))
        self.assertNotIn("old policy", updated)

    def test_generated_policies_use_current_capability_routing(self) -> None:
        codex = configure_policy.managed_block("codex", "\n")
        claude = configure_policy.managed_block("claude", "\n")

        self.assertIn("gpt-5.6-luna", codex)
        self.assertIn("gpt-5.6-sol", codex)
        self.assertIn("xhigh", codex)
        self.assertIn("fail-closed routing preflight", codex)
        self.assertIn("persisted route is verified", codex)
        self.assertIn("native spawn, wait, and same-worker steering", codex)
        self.assertIn("effective runtime thread capacity", codex)
        self.assertIn("CLI worker only as a fallback", codex)
        self.assertIn("agent workspace as shared", codex)
        self.assertIn("exclusive,\n  disjoint ownership", codex)
        self.assertIn("serialize overlapping edits", codex)
        self.assertIn("Keep nesting disabled by\n  default", codex)
        self.assertNotIn("Luna", codex)
        self.assertNotIn("Sol", codex)
        self.assertIn("dynamic workflows", claude)
        self.assertIn("`opus`", claude)
        self.assertNotIn("Mythos", claude)

    def test_rejects_malformed_or_duplicate_markers(self) -> None:
        malformed = f"{configure_policy.START}\nmissing end\n"
        duplicate = (
            f"{configure_policy.START}\n{configure_policy.END}\n"
            f"{configure_policy.START}\n{configure_policy.END}\n"
        )

        with self.assertRaises(ValueError):
            configure_policy.updated_text(malformed, "codex", "\n")
        with self.assertRaises(ValueError):
            configure_policy.updated_text(duplicate, "codex", "\n")

    def test_atomic_apply_creates_verified_backup_and_preserves_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "AGENTS.md"
            current = "# Existing\r\n\r\nKeep me.\r\n"
            path.write_bytes(current.encode("utf-8"))
            path.chmod(0o640)
            updated = configure_policy.updated_text(current, "codex", "\r\n")

            backup = configure_policy.apply_atomic(path, current, updated)

            self.assertIsNotNone(backup)
            assert backup is not None
            self.assertEqual(backup.read_bytes(), current.encode("utf-8"))
            self.assertEqual(path.read_bytes(), updated.encode("utf-8"))
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)

    def test_atomic_apply_creates_new_file_without_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CLAUDE.md"
            updated = configure_policy.updated_text("", "claude", "\n")

            backup = configure_policy.apply_atomic(path, "", updated)

            self.assertIsNone(backup)
            self.assertEqual(path.read_bytes(), updated.encode("utf-8"))

    def test_refuses_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real.md"
            link = root / "AGENTS.md"
            real.write_text("existing", encoding="utf-8")
            try:
                link.symlink_to(real)
            except OSError:
                self.skipTest("Symlink creation is unavailable")

            with self.assertRaises(ValueError):
                configure_policy.read_existing(link)

    def test_cli_requires_apply_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = [
                sys.executable,
                str(SCRIPT),
                "--platform",
                "codex",
                "--scope",
                "project",
                "--project-root",
                str(root),
            ]

            preview = subprocess.run(
                command, check=True, capture_output=True, text=True
            )

            self.assertIn("Preview only", preview.stdout)
            self.assertFalse((root / "AGENTS.md").exists())

            applied = subprocess.run(
                [*command, "--apply"], check=True, capture_output=True, text=True
            )

            self.assertIn("Applied", applied.stdout)
            self.assertTrue((root / "AGENTS.md").is_file())


if __name__ == "__main__":
    unittest.main()
