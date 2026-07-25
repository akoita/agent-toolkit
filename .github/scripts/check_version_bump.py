#!/usr/bin/env python3
"""Fail when a plugin package changes without a version bump.

Installed packages are cached by version on both platforms, so content shipped
under an unchanged version can be ignored by an existing installation. This gate
makes that failure impossible to merge instead of easy to forget.
"""

from __future__ import annotations

import argparse
import sys

from plugin_versions import (
    changed_files,
    current_version,
    discover_packages,
    packages_needing_bump,
    version_at,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        required=True,
        help="Base ref to compare against, e.g. origin/main",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packages = discover_packages()
    if not packages:
        print("No plugin packages found; nothing to check.")
        return 0

    changed = changed_files(args.base)
    base_versions = {
        package: version_at(args.base, manifest)
        for package, manifest in packages.items()
    }
    head_versions = {
        package: current_version(manifest) for package, manifest in packages.items()
    }

    stale = packages_needing_bump(changed, packages, base_versions, head_versions)
    if not stale:
        print("Version gate passed.")
        for package, manifest in packages.items():
            touched = any(
                path == package or path.startswith(f"{package}/") for path in changed
            )
            state = "bumped" if touched else "unchanged"
            print(f"  {package}: {head_versions[package]} ({state})")
        return 0

    print("Version gate failed.\n")
    for package in stale:
        manifest = packages[package]
        print(
            f"  {package} changed but {manifest} still declares "
            f"{head_versions[package]}."
        )
    print(
        "\nBump the version in each manifest above, and the matching entry in\n"
        ".claude-plugin/marketplace.json where the Claude catalog carries one.\n"
        "Both platforms cache packages by version, so an unchanged version lets\n"
        "an existing installation ignore this release. See docs/contributing.md."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
