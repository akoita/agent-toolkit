from __future__ import annotations

import unittest
from pathlib import Path


AGENTS_ROOT = (
    Path(__file__).resolve().parents[1] / "platforms" / "claude" / "agents"
)


class ClaudeMaestroAgentTests(unittest.TestCase):
    def test_expected_agents_are_bounded_and_use_current_aliases(self) -> None:
        expected = {
            "maestro-opus-implementation.md": ("opus", "high"),
            "maestro-sonnet-mechanical.md": ("sonnet", "medium"),
        }

        for filename, (model, effort) in expected.items():
            with self.subTest(filename=filename):
                text = (AGENTS_ROOT / filename).read_text(encoding="utf-8")
                self.assertIn(f"model: {model}\n", text)
                self.assertIn(f"effort: {effort}\n", text)
                self.assertIn("disallowedTools: Agent", text)
                self.assertNotIn("Mythos", text)

    def test_economical_explorer_is_haiku_and_strictly_read_only(self) -> None:
        text = (AGENTS_ROOT / "maestro-economical-explorer.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("model: haiku\n", text)
        self.assertNotIn("effort:", text)
        self.assertIn("tools: Read, Glob, Grep", text)
        self.assertIn("disallowedTools: Write, Edit, Bash, Agent", text)
        self.assertIn("background: true", text)


if __name__ == "__main__":
    unittest.main()
