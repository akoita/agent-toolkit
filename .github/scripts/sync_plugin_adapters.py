#!/usr/bin/env python3
"""Generate native security plugin adapters from the portable package.

The Agent Plugins manifest owns portable metadata and repository-specific
adapter data. This script renders the Claude and Codex native manifests and
replaces only their matching marketplace entries, leaving unrelated entries
untouched.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXTENSION_NAMESPACE = "io.github.akoita.agent-toolkit"
PORTABLE_MANIFEST = Path("plugins/portable/security/plugin.json")
CLAUDE_MANIFEST = Path("plugins/claude/security/.claude-plugin/plugin.json")
CODEX_MANIFEST = Path("plugins/codex/codex-security/.codex-plugin/plugin.json")
CLAUDE_MARKETPLACE = Path(".claude-plugin/marketplace.json")
CODEX_MARKETPLACE = Path(".agents/plugins/marketplace.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report generated-file drift and exit non-zero instead of writing",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def replace_marketplace_entry(
    catalog: dict[str, Any], name: str, replacement: dict[str, Any]
) -> dict[str, Any]:
    entries = catalog.get("plugins")
    if not isinstance(entries, list):
        raise ValueError("marketplace catalog must contain a plugins array")

    if any(not isinstance(entry, dict) for entry in entries):
        raise ValueError("marketplace plugins entries must be objects")
    matches = [
        index for index, entry in enumerate(entries) if entry.get("name") == name
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one marketplace entry named {name!r}, found {len(matches)}"
        )
    entries[matches[0]] = replacement
    return catalog


def rendered_outputs(root: Path = ROOT) -> dict[Path, bytes]:
    portable = load_json(root / PORTABLE_MANIFEST)
    try:
        adapters = portable["extensions"][EXTENSION_NAMESPACE]["adapters"]
        claude = adapters["claude"]
        codex = adapters["codex"]
    except (KeyError, TypeError) as error:
        raise ValueError("portable manifest is missing native adapter metadata") from error

    version = portable["version"]
    repository = portable["repository"]
    author = portable["author"]

    claude_manifest = {
        "name": claude["name"],
        "version": version,
        "description": claude["description"],
        "author": {"name": author["name"]},
        "repository": repository,
    }
    codex_manifest = {
        "name": codex["name"],
        "version": version,
        "description": codex["description"],
        "author": author,
        "homepage": portable["homepage"],
        "repository": repository,
        "keywords": portable["keywords"],
        "skills": "./skills/",
        "interface": codex["interface"],
    }

    claude_entry = {
        "name": claude["name"],
        **claude["marketplace"],
        "version": version,
    }
    # Keep the established Claude catalog field order stable.
    claude_entry = {
        "name": claude_entry["name"],
        "source": claude_entry["source"],
        "version": claude_entry["version"],
        "description": claude_entry["description"],
    }
    codex_entry = {"name": codex["name"], **codex["marketplace"]}

    claude_catalog = replace_marketplace_entry(
        load_json(root / CLAUDE_MARKETPLACE), claude["name"], claude_entry
    )
    codex_catalog = replace_marketplace_entry(
        load_json(root / CODEX_MARKETPLACE), codex["name"], codex_entry
    )

    return {
        CLAUDE_MANIFEST: json_bytes(claude_manifest),
        CODEX_MANIFEST: json_bytes(codex_manifest),
        CLAUDE_MARKETPLACE: json_bytes(claude_catalog),
        CODEX_MARKETPLACE: json_bytes(codex_catalog),
    }


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    drifted = False

    try:
        outputs = rendered_outputs(root)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    for relative, expected in outputs.items():
        target = root / relative
        actual = target.read_bytes() if target.is_file() else None
        if actual == expected:
            print(f"{relative}: in sync")
            continue

        drifted = True
        if args.check:
            print(f"{relative}: out of sync")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)
            print(f"{relative}: synchronized")

    if args.check and drifted:
        print("\nRun `python .github/scripts/sync_plugin_adapters.py` to update adapters.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
