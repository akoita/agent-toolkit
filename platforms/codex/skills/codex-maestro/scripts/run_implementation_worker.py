#!/usr/bin/env python3
"""Run or resume a configurable implementation worker through Codex CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "gpt-5.6"
DEFAULT_EFFORT = "medium"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", required=True, type=Path)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--session-file", type=Path)
    resume = parser.add_mutually_exclusive_group()
    resume.add_argument("--resume", metavar="SESSION_ID")
    resume.add_argument("--resume-last", action="store_true")
    parser.add_argument(
        "--model",
        default=os.environ.get("CODEX_MAESTRO_WORKER_MODEL", DEFAULT_MODEL),
        help=(
            "Codex model (default: $CODEX_MAESTRO_WORKER_MODEL or "
            f"{DEFAULT_MODEL})"
        ),
    )
    parser.add_argument(
        "--effort",
        default=os.environ.get("CODEX_MAESTRO_WORKER_EFFORT", DEFAULT_EFFORT),
        help=(
            "Reasoning effort (default: $CODEX_MAESTRO_WORKER_EFFORT or "
            f"{DEFAULT_EFFORT})"
        ),
    )
    parser.add_argument(
        "--sandbox",
        choices=("read-only", "workspace-write", "danger-full-access"),
        default="workspace-write",
    )
    return parser.parse_args()


def find_session_id(event: Any) -> str | None:
    if not isinstance(event, dict):
        return None
    if event.get("type") in {"thread.started", "session.started"}:
        for key in ("thread_id", "session_id", "threadId", "sessionId"):
            value = event.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def main() -> int:
    args = parse_args()
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex CLI was not found on PATH")

    prompt_path = args.prompt.expanduser().resolve()
    cwd = args.cwd.expanduser().resolve()
    if not prompt_path.is_file():
        raise SystemExit(f"prompt file does not exist: {prompt_path}")
    if not cwd.is_dir():
        raise SystemExit(f"working directory does not exist: {cwd}")

    command = [codex, "exec"]
    if args.resume or args.resume_last:
        command.append("resume")
    command.extend(
        [
            "--model",
            args.model,
            "--config",
            f'model_reasoning_effort="{args.effort}"',
        ]
    )
    if not (args.resume or args.resume_last):
        command.extend(["--sandbox", args.sandbox])
    if args.output:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        command.extend(["--output-last-message", str(output)])

    capture_session = args.session_file is not None and not (
        args.resume or args.resume_last
    )
    if capture_session:
        command.append("--json")
    if args.resume:
        command.append(args.resume)
    elif args.resume_last:
        command.append("--last")
    command.append("-")

    prompt = prompt_path.read_text(encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE if capture_session else None,
        stderr=None,
        text=True,
    )
    session_id: str | None = None
    if capture_session:
        assert process.stdin is not None
        assert process.stdout is not None
        process.stdin.write(prompt)
        process.stdin.close()
        for line in process.stdout:
            sys.stdout.write(line)
            try:
                session_id = session_id or find_session_id(json.loads(line))
            except json.JSONDecodeError:
                pass
        return_code = process.wait()
    else:
        process.communicate(prompt)
        return_code = process.returncode

    if return_code == 0 and args.session_file and session_id:
        session_file = args.session_file.expanduser().resolve()
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(session_id + "\n", encoding="utf-8")
        print(f"Recorded worker session: {session_file}")
    elif return_code == 0 and capture_session:
        print(
            "Warning: Codex completed but no worker session ID was found.",
            file=sys.stderr,
        )
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
