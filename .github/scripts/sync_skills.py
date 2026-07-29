#!/usr/bin/env python3
"""Synchronize every generated skill mirror with its canonical source.

The skills CLI discovers skills from a top-level `skills/` directory by
default, and does not follow symlinks, so the catalog has to be a real copy.
The catalog is not the only mirror: the security skills are also copied into
the Codex package, which ships the same skill bodies as the Claude plugin they
are authored in. This script performs those copies so contributors do not have
to remember which files moved. `tests/test_skills_cli_catalog.py` verifies the
result.
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CATALOG_ROOT = ROOT / "skills"
CLAUDE_SECURITY_SKILLS = ROOT / "plugins" / "claude" / "security" / "skills"
CODEX_SECURITY_SKILLS = ROOT / "plugins" / "codex" / "codex-security" / "skills"
# Authored once in the Claude plugin, shipped by the Codex package too.
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
        ROOT / "plugins" / "codex" / "codex-maestro" / "skills" / "codex-maestro"
    ),
    "setup-agent-toolkit": ROOT / "tools" / "setup-agent-toolkit",
    **{name: CLAUDE_SECURITY_SKILLS / name for name in SECURITY_SKILLS},
}
IGNORED_DIRECTORY_NAMES = {"__pycache__"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def mirrors_for(name: str) -> list[Path]:
    """Every generated copy of a canonical skill, in reporting order."""
    mirrors = [CATALOG_ROOT / name]
    if name in SECURITY_SKILLS:
        mirrors.append(CODEX_SECURITY_SKILLS / name)
    return mirrors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report drift and exit non-zero instead of writing",
    )
    return parser.parse_args()


def source_files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in IGNORED_DIRECTORY_NAMES for part in path.parts)
        and path.suffix not in IGNORED_SUFFIXES
    }


def is_executable(path: Path) -> bool:
    """Whether git would record this file as mode 100755.

    Git tracks only the owner-executable bit, not full permissions, so
    comparing the whole mode would fail on nothing more than a contributor's
    umask.
    """
    return bool(path.stat().st_mode & 0o100)


def differences(canonical: Path, mirror: Path) -> list[str]:
    """Human-readable drift between a canonical skill and its mirror."""
    canonical_files = source_files(canonical)
    mirror_files = source_files(mirror) if mirror.exists() else set()

    drift = []
    for relative in sorted(canonical_files - mirror_files):
        drift.append(f"missing: {relative}")
    for relative in sorted(mirror_files - canonical_files):
        drift.append(f"extra: {relative}")
    for relative in sorted(canonical_files & mirror_files):
        source, target = canonical / relative, mirror / relative
        if not filecmp.cmp(source, target, shallow=False):
            drift.append(f"content: {relative}")
        elif is_executable(source) != is_executable(target):
            drift.append(f"mode: {relative}")
    return drift


def sync(canonical: Path, mirror: Path) -> None:
    if mirror.exists():
        shutil.rmtree(mirror)
    shutil.copytree(
        canonical,
        mirror,
        ignore=shutil.ignore_patterns(*IGNORED_DIRECTORY_NAMES, "*.py[co]"),
    )


def main() -> int:
    args = parse_args()
    drifted = False

    for name, canonical in sorted(CANONICAL_SKILLS.items()):
        if not canonical.is_dir():
            print(f"error: canonical source missing for {name}: {canonical}")
            return 1

        for mirror in mirrors_for(name):
            label = mirror.relative_to(ROOT)
            drift = differences(canonical, mirror)
            if not drift:
                print(f"{label}: in sync")
                continue

            drifted = True
            if args.check:
                print(f"{label}: out of sync")
                for entry in drift:
                    print(f"  {entry}")
            else:
                sync(canonical, mirror)
                print(f"{label}: synchronized ({len(drift)} change(s))")

    if args.check and drifted:
        print("\nRun `python .github/scripts/sync_skills.py` to update the mirrors.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
