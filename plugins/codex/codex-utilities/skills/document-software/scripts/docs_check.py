#!/usr/bin/env python3
"""Check a project's documentation links, feature catalog and engineering guides.

    python3 docs_check.py [ROOT] [--exclude GLOB ...] [--json]

Errors (exit 1):

- a local Markdown link points to a file that does not exist;
- the feature catalog (docs/features/README.md) has no Feature and Status
  columns, or a row uses a status outside available, partial, planned and
  retired;
- a page in docs/features/ is not linked from the catalog;
- a page in docs/engineering/ is not linked from AGENTS.md or
  docs/engineering/README.md.

Warnings (exit 0): a feature page longer than 150 lines. Projects without
docs/features/ or docs/engineering/ skip those checks. External links and
anchors are not fetched. Uses only the standard library.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote

STATUSES = ("available", "partial", "planned", "retired")
FEATURE_PAGE_LINES = 150
FEATURES_DIR = "docs/features"
ENGINEERING_DIR = "docs/engineering"

DEFAULT_EXCLUDES = (
    "**/node_modules/**",
    "**/.git/**",
    "**/dist/**",
    "**/vendor/**",
)

FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")
INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^)]*[\"'])?\s*\)")
REFERENCE_LINK = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$")
SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


@dataclass
class Problem:
    level: str
    path: str
    line: int
    message: str


def excluded(relative: str, patterns: list[str]) -> bool:
    candidate = "/" + relative
    return any(
        fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(candidate, pattern)
        for pattern in patterns
    )


def links(text: str) -> list[tuple[int, str]]:
    """Return (line number, target) for every link outside code."""
    found = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = INLINE_CODE.sub("", line)
        found.extend((number, match.group(1)) for match in INLINE_LINK.finditer(line))
        reference = REFERENCE_LINK.match(line)
        if reference:
            found.append((number, reference.group(1)))
    return found


def resolve(root: Path, page: Path, target: str) -> Path | None:
    """Return the local file a link points to, or None for non-file links."""
    if SCHEME.match(target) or target.startswith(("#", "//")):
        return None
    path = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not path:
        return None
    base = root if path.startswith("/") else page.parent
    return (base / path.lstrip("/")).resolve()


def check_links(root: Path, pages: list[Path]) -> list[Problem]:
    problems = []
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        for number, target in links(text):
            path = resolve(root, page, target)
            if path is not None and not path.exists():
                problems.append(
                    Problem(
                        "error",
                        page.relative_to(root).as_posix(),
                        number,
                        f"broken link: {target}",
                    )
                )
    return problems


def table_rows(text: str) -> list[tuple[int, list[str]]]:
    """Return the first Markdown table as (line number, cells), header first."""
    rows: list[tuple[int, list[str]]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells if cell):
                continue
            rows.append((number, cells))
        elif rows:
            break
    return rows


def linked_files(root: Path, page: Path) -> set[Path]:
    if not page.is_file():
        return set()
    text = page.read_text(encoding="utf-8", errors="replace")
    targets = (resolve(root, page, target) for _, target in links(text))
    return {target for target in targets if target is not None}


def check_catalog(root: Path) -> list[Problem]:
    directory = root / FEATURES_DIR
    catalog = directory / "README.md"
    if not directory.is_dir():
        return []
    relative = catalog.relative_to(root).as_posix()
    if not catalog.is_file():
        return [Problem("error", relative, 0, "feature catalog is missing")]
    rows = table_rows(catalog.read_text(encoding="utf-8", errors="replace"))
    if not rows:
        return [Problem("error", relative, 0, "feature catalog has no table")]
    header_line, header = rows[0]
    columns = [cell.lower() for cell in header]
    problems = []
    for required in ("feature", "status"):
        if required not in columns:
            problems.append(
                Problem("error", relative, header_line, f"missing column: {required}")
            )
    if problems:
        return problems
    status_index = columns.index("status")
    for number, cells in rows[1:]:
        status = cells[status_index].strip("` *_").lower() if status_index < len(cells) else ""
        if status not in STATUSES:
            problems.append(
                Problem(
                    "error",
                    relative,
                    number,
                    f"status {status or '(empty)'!r} is not one of {', '.join(STATUSES)}",
                )
            )
    listed = linked_files(root, catalog)
    for page in sorted(directory.glob("*.md")):
        if page.name == "README.md":
            continue
        page_relative = page.relative_to(root).as_posix()
        if page.resolve() not in listed:
            problems.append(
                Problem("error", page_relative, 0, "feature page is not in the catalog")
            )
        lines = len(page.read_text(encoding="utf-8", errors="replace").splitlines())
        if lines > FEATURE_PAGE_LINES:
            problems.append(
                Problem(
                    "warning",
                    page_relative,
                    0,
                    f"feature page has {lines} lines; keep it under {FEATURE_PAGE_LINES}",
                )
            )
    return problems


def check_engineering(root: Path) -> list[Problem]:
    directory = root / ENGINEERING_DIR
    if not directory.is_dir():
        return []
    linked = linked_files(root, root / "AGENTS.md") | linked_files(
        root, directory / "README.md"
    )
    problems = []
    for page in sorted(directory.glob("*.md")):
        if page.name == "README.md":
            continue
        if page.resolve() not in linked:
            problems.append(
                Problem(
                    "error",
                    page.relative_to(root).as_posix(),
                    0,
                    "engineering guide is not linked from AGENTS.md or "
                    f"{ENGINEERING_DIR}/README.md",
                )
            )
    return problems


def check(root: Path, patterns: list[str]) -> list[Problem]:
    root = root.resolve()
    pages = [
        page
        for page in sorted(root.rglob("*.md"))
        if not excluded(page.relative_to(root).as_posix(), patterns)
    ]
    return [*check_links(root, pages), *check_catalog(root), *check_engineering(root)]


def render(problem: Problem) -> str:
    location = f"{problem.path}:{problem.line}" if problem.line else problem.path
    return f"{problem.level}: {location}: {problem.message}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip pages matching this glob, relative to ROOT (repeatable)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON rows")
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"{args.root} is not a directory")
    problems = check(args.root, [*DEFAULT_EXCLUDES, *args.exclude])
    if args.json:
        print(json.dumps([asdict(problem) for problem in problems], indent=2))
    else:
        for problem in problems:
            print(render(problem))
    errors = sum(1 for problem in problems if problem.level == "error")
    warnings = len(problems) - errors
    print(f"\n{errors} errors, {warnings} warnings.", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
