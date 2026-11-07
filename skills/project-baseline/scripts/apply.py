#!/usr/bin/env python3
"""Apply the mechanical baseline practices to a project, or record decisions.

Dry run by default: prints the unified diff of every change and writes
nothing. Pass --write to apply exactly what the dry run showed.

    python3 apply.py PROJECT --practice claude-imports-agents --practice toolkit-plugins
    python3 apply.py PROJECT --adopt feature-catalog
    python3 apply.py PROJECT --decline docs-check-ci --reason "Checked by the docs site build."
    python3 apply.py PROJECT ... --write

Mechanical practices: claude-imports-agents (create CLAUDE.md, or add the
@AGENTS.md import to it) and toolkit-plugins (add the agent-toolkit
marketplace and enable the utilities and baseline plugins in
.claude/settings.json, keeping every existing setting). Other practices need
judgment or their owning skill; asking for one prints its fix instead.
Decisions go to .agent-toolkit/baseline.json. Uses only the standard library.
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import json
import subprocess
import sys
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parents[1] / "references" / "practices.json"
RECORD_PATH = Path(".agent-toolkit") / "baseline.json"
MARKETPLACE = "agent-toolkit"
MARKETPLACE_SOURCE = {"source": "github", "repo": "akoita/agent-toolkit"}
PLUGINS = ("utilities@agent-toolkit", "baseline@agent-toolkit")
IMPORT_LINE = "@AGENTS.md"
NEW_CLAUDE_MD = (
    "# Claude Code instructions\n\n"
    "@AGENTS.md\n\n"
    "`AGENTS.md` is the canonical instruction file. Keep shared guidance there\n"
    "so Claude Code and other coding agents follow the same rules.\n"
)


def read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


def catalog() -> dict[str, dict[str, str]]:
    practices = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["practices"]
    return {practice["id"]: practice for practice in practices}


def claude_md(text: str | None) -> str:
    """Return CLAUDE.md text that imports AGENTS.md."""
    if text is None or not text.strip():
        return NEW_CLAUDE_MD
    lines = text.splitlines(keepends=True)
    if any(line.strip() == IMPORT_LINE for line in lines):
        return text
    if lines and lines[0].startswith("# "):
        return lines[0] + "\n" + IMPORT_LINE + "\n" + "".join(lines[1:])
    return IMPORT_LINE + "\n\n" + text


def settings(text: str | None) -> str:
    """Return settings.json text with the marketplace and both plugins enabled."""
    value = json.loads(text) if text and text.strip() else {}
    if not isinstance(value, dict):
        raise ValueError(".claude/settings.json must hold a JSON object")
    marketplaces = value.setdefault("extraKnownMarketplaces", {})
    marketplaces.setdefault(MARKETPLACE, {"source": dict(MARKETPLACE_SOURCE)})
    enabled = value.setdefault("enabledPlugins", {})
    for plugin in PLUGINS:
        enabled.setdefault(plugin, True)
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def record(text: str | None, decisions: dict[str, dict[str, str]]) -> str:
    """Return baseline.json text with the given decisions merged in."""
    value = json.loads(text) if text and text.strip() else {}
    if not isinstance(value, dict):
        raise ValueError(f"{RECORD_PATH} must hold a JSON object")
    value.setdefault("schema_version", 1)
    stored = value.setdefault("decisions", {})
    stored.update(decisions)
    value["decisions"] = dict(sorted(stored.items()))
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def settings_ignored(root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", ".claude/settings.json"],
            cwd=root,
            capture_output=True,
        )
    except OSError:
        return False
    return result.returncode == 0


def diff(root: Path, path: Path, old: str | None, new: str) -> str:
    name = path.relative_to(root).as_posix()
    return "".join(
        difflib.unified_diff(
            (old or "").splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{name}" if old is not None else "/dev/null",
            tofile=f"b/{name}",
        )
    )


def plan(root: Path, args: argparse.Namespace) -> tuple[dict[Path, tuple[str | None, str]], list[str]]:
    practices = catalog()
    changes: dict[Path, tuple[str | None, str]] = {}
    notes: list[str] = []
    for practice in args.practice:
        if practice not in practices:
            raise ValueError(f"unknown practice: {practice}")
        if practice == "claude-imports-agents":
            path = root / "CLAUDE.md"
            old = read(path)
            changes[path] = (old, claude_md(old))
            if read(root / "AGENTS.md") is None:
                notes.append("AGENTS.md does not exist yet; write it before relying on the import.")
        elif practice == "toolkit-plugins":
            path = root / ".claude" / "settings.json"
            old = read(path)
            changes[path] = (old, settings(old))
            if settings_ignored(root):
                notes.append(
                    ".claude/settings.json is git-ignored; ignore `.claude/*` and add "
                    "`!.claude/settings.json` so the setting is shared."
                )
        else:
            entry = practices[practice]
            notes.append(f"{practice} is not mechanical; use {entry['owner']}: {entry['fix']}")

    today = datetime.date.today().isoformat()
    decisions: dict[str, dict[str, str]] = {}
    for practice in args.adopt:
        decisions[practice] = {"decision": "adopt", "date": today}
    for practice in args.decline:
        decisions[practice] = {"decision": "decline", "reason": args.reason, "date": today}
    unknown = [practice for practice in decisions if practice not in practices]
    if unknown:
        raise ValueError("unknown practice: " + ", ".join(unknown))
    if decisions:
        path = root / RECORD_PATH
        old = read(path)
        changes[path] = (old, record(old, decisions))
    return changes, notes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", type=Path)
    parser.add_argument("--practice", action="append", default=[], metavar="ID")
    parser.add_argument("--adopt", action="append", default=[], metavar="ID")
    parser.add_argument("--decline", action="append", default=[], metavar="ID")
    parser.add_argument("--reason", help="why the declined practices do not fit")
    parser.add_argument("--write", action="store_true", help="apply the changes")
    args = parser.parse_args(argv)

    root = args.project.resolve()
    if not root.is_dir():
        parser.error(f"{args.project} is not a directory")
    if args.decline and not (args.reason and args.reason.strip()):
        parser.error("--decline needs --reason")
    if not (args.practice or args.adopt or args.decline):
        parser.error("name at least one --practice, --adopt or --decline")
    try:
        changes, notes = plan(root, args)
    except (ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    for note in notes:
        print(f"note: {note}", file=sys.stderr)
    pending = {path: pair for path, pair in changes.items() if pair[0] != pair[1]}
    if not pending:
        print("Nothing to change.")
        return 0
    for path, (old, new) in pending.items():
        print(diff(root, path, old, new), end="")
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
