#!/usr/bin/env python3
"""Synchronize generated plugin payloads with their canonical platform sources."""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IGNORED_DIRECTORY_NAMES = {"__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


@dataclass(frozen=True)
class Payload:
    source: Path
    destination: Path


PAYLOADS = (
    Payload(
        ROOT / "platforms" / "claude" / "skills" / "maestro",
        ROOT / "plugins" / "claude" / "maestro" / "skills" / "maestro",
    ),
    Payload(
        ROOT / "platforms" / "claude" / "agents",
        ROOT / "plugins" / "claude" / "maestro" / "agents",
    ),
    Payload(
        ROOT / "platforms" / "codex" / "skills" / "codex-maestro",
        ROOT
        / "plugins"
        / "codex"
        / "codex-maestro"
        / "skills"
        / "codex-maestro",
    ),
)


def ignored(path: Path) -> bool:
    return any(part in IGNORED_DIRECTORY_NAMES for part in path.parts) or (
        path.suffix in IGNORED_SUFFIXES
    )


def files_in(root: Path) -> dict[Path, bytes]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not ignored(path.relative_to(root))
    }


def differences(payload: Payload) -> list[str]:
    source_files = files_in(payload.source)
    destination_files = files_in(payload.destination)
    messages: list[str] = []
    for relative_path in sorted(source_files.keys() - destination_files.keys()):
        messages.append(f"missing {payload.destination / relative_path}")
    for relative_path in sorted(destination_files.keys() - source_files.keys()):
        messages.append(f"unexpected {payload.destination / relative_path}")
    for relative_path in sorted(source_files.keys() & destination_files.keys()):
        if source_files[relative_path] != destination_files[relative_path]:
            messages.append(f"modified {payload.destination / relative_path}")
    return messages


def copy_payload(payload: Payload) -> None:
    if not payload.source.is_dir():
        raise FileNotFoundError(f"canonical source does not exist: {payload.source}")
    if payload.destination.exists():
        shutil.rmtree(payload.destination)
    payload.destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        payload.source,
        payload.destination,
        ignore=shutil.ignore_patterns(
            "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", "*.py[co]"
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift without changing generated plugin payloads",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        drift = [message for payload in PAYLOADS for message in differences(payload)]
        if drift:
            print("Plugin payloads are out of sync:")
            for message in drift:
                print(f"- {message}")
            print("Run `python scripts/sync_plugin_packages.py` to refresh them.")
            return 1
        print("Plugin payloads match their canonical platform sources.")
        return 0

    for payload in PAYLOADS:
        copy_payload(payload)
        print(f"Synchronized {payload.source.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
