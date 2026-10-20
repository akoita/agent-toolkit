#!/usr/bin/env python3
"""Prepare and police the agent review of flagged authority sources.

The source-review workflow (ADR 0003, stage 3) lets an agent re-read only the
sources `check_sources.py` flags and propose a draft pull request. The agent
reads untrusted third-party content, so its output is checked here by code it
cannot modify before anything is committed:

- `select` turns a `check_sources.py --json` report into the agent's brief;
- `verify` rejects a proposed patch that touches anything but skill markdown,
  package manifests, catalogs, and the source manifest, that adds, deletes,
  renames, or re-modes a file, or that contains a credential value.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from check_sources import MANIFEST, load_manifest


ALLOWED_FILES = {
    ".github/authority-sources.json",
    ".claude-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
}
ALLOWED_PATTERNS = (
    re.compile(r"^plugins/[^/]+/[^/]+/plugin\.json$"),
    re.compile(r"^plugins/[^/]+/[^/]+/\.(claude|codex)-plugin/plugin\.json$"),
    re.compile(r"^(plugins|skills)/[A-Za-z0-9._/-]+\.md$"),
)
# Credentials the review job holds; none may appear in what it publishes.
SECRET_VARIABLES = ("ANTHROPIC_API_KEY", "GOOGLE_DEVELOPER_KNOWLEDGE_API_KEY")
DIFF_HEADER = re.compile(r"^diff --git a/(\S+) b/(\S+)$")
STRUCTURAL = (
    "new file mode",
    "deleted file mode",
    "old mode",
    "new mode",
    "rename from",
    "rename to",
    "copy from",
    "copy to",
    "similarity index",
    "GIT binary patch",
    "Binary files",
)


def path_allowed(path: str) -> bool:
    if ".." in path.split("/"):
        return False
    return path in ALLOWED_FILES or any(p.match(path) for p in ALLOWED_PATTERNS)


def check_patch(patch: str) -> list[str]:
    """Return every reason the patch may not be published."""
    problems = []
    paths = []
    for line in patch.splitlines():
        header = DIFF_HEADER.match(line)
        if header:
            old, new = header.groups()
            if old != new:
                problems.append(f"{old} -> {new}: renames are not allowed")
            paths.append(new)
            if not path_allowed(new):
                problems.append(f"{new}: outside the files a review may change")
            continue
        if line.startswith(STRUCTURAL):
            problems.append(f"{paths[-1] if paths else '?'}: {line.strip()}")
    if patch.strip() and not paths:
        problems.append("patch has no recognizable file headers")
    return problems


def check_secrets(texts: dict[str, str], secrets: list[str]) -> list[str]:
    problems = []
    for value in secrets:
        if len(value) < 8:
            continue
        for name, text in texts.items():
            if value in text:
                problems.append(f"{name}: contains a credential value")
    return problems


def select(report: dict, manifest: dict, only: set[str]) -> list[dict]:
    """Flagged results, merged with the manifest fields the agent needs."""
    entries = {source["id"]: source for source in manifest["sources"]}
    unknown = only - entries.keys()
    if unknown:
        raise ValueError(f"unknown source ids: {', '.join(sorted(unknown))}")
    brief = []
    for result in report["results"]:
        if only and result["id"] not in only:
            continue
        if not result.get("needs_attention"):
            continue
        source = entries[result["id"]]
        brief.append(
            {
                **{key: source[key] for key in ("package", "marker") if key in source},
                **result,
                "verified_on": source["verified_on"],
            }
        )
    return brief


def command_select(args: argparse.Namespace) -> int:
    report = json.loads(args.report.read_text(encoding="utf-8"))
    only = {part.strip() for part in args.sources.split(",") if part.strip()}
    try:
        brief = select(report, load_manifest(args.manifest), only)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2
    args.out.write_text(
        json.dumps(
            {"checked_on": report["checked_on"], "sources": brief}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    print(len(brief))
    return 0


def command_verify(args: argparse.Namespace) -> int:
    patch = args.patch.read_text(encoding="utf-8")
    summary = args.summary.read_text(encoding="utf-8")
    problems = check_patch(patch)
    if not summary.strip():
        problems.append(f"{args.summary.name}: the review summary is empty")
    secrets = [os.environ.get(name, "") for name in SECRET_VARIABLES]
    problems += check_secrets(
        {args.patch.name: patch, args.summary.name: summary}, secrets
    )
    for problem in problems:
        print(f"::error::{problem}")
    return 1 if problems else 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)

    brief = commands.add_parser("select", help="Write the agent brief")
    brief.add_argument("--report", type=Path, required=True)
    brief.add_argument("--out", type=Path, required=True)
    brief.add_argument("--sources", default="", help="Comma-separated ids")
    brief.add_argument("--manifest", type=Path, default=MANIFEST)
    brief.set_defaults(handler=command_select)

    verify = commands.add_parser("verify", help="Check a proposed change")
    verify.add_argument("--patch", type=Path, required=True)
    verify.add_argument("--summary", type=Path, required=True)
    verify.set_defaults(handler=command_verify)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
