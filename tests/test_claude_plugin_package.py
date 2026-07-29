from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGES_ROOT = ROOT / "plugins" / "claude"
MARKETPLACE_MANIFEST = ROOT / ".claude-plugin" / "marketplace.json"
AUTHOR = {"name": "Aboubakar Koïta"}
REPOSITORY = "https://github.com/akoita/agent-toolkit"
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def packages() -> list[Path]:
    """Every Claude package directory, discovered from the tree."""
    return sorted(
        path
        for path in PACKAGES_ROOT.iterdir()
        if (path / ".claude-plugin" / "plugin.json").is_file()
    )


def manifest_of(package: Path) -> dict:
    return json.loads(
        (package / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )


def marketplace() -> dict:
    return json.loads(MARKETPLACE_MANIFEST.read_text(encoding="utf-8"))


class ClaudePluginPackageTests(unittest.TestCase):
    def test_at_least_one_package_is_discovered(self) -> None:
        self.assertTrue(packages())

    def test_plugin_manifest_identity_and_layout(self) -> None:
        for package in packages():
            with self.subTest(package=package.name):
                manifest = manifest_of(package)

                self.assertEqual(manifest["name"], package.name)
                self.assertRegex(manifest["version"], SEMVER)
                self.assertTrue(manifest["description"])
                self.assertEqual(manifest["author"], AUTHOR)
                self.assertEqual(manifest["repository"], REPOSITORY)
                self.assertTrue(sorted((package / "skills").glob("*/SKILL.md")))

    def test_marketplace_identity(self) -> None:
        catalog = marketplace()

        self.assertEqual(catalog["name"], "agent-toolkit")
        self.assertEqual(catalog["owner"], AUTHOR)
        self.assertEqual(
            {entry["name"] for entry in catalog["plugins"]},
            {package.name for package in packages()},
        )

    def test_marketplace_entry_matches_package(self) -> None:
        entries = {entry["name"]: entry for entry in marketplace()["plugins"]}

        for package in packages():
            with self.subTest(package=package.name):
                entry = entries[package.name]

                self.assertEqual(
                    (ROOT / entry["source"]).resolve(), package.resolve()
                )
                self.assertTrue(entry["description"])
                self.assertEqual(entry["version"], manifest_of(package)["version"])

    def test_package_has_no_cache_artifacts(self) -> None:
        for package in packages():
            with self.subTest(package=package.name):
                cache_artifacts = [
                    path
                    for path in package.rglob("*")
                    if path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"}
                ]

                self.assertEqual(cache_artifacts, [])


if __name__ == "__main__":
    unittest.main()
