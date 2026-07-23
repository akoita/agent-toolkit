from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plugins" / "claude" / "maestro"
PLUGIN_MANIFEST = PACKAGE_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"


class ClaudePluginPackageTests(unittest.TestCase):
    def test_plugin_manifest_identity_and_layout(self) -> None:
        manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "maestro")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertTrue(manifest["description"])
        self.assertEqual(manifest["author"], {"name": "Aboubakar Koïta"})
        self.assertEqual(
            manifest["repository"],
            "https://github.com/akoita/agent-toolkit",
        )
        self.assertTrue((PACKAGE_ROOT / "skills" / "maestro" / "SKILL.md").is_file())
        self.assertTrue((PACKAGE_ROOT / "agents").is_dir())

    def test_marketplace_identity_and_plugin_path(self) -> None:
        marketplace = json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))

        self.assertEqual(marketplace["name"], "agent-toolkit")
        self.assertEqual(marketplace["owner"], {"name": "Aboubakar Koïta"})
        self.assertEqual(len(marketplace["plugins"]), 1)

        plugin = marketplace["plugins"][0]
        self.assertEqual(plugin["name"], "maestro")
        self.assertEqual(plugin["source"], "./plugins/claude/maestro")
        self.assertEqual(
            (ROOT / plugin["source"]).resolve(),
            PACKAGE_ROOT.resolve(),
        )
        self.assertEqual(plugin["version"], "0.1.0")
        self.assertTrue(plugin["description"])

    def test_package_has_no_cache_artifacts(self) -> None:
        cache_artifacts = [
            path
            for path in PACKAGE_ROOT.rglob("*")
            if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
        ]

        self.assertEqual(cache_artifacts, [])


if __name__ == "__main__":
    unittest.main()
