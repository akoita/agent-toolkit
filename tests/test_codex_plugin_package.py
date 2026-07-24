from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plugins" / "codex" / "codex-maestro"
PACKAGED_SKILL_ROOT = PACKAGE_ROOT / "skills" / "codex-maestro"
PLUGIN_MANIFEST = PACKAGE_ROOT / ".codex-plugin" / "plugin.json"
MARKETPLACE_MANIFEST = ROOT / ".agents" / "plugins" / "marketplace.json"
IGNORED_DIRECTORY_NAMES = {"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


class CodexPluginPackageTests(unittest.TestCase):
    def test_plugin_manifest_identity_and_layout(self) -> None:
        manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], PACKAGE_ROOT.name)
        self.assertRegex(manifest["version"], SEMVER)
        self.assertEqual(manifest["author"]["name"], "Aboubakar Koïta")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(
            manifest["repository"], "https://github.com/akoita/agent-toolkit"
        )
        self.assertTrue((PACKAGED_SKILL_ROOT / "SKILL.md").is_file())

    def test_marketplace_identity_policy_and_plugin_path(self) -> None:
        marketplace = json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(marketplace["name"], "agent-toolkit")
        self.assertEqual(marketplace["interface"]["displayName"], "Agent Toolkit")
        self.assertEqual(len(marketplace["plugins"]), 1)

        plugin = marketplace["plugins"][0]
        self.assertEqual(plugin["name"], "codex-maestro")
        self.assertEqual(plugin["source"]["source"], "local")
        self.assertEqual(
            (ROOT / plugin["source"]["path"]).resolve(), PACKAGE_ROOT.resolve()
        )
        self.assertEqual(
            plugin["policy"],
            {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        )
        self.assertEqual(plugin["category"], "Developer Tools")
        self.assertNotIn("products", plugin["policy"])

    def test_package_has_no_cache_artifacts(self) -> None:
        cache_artifacts = [
            path
            for path in PACKAGE_ROOT.rglob("*")
            if path.name in IGNORED_DIRECTORY_NAMES
            or path.suffix in IGNORED_SUFFIXES
        ]

        self.assertEqual(cache_artifacts, [])


if __name__ == "__main__":
    unittest.main()
