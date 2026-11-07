from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "portable" / "baseline" / "skills" / "project-baseline" / "scripts"


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"project_baseline_{name}", SCRIPTS / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ProjectBaselineApplyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.apply = load("apply")
        cls.audit = load("audit")

    def project(self, files: dict[str, str]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def run_main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            try:
                code = self.apply.main(list(args))
            except SystemExit as error:
                code = int(error.code or 0)
        return code, out.getvalue()

    def status(self, root: Path, practice: str) -> str:
        return {result.id: result.status for result in self.audit.audit(root)}[practice]

    def test_dry_run_writes_nothing(self) -> None:
        root = self.project({"AGENTS.md": "# Rules\n"})
        code, out = self.run_main(str(root), "--practice", "claude-imports-agents")
        self.assertEqual(code, 0)
        self.assertIn("+@AGENTS.md", out)
        self.assertFalse((root / "CLAUDE.md").exists())

    def test_write_makes_mechanical_practices_present(self) -> None:
        root = self.project({"AGENTS.md": "# Rules\n"})
        code, _ = self.run_main(
            str(root),
            "--practice",
            "claude-imports-agents",
            "--practice",
            "toolkit-plugins",
            "--write",
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.status(root, "claude-imports-agents"), "present")
        self.assertEqual(self.status(root, "toolkit-plugins"), "present")
        code, out = self.run_main(str(root), "--practice", "toolkit-plugins")
        self.assertEqual(out.strip(), "Nothing to change.")

    def test_existing_text_and_settings_are_kept(self) -> None:
        self.assertEqual(
            self.apply.claude_md("# Notes\nKeep me.\n"),
            "# Notes\n\n@AGENTS.md\nKeep me.\n",
        )
        self.assertEqual(self.apply.claude_md("Keep me.\n"), "@AGENTS.md\n\nKeep me.\n")
        merged = json.loads(
            self.apply.settings(
                json.dumps(
                    {
                        "permissions": {"allow": ["Bash(ls)"]},
                        "enabledPlugins": {"baseline@agent-toolkit": False},
                    }
                )
            )
        )
        self.assertEqual(merged["permissions"], {"allow": ["Bash(ls)"]})
        self.assertIs(merged["enabledPlugins"]["baseline@agent-toolkit"], False)
        self.assertIs(merged["enabledPlugins"]["utilities@agent-toolkit"], True)
        self.assertIn("agent-toolkit", merged["extraKnownMarketplaces"])

    def test_decisions_are_recorded_and_honoured(self) -> None:
        root = self.project({})
        code, _ = self.run_main(
            str(root),
            "--decline",
            "readme",
            "--reason",
            "Docs site is the front door.",
            "--adopt",
            "feature-catalog",
            "--write",
        )
        self.assertEqual(code, 0)
        record = json.loads((root / ".agent-toolkit" / "baseline.json").read_text())
        self.assertEqual(record["decisions"]["readme"]["decision"], "decline")
        self.assertEqual(record["decisions"]["feature-catalog"]["decision"], "adopt")
        self.assertEqual(self.status(root, "readme"), "declined")
        self.assertEqual(self.status(root, "feature-catalog"), "missing")

    def test_rejects_unknown_practice_and_decline_without_reason(self) -> None:
        root = self.project({})
        self.assertEqual(self.run_main(str(root), "--practice", "nope")[0], 2)
        self.assertEqual(self.run_main(str(root), "--decline", "readme")[0], 2)

    def test_non_mechanical_practice_writes_nothing(self) -> None:
        root = self.project({})
        code, out = self.run_main(str(root), "--practice", "feature-catalog", "--write")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "Nothing to change.")
        self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
