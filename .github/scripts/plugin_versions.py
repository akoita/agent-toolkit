#!/usr/bin/env python3
"""Shared helpers for the version gate and the release workflow.

Plugin packages are discovered from the tree rather than listed here, so adding
a skill needs no change to the release automation.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_GLOBS = (
    "plugins/*/*/.*-plugin/plugin.json",
    "plugins/portable/*/plugin.json",
)


def discover_packages(root: Path = ROOT) -> dict[str, str]:
    """Map each package directory to its manifest, both repo-relative."""
    packages = {}
    manifests = sorted(
        manifest for pattern in MANIFEST_GLOBS for manifest in root.glob(pattern)
    )
    for manifest in manifests:
        if manifest.parent.name in {".claude-plugin", ".codex-plugin"}:
            package = manifest.parent.parent
        else:
            package = manifest.parent
        packages[str(package.relative_to(root))] = str(manifest.relative_to(root))
    return packages


def git(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def changed_files(base: str, head: str = "HEAD") -> list[str]:
    output = git("diff", "--name-only", f"{base}...{head}")
    return [line for line in output.splitlines() if line]


def version_at(ref: str, manifest: str) -> str | None:
    """Version recorded at a ref, or None when the manifest did not exist."""
    try:
        return json.loads(git("show", f"{ref}:{manifest}"))["version"]
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        return None


def current_version(manifest: str, root: Path = ROOT) -> str:
    return json.loads((root / manifest).read_text(encoding="utf-8"))["version"]


def packages_needing_bump(
    changed: list[str],
    packages: dict[str, str],
    base_versions: dict[str, str | None],
    head_versions: dict[str, str],
) -> list[str]:
    """Packages whose files changed while their declared version did not.

    A package with no recorded base version is new, so it needs no bump.
    """
    stale = []
    for package, _manifest in packages.items():
        touched = any(
            path == package or path.startswith(f"{package}/") for path in changed
        )
        if not touched:
            continue
        base = base_versions.get(package)
        if base is None:
            continue
        if base == head_versions[package]:
            stale.append(package)
    return stale
