#!/usr/bin/env python3
"""Audit a repository against the Agent Toolkit practice catalog.

Read-only: it never writes to the project. For each practice in
references/practices.json it decides whether the practice applies, then
reports present, partial, missing, declined, not-applicable or review (a
person or agent must judge it), with the evidence it used.

    python3 audit.py [PROJECT]              # table
    python3 audit.py [PROJECT] --json       # JSON rows
    python3 audit.py [PROJECT] --check      # exit 1 if an applicable practice
                                            # is missing or partial

Decisions recorded in PROJECT/.agent-toolkit/baseline.json change the result:
"decline" reports the practice as declined, "adopt" makes it apply even when
the repository does not look like it needs it. Uses only the standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

CATALOG_PATH = Path(__file__).resolve().parents[1] / "references" / "practices.json"
RECORD_PATH = Path(".agent-toolkit") / "baseline.json"
REQUIRED_PLUGINS = ("utilities@agent-toolkit", "baseline@agent-toolkit")
WRITING_POLICY_MARKER = "<!-- agent-toolkit:writing-policy -->"
LINK_CHECKERS = (
    "docs_check",
    "lychee",
    "markdown-link-check",
    "linkinator",
    "remark-validate-links",
)
AGENTS_TOPICS = {
    "commands and checks": ("command", "check", "quality", "test", "gate"),
    "change delivery": ("deliver", "pull request", "change", "contribut"),
    "architecture boundaries": ("architecture", "boundar", "layout", "structure"),
}
DOCS_TREE_PAGES = 3
LINK = re.compile(r"\]\(\s*<?([^)\s>#]+)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


@dataclass
class Result:
    id: str
    group: str
    title: str
    status: str
    evidence: str
    fix: str


Check = Callable[[Path], tuple[str, str]]


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, IsADirectoryError):
        return ""


def headings(text: str) -> list[str]:
    return [heading.strip().lower() for heading in HEADING.findall(text)]


def linked(root: Path, page: Path) -> set[Path]:
    targets = set()
    for target in LINK.findall(read(page)):
        if "://" in target:
            continue
        base = root if target.startswith("/") else page.parent
        targets.add((base / target.lstrip("/")).resolve())
    return targets


def docs_pages(root: Path) -> list[Path]:
    docs = root / "docs"
    return sorted(docs.rglob("*.md")) if docs.is_dir() else []


# Applicability --------------------------------------------------------------


def is_application(root: Path) -> tuple[bool, str]:
    signals = []
    for name in ("apps", "cmd", "services"):
        if (root / name).is_dir():
            signals.append(f"{name}/")
    for pattern in ("Dockerfile*", "compose*.y*ml", "docker-compose*.y*ml"):
        signals.extend(path.name for path in sorted(root.glob(pattern)))
    package = root / "package.json"
    if package.is_file():
        try:
            data = json.loads(read(package))
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict) and (
            data.get("bin") or "start" in (data.get("scripts") or {})
        ):
            signals.append("package.json start or bin")
    if "[project.scripts]" in read(root / "pyproject.toml"):
        signals.append("pyproject.toml [project.scripts]")
    if signals:
        return True, "application signals: " + ", ".join(signals[:4])
    return False, "no application signals (apps/, Dockerfile, compose, start script)"


def has_docs_tree(root: Path) -> tuple[bool, str]:
    count = len(docs_pages(root))
    return count >= DOCS_TREE_PAGES, f"docs/ has {count} Markdown pages"


def has_ci_and_docs(root: Path) -> tuple[bool, str]:
    ci = (root / ".github" / "workflows").is_dir() or (root / ".gitlab-ci.yml").is_file()
    docs, evidence = has_docs_tree(root)
    return ci and docs, ("CI found; " if ci else "no CI found; ") + evidence


APPLIES: dict[str, Callable[[Path], tuple[bool, str]]] = {
    "always": lambda root: (True, "applies to every repository"),
    "application": is_application,
    "docs-tree": has_docs_tree,
    "ci-and-docs": has_ci_and_docs,
}


# Checks ---------------------------------------------------------------------


def check_agents_md(root: Path) -> tuple[str, str]:
    text = read(root / "AGENTS.md")
    if not text:
        return "missing", "no AGENTS.md"
    found = headings(text)
    absent = [
        topic
        for topic, words in AGENTS_TOPICS.items()
        if not any(word in heading for heading in found for word in words)
    ]
    if absent:
        return "partial", "AGENTS.md has no section on " + ", ".join(absent)
    return "present", "AGENTS.md covers " + ", ".join(AGENTS_TOPICS)


def check_claude_imports_agents(root: Path) -> tuple[str, str]:
    text = read(root / "CLAUDE.md")
    if not text:
        return "missing", "no CLAUDE.md"
    if any(line.strip() == "@AGENTS.md" for line in text.splitlines()):
        return "present", "CLAUDE.md imports @AGENTS.md"
    return "partial", "CLAUDE.md does not import @AGENTS.md"


def check_toolkit_plugins(root: Path) -> tuple[str, str]:
    path = root / ".claude" / "settings.json"
    try:
        settings = json.loads(read(path) or "{}")
    except json.JSONDecodeError:
        return "partial", ".claude/settings.json is not valid JSON"
    enabled = settings.get("enabledPlugins") if isinstance(settings, dict) else None
    enabled = enabled if isinstance(enabled, dict) else {}
    on = [plugin for plugin in REQUIRED_PLUGINS if enabled.get(plugin) is True]
    if len(on) == len(REQUIRED_PLUGINS):
        return "present", "enabled: " + ", ".join(on)
    off = [plugin for plugin in REQUIRED_PLUGINS if plugin not in on]
    status = "partial" if on else "missing"
    return status, "not enabled in .claude/settings.json: " + ", ".join(off)


def check_agent_access(root: Path) -> tuple[str, str]:
    catalog = read(root / "docs" / "features" / "README.md").lower()
    if "agent access" in catalog:
        return "present", "feature catalog has an Agent access column"
    return "review", "judge which features agents need, and how they reach them"


def check_writing_policy(root: Path) -> tuple[str, str]:
    text = read(root / "AGENTS.md")
    if WRITING_POLICY_MARKER in text:
        return "present", "AGENTS.md has the managed writing-policy block"
    if "writing documentation" in headings(text):
        return "partial", "AGENTS.md has a hand-written Writing documentation section"
    return "missing", "AGENTS.md has no writing policy"


def check_readme(root: Path) -> tuple[str, str]:
    readme = next(iter(sorted(root.glob("README*"))), None)
    if readme is None:
        return "missing", "no root README"
    lines = [line for line in read(readme).splitlines() if line.strip()]
    if len(lines) < 10:
        return "partial", f"{readme.name} has only {len(lines)} non-empty lines"
    return "present", f"{readme.name} has {len(lines)} non-empty lines"


def check_docs_map(root: Path) -> tuple[str, str]:
    if (root / "docs" / "README.md").is_file():
        return "present", "docs/README.md exists"
    return "missing", "no docs/README.md"


def check_architecture_overview(root: Path) -> tuple[str, str]:
    for page in docs_pages(root):
        relative = page.relative_to(root).as_posix()
        if "architecture" in relative.lower():
            return "present", f"found {relative}"
    if any("architecture" in heading for heading in headings(read(root / "README.md"))):
        return "present", "README.md has an Architecture section"
    return "missing", "no architecture page or README section"


def check_feature_catalog(root: Path) -> tuple[str, str]:
    catalog = root / "docs" / "features" / "README.md"
    text = read(catalog)
    if not text:
        return "missing", "no docs/features/README.md"
    header = next((line for line in text.splitlines() if line.strip().startswith("|")), "")
    columns = [cell.strip().lower() for cell in header.strip().strip("|").split("|")]
    if "feature" in columns and "status" in columns:
        return "present", "docs/features/README.md has Feature and Status columns"
    return "partial", "docs/features/README.md has no Feature and Status table"


def check_engineering_guides(root: Path) -> tuple[str, str]:
    directory = root / "docs" / "engineering"
    guides = [page for page in sorted(directory.glob("*.md")) if page.name != "README.md"]
    if not guides:
        return "missing", "no guides in docs/engineering/"
    targets = linked(root, root / "AGENTS.md") | linked(root, directory / "README.md")
    unlinked = [page.name for page in guides if page.resolve() not in targets]
    if unlinked:
        return "partial", "not linked from AGENTS.md: " + ", ".join(unlinked)
    return "present", f"{len(guides)} guides, all linked"


def check_docs_check_ci(root: Path) -> tuple[str, str]:
    workflows = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    sources = [*workflows, root / ".gitlab-ci.yml", root / "package.json"]
    for source in sources:
        text = read(source)
        for checker in LINK_CHECKERS:
            if checker in text:
                return "present", f"{source.name} runs {checker}"
    return "missing", "no link or catalog check found in CI"


CHECKS: dict[str, Check] = {
    "agents-md": check_agents_md,
    "claude-imports-agents": check_claude_imports_agents,
    "toolkit-plugins": check_toolkit_plugins,
    "agent-access": check_agent_access,
    "writing-policy": check_writing_policy,
    "readme": check_readme,
    "docs-map": check_docs_map,
    "architecture-overview": check_architecture_overview,
    "feature-catalog": check_feature_catalog,
    "engineering-guides": check_engineering_guides,
    "docs-check-ci": check_docs_check_ci,
}


# Audit ----------------------------------------------------------------------


def load_catalog() -> list[dict[str, str]]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["practices"]


def load_decisions(root: Path) -> dict[str, dict[str, str]]:
    text = read(root / RECORD_PATH)
    if not text:
        return {}
    record = json.loads(text)
    decisions = record.get("decisions", {}) if isinstance(record, dict) else {}
    return decisions if isinstance(decisions, dict) else {}


def audit(root: Path) -> list[Result]:
    decisions = load_decisions(root)
    results = []
    for practice in load_catalog():
        decision = decisions.get(practice["id"], {}).get("decision")
        applies, why = APPLIES[practice["applies"]](root)
        if decision == "decline":
            status = "declined"
            evidence = decisions[practice["id"]].get("reason", "declined in baseline.json")
        elif not applies and decision != "adopt":
            status, evidence = "not-applicable", why
        else:
            status, evidence = CHECKS[practice["id"]](root)
        results.append(
            Result(
                practice["id"],
                practice["group"],
                practice["title"],
                status,
                evidence,
                practice["fix"],
            )
        )
    return results


def render(results: list[Result]) -> str:
    rows = [
        "| Group | Practice | Status | Evidence | Fix |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        fix = "-" if result.status in ("present", "declined", "not-applicable") else result.fix
        rows.append(
            f"| {result.group} | `{result.id}` {result.title} | {result.status} | "
            f"{result.evidence} | {fix} |"
        )
    return "\n".join(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", nargs="?", default=".", type=Path)
    parser.add_argument("--json", action="store_true", help="print JSON rows")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 when an applicable practice is missing or partial",
    )
    args = parser.parse_args(argv)

    root = args.project.resolve()
    if not root.is_dir():
        parser.error(f"{args.project} is not a directory")
    try:
        results = audit(root)
    except json.JSONDecodeError as error:
        print(f"error: {RECORD_PATH} is not valid JSON: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        print(render(results))
    gaps = [result for result in results if result.status in ("missing", "partial")]
    print(f"\n{len(gaps)} of {len(results)} practices missing or partial.", file=sys.stderr)
    return 1 if args.check and gaps else 0


if __name__ == "__main__":
    sys.exit(main())
