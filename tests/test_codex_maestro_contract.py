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
    def test_only_sol_luna_route_is_advertised(self) -> None:
        skill = normalized(SKILL)
        self.assertIn("only supported route", skill)
        self.assertIn("`gpt-5.6-sol`", skill)
        self.assertIn("`gpt-5.6-luna`", skill)
        self.assertIn("`max`", skill)
        self.assertIn("implementation_worker", skill)
        self.assertIn("exploration_worker", skill)
        self.assertNotIn("gpt-6-astra", skill)

    def test_root_owns_planning_verification_and_publication(self) -> None:
        skill = normalized(SKILL)
        for required in (
            "## 1. Analyze and plan",
            "## 2. Delegate bounded work",
            "## 3. Review and verify",
            "## 4. Present and publish",
            "compatibility invariants",
            "explicit user override",
        ):
            self.assertIn(required, skill)
        self.assertIn("python scripts/check_routing.py --enforce", skill)
        self.assertIn("--worker-rollout", skill)
        self.assertIn("fails closed", skill)

    def test_readme_discloses_evidence_limits_and_migration(self) -> None:
        readme = normalized(README)
        self.assertIn("only supported route", readme)
        self.assertIn("did not establish", readme)
        self.assertIn("does not write user-owned agent configuration", readme)
        self.assertIn("Version 0.7.4", readme)
        self.assertIn("--agent-only --force", readme)
        self.assertNotIn("gpt-6-astra", readme)


if __name__ == "__main__":
    unittest.main()
