from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG_ROOT = ROOT / "skills"
CLAUDE_SECURITY_SKILLS = ROOT / "plugins" / "claude" / "security" / "skills"
CODEX_SECURITY_SKILLS = ROOT / "plugins" / "codex" / "codex-security" / "skills"
# Authored once in the Claude plugin, shipped by the Codex package too. Kept in
# step with `.github/scripts/sync_skills.py`.
SECURITY_SKILLS = (
    "security-audit",
    "security-review",
    "security-scan",
    "security-supply-chain",
    "security-threat-model",
    "security-smart-contracts",
    "security-ai",
)
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
    **{name: CLAUDE_SECURITY_SKILLS / name for name in SECURITY_SKILLS},
}
IGNORED_DIRECTORY_NAMES = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def mirrors_for(name: str) -> list[Path]:
    """Every generated copy of a canonical skill."""
    mirrors = [CATALOG_ROOT / name]
    if name in SECURITY_SKILLS:
        mirrors.append(CODEX_SECURITY_SKILLS / name)
    return mirrors


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

    def test_codex_security_package_contains_only_the_mirrored_skills(self) -> None:
        skill_directories = {
            path.name for path in CODEX_SECURITY_SKILLS.iterdir() if path.is_dir()
        }

        self.assertEqual(skill_directories, set(SECURITY_SKILLS))

    def test_mirrors_match_canonical_sources_byte_for_byte(self) -> None:
        for skill_name, canonical_root in CANONICAL_SKILLS.items():
            canonical_files = source_files(canonical_root)

            for mirror_root in mirrors_for(skill_name):
                mirror = str(mirror_root.relative_to(ROOT))
                mirror_files = source_files(mirror_root)

                with self.subTest(mirror=mirror, check="file set"):
                    self.assertEqual(mirror_files, canonical_files)

                for relative_path in sorted(canonical_files):
                    mirror_file = mirror_root / relative_path
                    canonical_file = canonical_root / relative_path

                    with self.subTest(mirror=mirror, file=str(relative_path)):
                        self.assertEqual(
                            mirror_file.read_bytes(), canonical_file.read_bytes()
                        )

                    with self.subTest(mirror=mirror, mode=str(relative_path)):
                        # Git records only the owner-executable bit, so comparing
                        # the full mode would fail on a contributor's umask alone.
                        self.assertEqual(
                            bool(mirror_file.stat().st_mode & 0o100),
                            bool(canonical_file.stat().st_mode & 0o100),
                            f"executable bit differs for {relative_path}",
                        )


if __name__ == "__main__":
    unittest.main()
