from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = ROOT / "skills"
CANONICAL_SKILLS = {
    "maestro": ROOT / "plugins" / "claude" / "maestro" / "skills" / "maestro",
    "codex-maestro": (
        ROOT
        / "plugins"
        / "codex"
        / "codex-maestro"
        / "skills"
        / "codex-maestro"
    ),
    "setup-agent-toolkit": ROOT / "tools" / "setup-agent-toolkit",
}
IGNORED_DIRECTORY_NAMES = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def source_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_DIRECTORY_NAMES for part in path.parts)
        and path.suffix not in IGNORED_SUFFIXES
    }


class SkillsCliCatalogTests(unittest.TestCase):
    def test_catalog_contains_only_the_mirrored_skills(self) -> None:
        skill_directories = {
            path.name for path in CATALOG_ROOT.iterdir() if path.is_dir()
        }

        self.assertEqual(skill_directories, set(CANONICAL_SKILLS))

    def test_mirrors_match_canonical_sources_byte_for_byte(self) -> None:
        for skill_name, canonical_root in CANONICAL_SKILLS.items():
            mirror_root = CATALOG_ROOT / skill_name
            canonical_files = source_files(canonical_root)
            mirror_files = source_files(mirror_root)

            with self.subTest(skill=skill_name, check="file set"):
                self.assertEqual(mirror_files, canonical_files)

            for relative_path in sorted(canonical_files):
                with self.subTest(skill=skill_name, file=str(relative_path)):
                    self.assertEqual(
                        (mirror_root / relative_path).read_bytes(),
                        (canonical_root / relative_path).read_bytes(),
                    )


if __name__ == "__main__":
    unittest.main()
