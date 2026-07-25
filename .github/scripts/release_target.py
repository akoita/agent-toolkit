#!/usr/bin/env python3
"""Decide whether the merge commit on main should produce a release.

Writes GitHub Actions outputs: `release` (true/false) and `version`.
"""

from __future__ import annotations

import os
import sys

from plugin_versions import current_version, discover_packages, git, version_at


def emit(**outputs: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    lines = [f"{key}={value}" for key, value in outputs.items()]
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    for line in lines:
        print(line)


def main() -> int:
    packages = discover_packages()
    if not packages:
        print("No plugin packages found.")
        emit(release="false", version="")
        return 0

    head_versions = {
        package: current_version(manifest) for package, manifest in packages.items()
    }
    distinct = set(head_versions.values())
    if len(distinct) > 1:
        # This repository releases its plugins in lockstep so that one
        # repository tag is unambiguous. Diverged versions need a deliberate
        # per-plugin tagging scheme, so stop rather than guess a tag name.
        print("Plugin versions have diverged; refusing to guess a release tag:")
        for package, version in sorted(head_versions.items()):
            print(f"  {package}: {version}")
        print("Tag each plugin explicitly, or restore lockstep versioning.")
        emit(release="false", version="")
        return 1

    version = distinct.pop()
    previous = {
        package: version_at("HEAD~1", manifest)
        for package, manifest in packages.items()
    }
    if all(previous.get(package) == version for package in packages):
        print(f"Version unchanged at {version}; no release.")
        emit(release="false", version=version)
        return 0

    tag = f"v{version}"
    existing = git("tag", "--list", tag)
    if existing:
        print(f"Tag {tag} already exists; no release.")
        emit(release="false", version=version)
        return 0

    print(f"Version changed to {version}; releasing {tag}.")
    emit(release="true", version=version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
