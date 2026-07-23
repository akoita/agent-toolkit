from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_SKILL_ROOT = ROOT / "platforms" / "claude" / "skills" / "maestro"
CANONICAL_AGENTS_ROOT = ROOT / "platforms" / "claude" / "agents"
PACKAGE_ROOT = ROOT / "plugins" / "claude" / "maestro"
PLUGIN_MANIFEST = PACKAGE_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"


def _files_by_relative_path(root: Path) -> dict[Path, Path]:
    return {
        path.relative_to(root): path
        for path in root.rglob("*")
        if path.is_file()
    }


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

    def test_packaged_skill_and_agents_match_canonical_sources(self) -> None:
        source_roots = (
            (
                CANONICAL_SKILL_ROOT,
                PACKAGE_ROOT / "skills" / "maestro",
            ),
            (CANONICAL_AGENTS_ROOT, PACKAGE_ROOT / "agents"),
        )

        for canonical_root, packaged_root in source_roots:
            with self.subTest(root=canonical_root):
                canonical_files = _files_by_relative_path(canonical_root)
                packaged_files = _files_by_relative_path(packaged_root)
                self.assertEqual(
                    set(packaged_files),
                    set(canonical_files),
                )

                for relative_path, canonical_file in canonical_files.items():
                    self.assertEqual(
                        packaged_files[relative_path].read_bytes(),
                        canonical_file.read_bytes(),
                        relative_path.as_posix(),
                    )

    def test_package_has_no_cache_artifacts(self) -> None:
        cache_artifacts = [
            path
            for path in PACKAGE_ROOT.rglob("*")
            if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
        ]

        self.assertEqual(cache_artifacts, [])


if __name__ == "__main__":
    unittest.main()
