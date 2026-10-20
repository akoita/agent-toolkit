from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

from check_sources import (  # noqa: E402
    Fetcher,
    check_source,
    load_manifest,
    render_markdown,
    validate_manifest,
)


WORKFLOW = ROOT / ".github" / "workflows" / "source-drift.yml"
TODAY = dt.date(2026, 10, 20)
TOOLCHAIN = "plugins/portable/security/skills/security-scan/references/toolchain.md"


class FakeFetcher(Fetcher):
    def __init__(self, documents=None, probes=None) -> None:
        super().__init__()
        self.documents = documents or {}
        self.probes = probes or {}

    def json(self, url: str, *, github_api: bool = False) -> object:
        return self.documents[url]

    def probe(self, url: str) -> tuple[int, str]:
        return self.probes[url]


def version_source(**overrides) -> dict:
    source = {
        "id": "gitleaks",
        "kind": "github-release",
        "package": "gitleaks/gitleaks",
        "pinned": "8.30.1",
        "marker": "# v8.30.1",
        "publisher": "gitleaks",
        "files": [TOOLCHAIN],
        "verified_on": "2026-07-29",
    }
    source.update(overrides)
    return source


def url_source(**overrides) -> dict:
    source = {
        "id": "guide",
        "kind": "url",
        "url": "https://example.org/guide",
        "publisher": "example",
        "claim": "The guide says so.",
        "files": ["docs/guide.md"],
        "verified_on": "2026-08-03",
    }
    source.update(overrides)
    return source


GITLEAKS_LATEST = "https://api.github.com/repos/gitleaks/gitleaks/releases/latest"


class RepositoryManifestTests(unittest.TestCase):
    def test_manifest_is_valid(self) -> None:
        self.assertEqual(validate_manifest(load_manifest()), [])

    def test_tracks_the_security_scan_skill_and_google_sources(self) -> None:
        manifest = load_manifest()
        tracked = set(manifest["tracked_files"])
        scan = ROOT / "plugins/portable/security/skills/security-scan"

        for path in scan.rglob("*.md"):
            self.assertIn(str(path.relative_to(ROOT)), tracked)
        google = {s["id"] for s in manifest["sources"] if s["publisher"] == "google"}
        self.assertTrue(
            {"osv-scanner", "chrome-stronger-with-every-update"} <= google
        )


class ManifestValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        guide = self.root / "docs" / "guide.md"
        guide.parent.mkdir(parents=True)
        guide.write_text(
            "See https://example.org/guide.\n"
            "```bash\n"
            "curl https://target/  # example\n"
            "tool scan .   # v1.2.3\n"
            "```\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def manifest(self, *sources: dict) -> dict:
        return {
            "version": 1,
            "default_review_after_days": 90,
            "tracked_files": ["docs/guide.md"],
            "example_urls": ["https://target/"],
            "sources": list(sources),
        }

    def tool(self, **overrides) -> dict:
        fields = {
            "id": "tool",
            "package": "example/tool",
            "pinned": "1.2.3",
            "marker": "# v1.2.3",
            "files": ["docs/guide.md"],
        }
        return version_source(**{**fields, **overrides})

    def test_accepts_a_fully_registered_file(self) -> None:
        manifest = self.manifest(url_source(), self.tool())

        self.assertEqual(validate_manifest(manifest, self.root), [])

    def test_rejects_an_unregistered_url(self) -> None:
        problems = validate_manifest(self.manifest(self.tool()), self.root)

        self.assertIn(
            "docs/guide.md:1: unregistered source https://example.org/guide",
            problems,
        )

    def test_rejects_an_unregistered_pinned_version(self) -> None:
        problems = validate_manifest(self.manifest(url_source()), self.root)

        self.assertIn("docs/guide.md:4: unregistered pinned version", problems)

    def test_rejects_a_marker_missing_from_its_file(self) -> None:
        stale = self.tool(marker="# v1.2.2")

        problems = validate_manifest(self.manifest(url_source(), stale), self.root)

        self.assertIn(
            "source 'tool': marker '# v1.2.2' not found in docs/guide.md", problems
        )

    def test_rejects_a_url_its_file_no_longer_cites(self) -> None:
        moved = url_source(url="https://example.org/old-guide")

        problems = validate_manifest(self.manifest(moved, self.tool()), self.root)

        self.assertIn("source 'guide': url not cited in docs/guide.md", problems)

    def test_rejects_duplicate_ids_and_missing_claims(self) -> None:
        unclaimed = url_source(claim="")

        problems = validate_manifest(
            self.manifest(unclaimed, self.tool(), self.tool()), self.root
        )

        self.assertIn("source 'tool': duplicate id", problems)
        self.assertIn("source 'guide': claim is required for a url source", problems)

    def test_rejects_a_generated_mirror(self) -> None:
        # Mirrors are overwritten by sync_skills.py; drift must name the source.
        mirror = version_source(files=["skills/security-scan/references/toolchain.md"])
        manifest = load_manifest()
        manifest["sources"] = [mirror]
        manifest["tracked_files"] = []

        problems = validate_manifest(manifest)

        self.assertIn(
            "source 'gitleaks': skills/security-scan/references/toolchain.md "
            "is a generated mirror; cite the canonical file",
            problems,
        )


class VersionCheckTests(unittest.TestCase):
    def check(self, tag: object, **overrides):
        fetcher = FakeFetcher(documents={GITLEAKS_LATEST: {"tag_name": tag}})
        return check_source(version_source(**overrides), fetcher, TODAY, 90)

    def test_current_release_is_ok(self) -> None:
        result = self.check("v8.30.1")

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.needs_attention)

    def test_newer_release_is_outdated(self) -> None:
        result = self.check("v8.31.0")

        self.assertEqual(result.status, "outdated")
        self.assertEqual(result.detail, "8.30.1 pinned; 8.31.0 released")

    def test_numeric_not_lexical_ordering(self) -> None:
        self.assertEqual(self.check("v8.100.0").status, "outdated")

    def test_pin_newer_than_any_release_is_flagged(self) -> None:
        # A version that was never released is a hallucination risk.
        result = self.check("v8.29.0")

        self.assertEqual(result.status, "ahead")
        self.assertTrue(result.needs_attention)

    def test_unsafe_registry_text_never_reaches_the_report(self) -> None:
        result = self.check("v9 | [click](https://evil.example)")

        self.assertEqual(result.status, "error")
        self.assertNotIn("evil", render_markdown([result], TODAY))

    def test_reads_each_registry(self) -> None:
        cases = {
            "pypi": ("https://pypi.org/pypi/bandit/json", {"info": {"version": "1.9.5"}}),
            "npm": ("https://registry.npmjs.org/bandit/latest", {"version": "1.9.5"}),
            "rubygems": (
                "https://rubygems.org/api/v1/versions/bandit/latest.json",
                {"version": "1.9.5"},
            ),
        }
        for kind, (url, document) in cases.items():
            with self.subTest(kind=kind):
                source = version_source(kind=kind, package="bandit", pinned="1.9.4")
                fetcher = FakeFetcher(documents={url: document})

                result = check_source(source, fetcher, TODAY, 90)

                self.assertEqual(result.latest, "1.9.5")
                self.assertEqual(result.status, "outdated")


