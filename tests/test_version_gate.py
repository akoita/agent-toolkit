from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

from plugin_versions import discover_packages, packages_needing_bump  # noqa: E402


PACKAGES = {
    "plugins/claude/maestro": "plugins/claude/maestro/.claude-plugin/plugin.json",
    "plugins/codex/codex-maestro": (
        "plugins/codex/codex-maestro/.codex-plugin/plugin.json"
    ),
}


class DiscoveryTests(unittest.TestCase):
    def test_discovers_every_packaged_plugin(self) -> None:
        discovered = discover_packages(ROOT)

        self.assertEqual(discovered, PACKAGES)
        for manifest in discovered.values():
            self.assertTrue((ROOT / manifest).is_file())


class BumpDetectionTests(unittest.TestCase):
    def test_changed_package_without_bump_is_reported(self) -> None:
        stale = packages_needing_bump(
            changed=["plugins/claude/maestro/skills/maestro/SKILL.md"],
            packages=PACKAGES,
            base_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": "0.3.1",
            },
            head_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": "0.3.1",
            },
        )

        self.assertEqual(stale, ["plugins/claude/maestro"])

    def test_changed_package_with_bump_passes(self) -> None:
        stale = packages_needing_bump(
            changed=["plugins/claude/maestro/README.md"],
            packages=PACKAGES,
            base_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": "0.3.1",
            },
            head_versions={
                "plugins/claude/maestro": "0.3.2",
                "plugins/codex/codex-maestro": "0.3.1",
            },
        )

        self.assertEqual(stale, [])

    def test_changes_outside_packages_need_no_bump(self) -> None:
        stale = packages_needing_bump(
            changed=["README.md", "docs/updating.md", "tests/test_version_gate.py"],
            packages=PACKAGES,
            base_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": "0.3.1",
            },
            head_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": "0.3.1",
            },
        )

        self.assertEqual(stale, [])

    def test_new_package_needs_no_bump(self) -> None:
        stale = packages_needing_bump(
            changed=["plugins/codex/codex-maestro/.codex-plugin/plugin.json"],
            packages=PACKAGES,
            base_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": None,
            },
            head_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": "0.1.0",
            },
        )

        self.assertEqual(stale, [])

    def test_prefix_collision_does_not_count_as_touched(self) -> None:
        stale = packages_needing_bump(
            changed=["plugins/claude/maestro-extra/SKILL.md"],
            packages=PACKAGES,
            base_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": "0.3.1",
            },
            head_versions={
                "plugins/claude/maestro": "0.3.1",
                "plugins/codex/codex-maestro": "0.3.1",
            },
        )

        self.assertEqual(stale, [])


if __name__ == "__main__":
    unittest.main()
