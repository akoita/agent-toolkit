#!/usr/bin/env python3
"""Find the Markdown pages that break the writing guide's size limits.

Prints one row per page: words, lines, prose paragraphs over the paragraph
limit, and the longest section in lines. Pages over any limit are listed
first, densest first. Uses only the standard library.

    python3 docs_density.py [ROOT] [--exclude GLOB ...] [--json] [--fail]

ROOT defaults to the current directory. Code blocks, tables, lists, headings
and HTML blocks are not counted as prose paragraphs, and code blocks do not
count towards words.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

PARAGRAPH_WORDS = 120
SECTION_LINES = 150
PAGE_WORDS = 4000
PAGE_LINES = 500

DEFAULT_EXCLUDES = (
    "**/node_modules/**",
    "**/.git/**",
    "**/dist/**",
    "**/vendor/**",
    "**/CHANGELOG.md",
)

HEADING = re.compile(r"^#{1,6}\s")
FENCE = re.compile(r"^\s*(```|~~~)")
NON_PROSE = re.compile(r"^\s*([-*+]\s|\d+[.)]\s|\||>|<)")
WORD = re.compile(r"\S+")


@dataclass
class PageStats:
    path: str
    words: int
    lines: int
    long_paragraphs: int
    longest_section: int

    def over_limits(self) -> list[str]:
        reasons = []
        if self.words > PAGE_WORDS:
            reasons.append(f"page over {PAGE_WORDS} words")
        if self.lines > PAGE_LINES:
            reasons.append(f"page over {PAGE_LINES} lines")
        if self.long_paragraphs:
            reasons.append(f"paragraphs over {PARAGRAPH_WORDS} words")
        if self.longest_section > SECTION_LINES:
            reasons.append(f"section over {SECTION_LINES} lines")
        return reasons


def measure(text: str, path: str = "") -> PageStats:
    lines = text.splitlines()
    words = 0
    long_paragraphs = 0
    paragraph_words = 0
    in_fence = False
    section_start = 0
    longest_section = 0

    def close_paragraph() -> None:
        nonlocal paragraph_words, long_paragraphs
        if paragraph_words > PARAGRAPH_WORDS:
            long_paragraphs += 1
        paragraph_words = 0

    for index, line in enumerate(lines):
        if FENCE.match(line):
            close_paragraph()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        count = len(WORD.findall(line))
        words += count
        if HEADING.match(line):
            close_paragraph()
            longest_section = max(longest_section, index - section_start)
            section_start = index
        elif not line.strip() or NON_PROSE.match(line):
            close_paragraph()
        else:
            paragraph_words += count
    close_paragraph()
    longest_section = max(longest_section, len(lines) - section_start)
    return PageStats(path, words, len(lines), long_paragraphs, longest_section)


def excluded(relative: str, patterns: list[str]) -> bool:
    candidate = "/" + relative
    return any(
        fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(candidate, pattern)
        for pattern in patterns
    )


def scan(root: Path, patterns: list[str]) -> list[PageStats]:
    pages = []
    for file in sorted(root.rglob("*.md")):
        relative = file.relative_to(root).as_posix()
        if excluded(relative, patterns):
            continue
        text = file.read_text(encoding="utf-8", errors="replace")
        pages.append(measure(text, relative))
    pages.sort(key=lambda page: (not page.over_limits(), -page.words))
    return pages


def render(pages: list[PageStats]) -> str:
    rows = [
        "| Page | Words | Lines | Long paras | Longest section | Over limits |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for page in pages:
        reasons = ", ".join(page.over_limits()) or "-"
        rows.append(
            f"| {page.path} | {page.words:,} | {page.lines:,} | "
            f"{page.long_paragraphs} | {page.longest_section} | {reasons} |"
        )
    return "\n".join(rows)


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
    parser.add_argument(
        "--fail", action="store_true", help="exit 1 when any page is over a limit"
    )
    args = parser.parse_args(argv)

    if not args.root.is_dir():
        parser.error(f"{args.root} is not a directory")
    pages = scan(args.root, [*DEFAULT_EXCLUDES, *args.exclude])
    if args.json:
        rows = [{**asdict(page), "over_limits": page.over_limits()} for page in pages]
        print(json.dumps(rows, indent=2))
    else:
        print(render(pages))
    over = sum(1 for page in pages if page.over_limits())
    print(f"\n{over} of {len(pages)} pages over a limit.", file=sys.stderr)
    return 1 if args.fail and over else 0


if __name__ == "__main__":
    sys.exit(main())
