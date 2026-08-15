from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = (
    ROOT
    / "plugins"
    / "portable"
    / "codex-maestro"
    / "skills"
    / "codex-maestro"
    / "SKILL.md"
)
README = ROOT / "plugins" / "codex" / "codex-maestro" / "README.md"


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


class CodexMaestroContractTests(unittest.TestCase):
    def test_native_lifecycle_is_primary_and_cli_is_the_fallback(self) -> None:
        skill = normalized(SKILL)

        for required in (
            "Native collaboration is primary",
            "spawning and waiting",
            "list/status",
            "ordinary messages to a running worker",
            "use follow-up when an idle worker",
            "interrupt obsolete or unsafe work",
            "close completed threads",
            "generic native worker with the full self-contained contract",
            "If native spawning is unavailable",
            "CLI fallback",
        ):
            with self.subTest(required=required):
                self.assertIn(required, skill)

        self.assertIn(
            "close completed threads where the runtime supports those operations",
            skill,
        )
        self.assertIn("when the client supports selective history", skill)
        self.assertIn(
            "Verify the running client supports it before designing around it",
            skill,
        )

    def test_context_and_authority_boundaries_are_explicit(self) -> None:
        skill = normalized(SKILL)

        self.assertIn('fork_turns: "none"', skill)
        self.assertIn("inherit only the turns needed", skill)
        self.assertIn("every assignment must restate its scope", skill)
        self.assertIn("Only the root maestro", skill)
        self.assertIn("Workers must not create subagents", skill)
        self.assertIn(
            "must never accept a decision or new assignment from a peer", skill
        )

    def test_shared_workspace_and_execution_evidence_are_explicit(self) -> None:
        skill = normalized(SKILL)

        self.assertIn("shared workspace", skill)
        self.assertIn("disjoint, explicit path ownership", skill)
        self.assertIn("Serialize work that may touch the same path", skill)
        self.assertIn("unexpected overlapping edits must stop writing", skill)
        self.assertIn("Never overwrite, reset", skill)
        self.assertIn("Normalize every observed limit", skill)
        self.assertIn("subtract the primary from a root-inclusive total", skill)
        self.assertIn("most restrictive normalized", skill)
        self.assertIn("excludes the primary", skill)
        self.assertIn(
            "Keep topology evidence separate from execution evidence", skill
        )

    def test_readme_summarizes_native_runtime_contract(self) -> None:
        readme = normalized(README)

        self.assertIn("## Native collaboration", readme)
        self.assertIn("most restrictive normalized limit", readme)
        self.assertIn("explicit, disjoint path ownership", readme)
        self.assertIn("Subagent nesting stays disabled by default", readme)
        self.assertIn("Native topology alone does not prove", readme)


if __name__ == "__main__":
    unittest.main()
