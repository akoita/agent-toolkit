#!/usr/bin/env python3
"""Install or update the shared writing policy in a project.

Writes the skill's canonical block (assets/agents-writing-policy.md) into the
project's AGENTS.md between two markers, and enables the agent-toolkit
utilities plugin in .claude/settings.json so Claude Code loads the full guide.

    python3 install_policy.py [PROJECT]            # show what would change
    python3 install_policy.py [PROJECT] --write    # apply it
    python3 install_policy.py [PROJECT] --check    # exit 1 if out of date

Text outside the markers is never changed. When AGENTS.md has no markers yet,
an existing "## Writing documentation" section is replaced by the marked
block; otherwise the block is appended. Existing settings are kept. Uses only
the standard library.
"""

from __future__ import annotations

import argparse
import difflib
import json
import subprocess
import sys
from pathlib import Path

START = "<!-- agent-toolkit:writing-policy -->"
END = "<!-- /agent-toolkit:writing-policy -->"
LEGACY_HEADING = "## Writing documentation"
BLOCK_PATH = Path(__file__).resolve().parents[1] / "assets" / "agents-writing-policy.md"

MARKETPLACE = "agent-toolkit"
MARKETPLACE_SOURCE = {"source": "github", "repo": "akoita/agent-toolkit"}
PLUGIN = "utilities@agent-toolkit"


def canonical_block() -> str:
    body = BLOCK_PATH.read_text(encoding="utf-8").strip("\n")
    return f"{START}\n\n{body}\n\n{END}\n"


def update_agents(text: str, block: str) -> str:
    """Return AGENTS.md text with the marked block installed or refreshed."""
    if START in text and END in text:
        before, rest = text.split(START, 1)
        _, after = rest.split(END, 1)
        return before + block.rstrip("\n") + after

    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.rstrip() == LEGACY_HEADING:
            end = index + 1
            while end < len(lines) and not lines[end].startswith("## "):
                end += 1
            trailing = "\n" if end < len(lines) else ""
            return "".join(lines[:index]) + block + trailing + "".join(lines[end:])

    if not text.strip():
        return "# Working instructions\n\n" + block
    return text.rstrip("\n") + "\n\n" + block


def update_settings(text: str | None) -> str:
    """Return settings.json text with the marketplace and plugin enabled."""
    settings = json.loads(text) if text and text.strip() else {}
    if not isinstance(settings, dict):
        raise ValueError(".claude/settings.json must hold a JSON object")
    marketplaces = settings.setdefault("extraKnownMarketplaces", {})
    marketplaces.setdefault(MARKETPLACE, {"source": dict(MARKETPLACE_SOURCE)})
    plugins = settings.setdefault("enabledPlugins", {})
    plugins.setdefault(PLUGIN, True)
    return json.dumps(settings, indent=2, ensure_ascii=False) + "\n"


def read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.exists() else None


def diff(path: Path, old: str | None, new: str, root: Path) -> str:
    name = path.relative_to(root).as_posix()
    return "".join(
        difflib.unified_diff(
            (old or "").splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{name}" if old is not None else "/dev/null",
            tofile=f"b/{name}",
        )
    )


def warnings(root: Path) -> list[str]:
    notes = []
    claude_md = root / "CLAUDE.md"
    if claude_md.exists() and "AGENTS.md" not in claude_md.read_text(encoding="utf-8"):
        notes.append("CLAUDE.md does not import AGENTS.md; add a line `@AGENTS.md`.")
    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".claude/settings.json"],
            cwd=root,
            capture_output=True,
        ).returncode == 0
    except OSError:
        ignored = False
    if ignored:
        notes.append(
            ".claude/settings.json is git-ignored; ignore `.claude/*` and add "
            "`!.claude/settings.json` so the setting is shared."
        )
    return notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", nargs="?", default=".", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="apply the changes")
    mode.add_argument(
        "--check", action="store_true", help="exit 1 when the project is out of date"
    )
    parser.add_argument(
        "--no-settings", action="store_true", help="leave .claude/settings.json alone"
    )
    args = parser.parse_args(argv)

    root = args.project.resolve()
    if not root.is_dir():
        parser.error(f"{args.project} is not a directory")

    agents_path = root / "AGENTS.md"
    settings_path = root / ".claude" / "settings.json"
    old_agents = read(agents_path)
    changes = {agents_path: (old_agents, update_agents(old_agents or "", canonical_block()))}
    if not args.no_settings:
        old_settings = read(settings_path)
        try:
            changes[settings_path] = (old_settings, update_settings(old_settings))
        except (ValueError, json.JSONDecodeError) as error:
            print(f"Cannot update {settings_path}: {error}", file=sys.stderr)
            return 2

    pending = {path: pair for path, pair in changes.items() if pair[0] != pair[1]}
    for note in warnings(root):
        print(f"warning: {note}", file=sys.stderr)

    if not pending:
        print("The writing policy is up to date.")
        return 0
    if args.check:
        names = ", ".join(path.relative_to(root).as_posix() for path in pending)
        print(f"The writing policy is out of date in: {names}")
        return 1
    for path, (old, new) in pending.items():
        print(diff(path, old, new, root), end="")
    if args.write:
        for path, (_, new) in pending.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8")
        print(f"\nUpdated {len(pending)} file(s).")
    else:
        print("\nDry run: re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
