#!/usr/bin/env python3
"""Install Codex Maestro and its Luna worker for the current user."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


SKILL_NAME = "codex-maestro"
AGENT_FILENAME = "luna-worker.toml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=Path.home() / ".agents" / "skills",
        help="Personal Agent Skills directory (default: ~/.agents/skills)",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
        help="Codex home containing agents/ (default: $CODEX_HOME or ~/.codex)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--skill-only", action="store_true")
    mode.add_argument("--agent-only", action="store_true")
    parser.add_argument(
        "--link",
        action="store_true",
        help="Symlink the skill source instead of copying it",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing installation",
    )
    return parser.parse_args()


def remove_existing(path: Path, force: bool) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if not force:
        raise FileExistsError(f"{path} already exists; rerun with --force")
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def install_skill(source: Path, destination: Path, link: bool, force: bool) -> None:
    source = source.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.resolve() == source:
        print(f"Skill already runs from {source}")
        return
    remove_existing(destination, force)
    if link:
        destination.symlink_to(source, target_is_directory=True)
        action = "Linked"
    else:
        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns("__pycache__", "*.py[co]"),
        )
        action = "Installed"
    print(f"{action} skill: {destination}")


def install_agent(template: Path, destination: Path, force: bool) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    remove_existing(destination, force)
    shutil.copy2(template, destination)
    print(f"Installed Luna worker: {destination}")


def main() -> int:
    args = parse_args()
    skill_source = Path(__file__).resolve().parents[1]
    agent_template = skill_source / "references" / "luna-worker.toml"

    if not args.agent_only:
        install_skill(
            skill_source,
            args.skills_root.expanduser() / SKILL_NAME,
            args.link,
            args.force,
        )
    if not args.skill_only:
        install_agent(
            agent_template,
            args.codex_home.expanduser() / "agents" / AGENT_FILENAME,
            args.force,
        )
    print("Restart Codex or start a new task so it discovers the installation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
