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
    def test_only_solo_preset_is_advertised(self) -> None:
        skill = normalized(SKILL)
        self.assertIn("only supported preset is `gpt-6-astra` at `medium`", skill)
        self.assertIn("Do not spawn native workers, run CLI workers", skill)
        self.assertIn("not supported presets", skill)
        self.assertNotIn("--profile economy", skill)
        self.assertNotIn("--profile astra-parallel", skill)

    def test_root_owns_planning_verification_and_publication(self) -> None:
        skill = normalized(SKILL)
        for required in ("## 1. Analyze", "## 2. Plan", "## 3. Implement",
                         "## 4. Review", "## 5. Present", "compatibility invariants",
                         "root owns final review", "explicit user override"):
            self.assertIn(required, skill)
        self.assertIn("python scripts/check_routing.py --enforce", skill)
        self.assertIn("fails closed", skill)

    def test_readme_discloses_evidence_limits_and_migration(self) -> None:
        readme = normalized(README)
        self.assertIn("only supported preset", readme)
        self.assertIn("did not establish", readme)
        self.assertIn("No custom-agent setup is required", readme)
        self.assertIn("Existing worker definitions remain untouched", readme)
        self.assertIn("not part of the supported Maestro workflow", readme)


if __name__ == "__main__":
    unittest.main()
