#!/usr/bin/env python3
"""Generate native plugin adapters from portable packages.

Each Agent Plugins manifest owns portable metadata and repository-specific
adapter data. This script renders only the native adapters declared by each
package and replaces only their matching marketplace entries, leaving
unrelated entries untouched.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
EXTENSION_NAMESPACE = "io.github.akoita.agent-toolkit"
PORTABLE_MANIFESTS = (
    Path("plugins/portable/codex-maestro/plugin.json"),
    Path("plugins/portable/security/plugin.json"),
)
CLAUDE_MARKETPLACE = Path(".claude-plugin/marketplace.json")
CODEX_MARKETPLACE = Path(".agents/plugins/marketplace.json")
MARKETPLACES = {
    "claude": CLAUDE_MARKETPLACE,
    "codex": CODEX_MARKETPLACE,
}
PACKAGE_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


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


def adapter_package_path(kind: str, adapter: dict[str, Any]) -> Path:
    source = adapter["marketplace"]["source"]
    if kind == "claude" and isinstance(source, str):
        source_path = source
    elif (
        kind == "codex"
        and isinstance(source, dict)
        and source.get("source") == "local"
        and isinstance(source.get("path"), str)
    ):
        source_path = source["path"]
    else:
        raise ValueError(f"unsupported {kind} marketplace source")
    components = source_path.split("/")
    package_name = components[3] if len(components) == 4 else ""
    if (
        len(components) != 4
        or components[:3] != [".", "plugins", kind]
        or PACKAGE_NAME.fullmatch(package_name) is None
        or adapter.get("name") != package_name
    ):
        raise ValueError(
            f"{kind} adapter must target its matching "
            f"plugins/{kind}/<package-name>: {source_path}"
        )
    return Path(*components[1:])


def native_manifest(
    kind: str, portable: dict[str, Any], adapter: dict[str, Any]
) -> dict[str, Any]:
    common = {
        "name": adapter["name"],
        "version": portable["version"],
        "description": adapter["description"],
    }
    if kind == "claude":
        return {
            **common,
            "author": {"name": portable["author"]["name"]},
            "repository": portable["repository"],
        }
    if kind == "codex":
        return {
            **common,
            "author": portable["author"],
            "homepage": portable["homepage"],
            "repository": portable["repository"],
            "keywords": portable["keywords"],
            "skills": "./skills/",
            "interface": adapter["interface"],
        }
    raise ValueError(f"unsupported adapter kind: {kind}")


def marketplace_entry(
    kind: str, portable: dict[str, Any], adapter: dict[str, Any]
) -> dict[str, Any]:
    if kind == "claude":
        marketplace = adapter["marketplace"]
        # Keep the established Claude catalog field order stable.
        return {
            "name": adapter["name"],
            "source": marketplace["source"],
            "version": portable["version"],
            "description": marketplace["description"],
        }
    if kind == "codex":
        return {"name": adapter["name"], **adapter["marketplace"]}
    raise ValueError(f"unsupported adapter kind: {kind}")


def rendered_outputs(root: Path = ROOT) -> dict[Path, bytes]:
    catalogs = {
        kind: load_json(root / path) for kind, path in MARKETPLACES.items()
    }
    manifests: dict[Path, bytes] = {}

    for relative in PORTABLE_MANIFESTS:
        portable = load_json(root / relative)
        try:
            adapters = portable["extensions"][EXTENSION_NAMESPACE]["adapters"]
        except (KeyError, TypeError) as error:
            raise ValueError(
                f"portable manifest is missing native adapter metadata: {relative}"
            ) from error
        if not isinstance(adapters, dict) or not adapters:
            raise ValueError(f"portable manifest declares no native adapters: {relative}")

        for kind, adapter in adapters.items():
            if kind not in MARKETPLACES or not isinstance(adapter, dict):
                raise ValueError(f"unsupported adapter kind: {kind}")
            package = adapter_package_path(kind, adapter)
            manifest_dir = f".{kind}-plugin"
            manifest_path = package / manifest_dir / "plugin.json"
            if manifest_path in manifests:
                raise ValueError(f"duplicate generated manifest: {manifest_path}")
            manifests[manifest_path] = json_bytes(
                native_manifest(kind, portable, adapter)
            )
            replace_marketplace_entry(
                catalogs[kind],
                adapter["name"],
                marketplace_entry(kind, portable, adapter),
            )

    return {
        **manifests,
        **{
            MARKETPLACES[kind]: json_bytes(catalog)
            for kind, catalog in catalogs.items()
        },
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
