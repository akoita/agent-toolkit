#!/usr/bin/env python3
"""Preview or safely apply Agent Toolkit policy to an agent instruction file."""

from __future__ import annotations

import argparse
import difflib
import os
import shutil
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path


POLICIES = {
    "codex": """## Orchestration policy

- Use `$codex-maestro` for non-trivial implementation and multi-step debugging.
- Keep requirements, architecture, planning, review, and publication in the
  root task; delegate only bounded work with disjoint ownership.
- Default to Balanced: use `gpt-5.6-sol` for the root orchestrator and
  demanding workers, and `gpt-5.6-terra` for economical read-heavy exploration.
- Handle trivial, localized, low-risk work directly.
- Escalate to Quality only for security-sensitive, architectural, migration,
  permissions, payments, public-contract, or highly ambiguous work.
- Keep subagent nesting disabled by default and avoid parallel write-heavy work
  unless file ownership and verification boundaries are disjoint.
- Follow the installed `codex-maestro` skill for the complete workflow.
- Do not delegate trivial work or pure analysis/review unnecessarily.""",
    "claude": """## Orchestration policy

- Use `/maestro` for non-trivial implementation work such as features, bug
  fixes, refactors, tests, configuration, or infrastructure.
- Keep analysis, design decisions, planning, review, and publication in the
  root session; delegate bounded implementation work as directed by the
  installed `maestro` skill.
- Use a few subagents for independent bounded work, agent teams only when
  workers must communicate, and dynamic workflows for large repeatable fan-out.
- Prefer documented model aliases and capability-based effort: `opus` at high
  effort for correctness-sensitive work and `sonnet` at medium or high effort
  for mechanical work.
- Do not orchestrate trivial edits, pure analysis or review, or tasks where the
  user explicitly requests direct implementation.
- Follow the installed `maestro` skill for worker selection, verification, and
  retry behavior.""",
}

START = "<!-- agent-toolkit:maestro-policy:start -->"
END = "<!-- agent-toolkit:maestro-policy:end -->"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=sorted(POLICIES), required=True)
    parser.add_argument("--scope", choices=("global", "project"), required=True)
    parser.add_argument(
        "--project-root",
        type=Path,
        help="Repository root; required only to override the current directory",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the previewed change; otherwise only print a diff",
    )
    return parser.parse_args()


def target_path(args: argparse.Namespace) -> Path:
    if args.scope == "project":
        root = (args.project_root or Path.cwd()).expanduser().resolve()
        if not root.is_dir():
            raise ValueError(f"Project root is not a directory: {root}")
        return root / ("AGENTS.md" if args.platform == "codex" else "CLAUDE.md")

    if args.project_root:
        raise ValueError("--project-root is valid only with --scope project")
    if args.platform == "codex":
        home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        return home.expanduser() / "AGENTS.md"
    return Path.home() / ".claude" / "CLAUDE.md"


def read_existing(path: Path) -> tuple[str, str]:
    if path.is_symlink():
        raise ValueError(f"Refusing to modify symlink: {path}")
    if path.exists() and not path.is_file():
        raise ValueError(f"Target exists but is not a regular file: {path}")
    if not path.exists():
        return "", "\n"
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Target is not valid UTF-8: {path}") from exc
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return text, newline


def managed_block(platform: str, newline: str) -> str:
    body = POLICIES[platform].replace("\n", newline)
    return f"{START}{newline}{body}{newline}{END}"


def updated_text(current: str, platform: str, newline: str) -> str:
    start_count = current.count(START)
    end_count = current.count(END)
    if start_count != end_count or start_count > 1:
        raise ValueError(
            "Malformed or duplicate Agent Toolkit markers; resolve manually first"
        )

    block = managed_block(platform, newline)
    if start_count == 1:
        start = current.index(START)
        end = current.index(END, start) + len(END)
        return current[:start] + block + current[end:]

    if not current:
        return block + newline
    separator = "" if current.endswith(newline * 2) else (
        newline if current.endswith(newline) else newline * 2
    )
    return current + separator + block + newline


def print_diff(path: Path, current: str, updated: str) -> None:
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=str(path),
        tofile=str(path),
    )
    print("".join(diff), end="")


def apply_atomic(path: Path, current: str, updated: str) -> Path | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    original_mode = None
    if path.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(f"{path.name}.agent-toolkit-backup-{stamp}")
        shutil.copy2(path, backup)
        if backup.read_bytes() != path.read_bytes():
            raise RuntimeError(f"Backup verification failed: {backup}")
        original_mode = stat.S_IMODE(path.stat().st_mode)

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        if original_mode is not None:
            temp_path.chmod(original_mode)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

    if path.read_bytes().decode("utf-8") != updated:
        raise RuntimeError(f"Post-write verification failed: {path}")
    return backup


def main() -> int:
    args = parse_args()
    try:
        path = target_path(args)
        current, newline = read_existing(path)
        updated = updated_text(current, args.platform, newline)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc

    print(f"Target: {path}")
    if current == updated:
        print("No change required.")
        return 0

    print_diff(path, current, updated)
    if not args.apply:
        print("Preview only. Rerun with --apply after explicit approval.")
        return 0

    backup = apply_atomic(path, current, updated)
    print(f"Applied: {path}")
    if backup:
        print(f"Backup: {backup}")
    else:
        print("Created a new instruction file; no backup was needed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