class UrlCheckTests(unittest.TestCase):
    def check(self, response: tuple[int, str], **overrides):
        source = url_source(**overrides)
        fetcher = FakeFetcher(probes={source["url"]: response})
        return check_source(source, fetcher, TODAY, 90)

    def test_reachable_recent_source_is_ok(self) -> None:
        result = self.check((200, "https://example.org/guide/"))

        self.assertEqual(result.status, "ok")
        self.assertFalse(result.review_due)

    def test_missing_page_is_broken(self) -> None:
        self.assertEqual(self.check((404, "https://example.org/guide")).status, "broken")

    def test_blocked_page_is_unconfirmed_not_broken(self) -> None:
        self.assertEqual(self.check((403, "https://example.org/guide")).status, "error")

    def test_redirect_is_reported_with_sanitized_target(self) -> None:
        result = self.check((200, "https://example.org/new|`x`"))

        self.assertEqual(result.status, "moved")
        self.assertEqual(result.detail, "redirects to https://example.org/newx")

    def test_claim_is_due_for_review_after_its_interval(self) -> None:
        result = self.check((200, "https://example.org/guide"), verified_on="2026-07-01")

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.review_due)

    def test_entry_interval_overrides_the_default(self) -> None:
        result = self.check(
            (200, "https://example.org/guide"),
            verified_on="2026-07-01",
            review_after_days=365,
        )

        self.assertFalse(result.review_due)


class FetcherTests(unittest.TestCase):
    def capture(self, url: str, *, github_api: bool):
        requests = []

        def opener(request, timeout):
            requests.append(request)
            return contextlib.nullcontext(io.BytesIO(json.dumps({}).encode()))

        Fetcher(github_token="secret", opener=opener).json(url, github_api=github_api)
        return requests[0]

    def test_token_is_sent_only_to_the_github_api_and_never_redirected(self) -> None:
        api = self.capture(GITLEAKS_LATEST, github_api=True)
        registry = self.capture("https://pypi.org/pypi/bandit/json", github_api=False)

        self.assertEqual(api.unredirected_hdrs.get("Authorization"), "Bearer secret")
        self.assertNotIn("Authorization", api.headers)
        self.assertFalse(registry.has_header("Authorization"))


class ReportTests(unittest.TestCase):
    def test_groups_findings_by_what_the_maintainer_must_do(self) -> None:
        fetcher = FakeFetcher(
            documents={GITLEAKS_LATEST: {"tag_name": "v8.31.0"}},
            probes={"https://example.org/guide": (200, "https://example.org/guide")},
        )
        results = [
            check_source(version_source(), fetcher, TODAY, 90),
            check_source(url_source(verified_on="2026-01-01"), fetcher, TODAY, 90),
        ]

        report = render_markdown(results, TODAY)

        self.assertIn("2 sources checked: 1 need action, 1 due for review", report)
        self.assertIn("## Needs action", report)
        self.assertIn("## Due for review", report)
        self.assertNotIn("## Could not be checked", report)


class WorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_actions_are_pinned_to_commit_shas(self) -> None:
        uses = re.findall(r"uses:\s*(\S+)", self.text)

        self.assertTrue(uses)
        for action in uses:
            self.assertRegex(action, r"@[0-9a-f]{40}$")

    def test_runs_on_a_schedule_with_least_privilege(self) -> None:
        self.assertIn("schedule:", self.text)
        self.assertNotIn("pull_request_target", self.text)
        self.assertRegex(self.text, r"(?m)^permissions:\n  contents: read$")
        self.assertIn("persist-credentials: false", self.text)

    def test_untrusted_report_is_never_interpolated_into_a_script(self) -> None:
        for line in self.text.splitlines():
            if "needs.check.outputs.report" in line:
                self.assertRegex(line, r"^\s+REPORT: \$\{\{")


if __name__ == "__main__":
    unittest.main()
