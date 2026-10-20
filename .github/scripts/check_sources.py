#!/usr/bin/env python3
"""Check the authority sources that skills are built from for drift.

Skills pin tool versions and cite primary sources. Both go stale silently: a
release ships, a page moves, guidance is superseded. `.github/authority-sources.json`
records every such source together with the canonical file that depends on it,
and this script compares each entry against what is published today:

- version entries (`github-release`, `pypi`, `npm`, `rubygems`) against the
  latest published release;
- `url` entries for reachability and redirects, and for a periodic human or
  agent review of the claim once `review_after_days` have passed.

It is deterministic and needs no model or third-party dependency. Exit status
is 0 when every source is current, 1 when anything needs attention, and 2 when
the manifest itself is invalid. `tests/test_authority_sources.py` runs the
manifest validation offline on every pull request.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from sync_skills import CANONICAL_SKILLS, mirrors_for


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".github" / "authority-sources.json"
VERSION_KINDS = ("github-release", "pypi", "npm", "rubygems")
KINDS = (*VERSION_KINDS, "url")
USER_AGENT = "agent-toolkit-source-check (+https://github.com/akoita/agent-toolkit)"
TIMEOUT_SECONDS = 20

SOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
VERSION_TEXT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}$")
PACKAGE_NAMES = {
    "github-release": re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"),
    "pypi": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
    "npm": re.compile(r"^(@[a-z0-9._-]+/)?[a-z0-9._-]+$"),
    "rubygems": re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$"),
}
# A URL ends at whitespace or at markdown, quoting, or code delimiters.
URL_IN_TEXT = re.compile(r"https?://[^\s<>()\[\]\"'`]+")
# The toolchain convention: a release observed when the line was written.
VERSION_COMMENT = re.compile(r"#\s*v?\d+(?:\.\d+)+[a-z]?\s*$")
SAFE_TEXT = re.compile(r"[^A-Za-z0-9 ._:/?=&%#+@~-]")

ATTENTION = ("outdated", "ahead", "changed", "broken", "moved", "error")


class ManifestError(Exception):
    pass


@dataclass
class Result:
    id: str
    kind: str
    status: str
    detail: str
    publisher: str
    files: list[str]
    claim: str | None = None
    review_due: bool = False
    latest: str | None = None
    pinned: str | None = None
    url: str | None = None

    @property
    def needs_attention(self) -> bool:
        return self.status in ATTENTION or self.review_due


@dataclass
class Fetcher:
    """Network access, isolated so tests can substitute recorded responses."""

    github_token: str | None = None
    timeout: float = TIMEOUT_SECONDS
    opener: Callable[..., object] = field(default=urllib.request.urlopen)

    def json(self, url: str, *, github_api: bool = False) -> object:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        if github_api:
            request.add_header("Accept", "application/vnd.github+json")
            request.add_header("X-GitHub-Api-Version", "2022-11-28")
            if self.github_token:
                # Unredirected, so the token never follows a redirect off-host.
                request.add_unredirected_header(
                    "Authorization", f"Bearer {self.github_token}"
                )
        with self.opener(request, timeout=self.timeout) as response:
            return json.load(response)

    def probe(self, url: str) -> tuple[int, str]:
        """Return the final HTTP status and URL after redirects."""
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self.opener(request, timeout=self.timeout) as response:
                return response.status, response.geturl()
        except urllib.error.HTTPError as error:
            return error.code, error.geturl() or url


def load_manifest(path: Path = MANIFEST) -> dict:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"{path}: {error}") from error
    if not isinstance(manifest, dict):
        raise ManifestError(f"{path}: top level must be an object")
    return manifest


def generated_mirror_roots() -> list[Path]:
    return [
        mirror.relative_to(ROOT)
        for name in CANONICAL_SKILLS
        for mirror in mirrors_for(name)
    ]


def urls_in(text: str) -> set[str]:
    return {match.rstrip(".,;:") for match in URL_IN_TEXT.findall(text)}


def parse_date(value: object) -> dt.date | None:
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _validate_files(
    owner: str, files: object, root: Path, mirrors: list[Path], problems: list[str]
) -> list[str]:
    if not isinstance(files, list) or not files:
        problems.append(f"{owner}: files must be a non-empty list")
        return []
    valid = []
    for name in files:
        if not isinstance(name, str) or not (root / name).is_file():
            problems.append(f"{owner}: {name!r} is not a file in the repository")
            continue
        path = Path(name)
        if any(path.is_relative_to(mirror) for mirror in mirrors):
            problems.append(
                f"{owner}: {name} is a generated mirror; cite the canonical file"
            )
            continue
        valid.append(name)
    return valid


def validate_manifest(manifest: dict, root: Path = ROOT) -> list[str]:
    """Return every problem with the manifest; an empty list means valid."""
    problems: list[str] = []
    mirrors = generated_mirror_roots()

    if manifest.get("version") != 1:
        problems.append("version must be 1")
    default_days = manifest.get("default_review_after_days")
    if not isinstance(default_days, int) or default_days < 1:
        problems.append("default_review_after_days must be a positive integer")
    examples = manifest.get("example_urls", [])
    if not isinstance(examples, list):
        problems.append("example_urls must be a list")
        examples = []
    tracked = _validate_files(
        "tracked_files", manifest.get("tracked_files"), root, mirrors, problems
    )
    sources = manifest.get("sources")
    if not isinstance(sources, list) or not sources:
        problems.append("sources must be a non-empty list")
        return problems

    seen: set[str] = set()
    registered_urls: set[str] = set()
    markers: list[str] = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            problems.append(f"sources[{index}] must be an object")
            continue
        source_id = source.get("id")
        owner = f"source {source_id!r}" if source_id else f"sources[{index}]"
        if not isinstance(source_id, str) or not SOURCE_ID.match(source_id):
            problems.append(f"{owner}: id must be lowercase kebab-case")
        elif source_id in seen:
            problems.append(f"{owner}: duplicate id")
        else:
            seen.add(source_id)

        kind = source.get("kind")
        if kind not in KINDS:
            problems.append(f"{owner}: kind must be one of {', '.join(KINDS)}")
            continue
        if not isinstance(source.get("publisher"), str) or not source["publisher"]:
            problems.append(f"{owner}: publisher is required")
        if parse_date(source.get("verified_on")) is None:
            problems.append(f"{owner}: verified_on must be an ISO date")
        review_days = source.get("review_after_days")
        if review_days is not None and (
            not isinstance(review_days, int) or review_days < 1
        ):
            problems.append(f"{owner}: review_after_days must be a positive integer")
        files = _validate_files(owner, source.get("files"), root, mirrors, problems)

        if kind in VERSION_KINDS:
            package = source.get("package")
            if not isinstance(package, str) or not PACKAGE_NAMES[kind].match(package):
                problems.append(f"{owner}: package is not a valid {kind} name")
            pinned = source.get("pinned")
            if not isinstance(pinned, str) or not VERSION_TEXT.match(pinned):
                problems.append(f"{owner}: pinned must be a version string")
            marker = source.get("marker")
            if not isinstance(marker, str) or not marker.strip():
                problems.append(f"{owner}: marker is required")
                continue
            markers.append(marker)
            for name in files:
                if marker not in (root / name).read_text(encoding="utf-8"):
                    problems.append(f"{owner}: marker {marker!r} not found in {name}")
        else:
            url = source.get("url")
            if not isinstance(url, str) or not url.startswith("https://"):
                problems.append(f"{owner}: url must be an https URL")
                continue
            if not isinstance(source.get("claim"), str) or not source["claim"]:
                problems.append(f"{owner}: claim is required for a url source")
            registered_urls.add(url)
            for name in files:
                if url not in urls_in((root / name).read_text(encoding="utf-8")):
                    problems.append(f"{owner}: url not cited in {name}")

    # Coverage: a tracked file may not cite a source the manifest ignores.
    for name in tracked:
        lines = (root / name).read_text(encoding="utf-8").splitlines()
        for number, line in enumerate(lines, start=1):
            for url in sorted(urls_in(line)):
                if url not in registered_urls and url not in examples:
                    problems.append(f"{name}:{number}: unregistered source {url}")
            if VERSION_COMMENT.search(line) and not any(m in line for m in markers):
                problems.append(f"{name}:{number}: unregistered pinned version")
    return problems


def normalize_version(raw: str) -> str:
    value = raw.strip()
    return value[1:] if value[:1] in ("v", "V") else value


def version_key(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in re.findall(r"\d+", value))


def latest_version(source: dict, fetcher: Fetcher) -> str:
    kind, package = source["kind"], source["package"]
    if kind == "github-release":
        data = fetcher.json(
            f"https://api.github.com/repos/{package}/releases/latest",
            github_api=True,
        )
        raw = data.get("tag_name") if isinstance(data, dict) else None
    elif kind == "pypi":
        data = fetcher.json(f"https://pypi.org/pypi/{package}/json")
        raw = data.get("info", {}).get("version") if isinstance(data, dict) else None
    elif kind == "npm":
        name = urllib.parse.quote(package, safe="@")
        data = fetcher.json(f"https://registry.npmjs.org/{name}/latest")
        raw = data.get("version") if isinstance(data, dict) else None
    else:
        data = fetcher.json(
            f"https://rubygems.org/api/v1/versions/{package}/latest.json"
        )
        raw = data.get("version") if isinstance(data, dict) else None
    # Release metadata is third-party text that ends up in an issue body.
    if not isinstance(raw, str) or not VERSION_TEXT.match(raw):
        raise ValueError("registry returned no usable version")
    return normalize_version(raw)


def check_version(source: dict, fetcher: Fetcher) -> tuple[str, str, str]:
    pinned = normalize_version(source["pinned"])
    latest = latest_version(source, fetcher)
    if latest == pinned:
        return "ok", f"{pinned} is the latest release", latest
    if version_key(latest) > version_key(pinned):
        return "outdated", f"{pinned} pinned; {latest} released", latest
    if version_key(latest) < version_key(pinned):
        return (
            "ahead",
            f"{pinned} pinned but latest release is {latest}; confirm {pinned} exists",
            latest,
        )
    return "changed", f"{pinned} pinned; registry reports {latest}", latest


def check_url(source: dict, fetcher: Fetcher) -> tuple[str, str]:
    url = source["url"]
    status, final = fetcher.probe(url)
    if status in (404, 410):
        return "broken", f"HTTP {status}"
    if not 200 <= status < 300:
        # 403, 429, and 5xx are often bot defenses or outages, not removal.
        return "error", f"HTTP {status}; could not confirm the page"
    if final.rstrip("/") != url.rstrip("/"):
        return "moved", f"redirects to {clean(final)}"
    return "ok", f"HTTP {status}"


def clean(text: str, limit: int = 200) -> str:
    """Strip markup from external text before it reaches a report."""
    return SAFE_TEXT.sub("", text)[:limit]


def check_source(
    source: dict, fetcher: Fetcher, today: dt.date, default_days: int
) -> Result:
    result = Result(
        id=source["id"],
        kind=source["kind"],
        status="ok",
        detail="",
        publisher=source["publisher"],
        files=list(source["files"]),
        claim=source.get("claim"),
        pinned=source.get("pinned"),
        url=source.get("url"),
    )
    try:
        if source["kind"] in VERSION_KINDS:
            result.status, result.detail, result.latest = check_version(
                source, fetcher
            )
        else:
            result.status, result.detail = check_url(source, fetcher)
            # A reachable page can still be superseded; only a reader can tell.
            age = today - dt.date.fromisoformat(source["verified_on"])
            review_days = source.get("review_after_days", default_days)
            result.review_due = age.days > review_days
    except (urllib.error.URLError, OSError, ValueError) as error:
        result.status = "error"
        result.detail = clean(f"{type(error).__name__}: {error}")
    return result


def check_all(manifest: dict, fetcher: Fetcher, today: dt.date) -> list[Result]:
    default_days = manifest["default_review_after_days"]
    return [
        check_source(source, fetcher, today, default_days)
        for source in manifest["sources"]
    ]


def _table(results: list[Result]) -> list[str]:
    lines = [
        "| Source | Publisher | Kind | Finding | Cited in |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        cited = "<br>".join(f"`{name}`" for name in result.files)
        lines.append(
            f"| `{result.id}` | {result.publisher} | {result.kind} "
            f"| {result.status}: {result.detail} | {cited} |"
        )
    return lines


def render_markdown(results: list[Result], today: dt.date) -> str:
    action = [r for r in results if r.status in ATTENTION and r.status != "error"]
    errors = [r for r in results if r.status == "error"]
    due = [r for r in results if r.review_due]
    current = [r for r in results if not r.needs_attention]

    lines = [
        "# Authority source drift report",
        "",
        f"_Checked on {today.isoformat()} against `.github/authority-sources.json`._",
        "",
        f"{len(results)} sources checked: {len(action)} need action, "
        f"{len(due)} due for review, {len(errors)} could not be checked, "
        f"{len(current)} current.",
    ]
    if action:
        lines += ["", "## Needs action", "", *_table(action)]
    if due:
        lines += [
            "",
            "## Due for review",
            "",
            "Reachable, but not re-read within the review interval. Confirm the "
            "claim still matches the source, then update `verified_on`.",
            "",
            *_table(due),
        ]
    if errors:
        lines += ["", "## Could not be checked", "", *_table(errors)]
    if action or due:
        lines += [
            "",
            "## Resolving",
            "",
            "Edit the canonical file named above, run "
            "`python .github/scripts/sync_skills.py`, update the entry's "
            "`pinned`, `marker`, or `url` and its `verified_on` in "
            "`.github/authority-sources.json`, and bump the package version.",
        ]
    return "\n".join(lines) + "\n"


def render_json(results: list[Result], today: dt.date) -> str:
    payload = {
        "checked_on": today.isoformat(),
        "results": [
            {**asdict(result), "needs_attention": result.needs_attention}
            for result in results
        ],
    }
    return json.dumps(payload, indent=2) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the manifest offline and exit",
    )
    parser.add_argument("--markdown", type=Path, help="Write the report here")
    parser.add_argument("--json", type=Path, help="Write machine-readable results")
    parser.add_argument(
        "--today",
        type=dt.date.fromisoformat,
        default=dt.date.today(),
        help="Date used for review intervals (default: today)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as error:
        print(error, file=sys.stderr)
        return 2
    problems = validate_manifest(manifest)
    if problems:
        print("authority-sources.json is invalid:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 2
    if args.validate_only:
        print(f"{len(manifest['sources'])} sources registered; manifest valid")
        return 0

    fetcher = Fetcher(github_token=os.environ.get("GITHUB_TOKEN") or None)
    results = check_all(manifest, fetcher, args.today)
    markdown = render_markdown(results, args.today)
    if args.markdown:
        args.markdown.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
    if args.json:
        args.json.write_text(render_json(results, args.today), encoding="utf-8")
    return 1 if any(result.needs_attention for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
