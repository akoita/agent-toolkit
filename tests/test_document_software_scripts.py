from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import json
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = (
    ROOT / "plugins" / "portable" / "utilities" / "skills" / "document-software"
)


def load(name: str) -> ModuleType:
    path = SKILL_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"document_software_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run(module: ModuleType, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = module.main(list(args))
    return code, out.getvalue()


class DocsDensityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.density = load("docs_density")

    def test_counts_long_prose_paragraphs_but_not_code_or_lists(self) -> None:
        long_line = " ".join(["word"] * 130)
        text = "\n".join(
            [
                "# Title",
                "",
                long_line,
                "",
                "- " + long_line,
                "",
                "```",
                long_line,
                "```",
                "",
                "Short paragraph.",
            ]
        )
        stats = self.density.measure(text, "page.md")
        self.assertEqual(stats.long_paragraphs, 1)
        self.assertEqual(stats.words, 1 + 1 + 130 + 131 + 2)
        self.assertIn("paragraphs over 120 words", stats.over_limits())

    def test_longest_section_is_measured_between_headings(self) -> None:
        text = "# A\n" + "x\n" * 3 + "## B\n" + "y\n" * 200
        stats = self.density.measure(text)
        self.assertEqual(stats.longest_section, 201)
        self.assertIn("section over 150 lines", stats.over_limits())

    def test_scan_lists_pages_over_limits_first_and_honours_excludes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "small.md").write_text("# Small\n\nFine.\n", encoding="utf-8")
            (root / "big.md").write_text("word " * 4500, encoding="utf-8")
            (root / "skip").mkdir()
            (root / "skip" / "huge.md").write_text("word " * 9000, encoding="utf-8")
            pages = self.density.scan(root, ["skip/**"])
            self.assertEqual([page.path for page in pages], ["big.md", "small.md"])
            code, _ = run(self.density, str(root), "--exclude", "skip/**", "--fail")
            self.assertEqual(code, 1)


class InstallPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.install = load("install_policy")
        cls.block = cls.install.canonical_block()

    def test_block_is_wrapped_in_markers(self) -> None:
        self.assertTrue(self.block.startswith(self.install.START + "\n\n## "))
        self.assertTrue(self.block.endswith("\n\n" + self.install.END + "\n"))

    def test_replaces_a_legacy_section_and_keeps_the_rest(self) -> None:
        text = (
            "# Rules\n\n## Before\n\nKeep me.\n\n"
            "## Writing documentation\n\nOld text.\n\n## After\n\nKeep me too.\n"
        )
        updated = self.install.update_agents(text, self.block)
        self.assertNotIn("Old text.", updated)
        self.assertIn("## Before\n\nKeep me.\n\n" + self.install.START, updated)
        self.assertIn(self.install.END + "\n\n## After\n\nKeep me too.\n", updated)
        self.assertEqual(self.install.update_agents(updated, self.block), updated)

    def test_refreshes_only_the_marked_block(self) -> None:
        stale = f"# Rules\n\n{self.install.START}\nold\n{self.install.END}\n\nLocal.\n"
        updated = self.install.update_agents(stale, self.block)
        self.assertEqual(updated, "# Rules\n\n" + self.block + "\nLocal.\n")

    def test_appends_or_creates_when_no_section_exists(self) -> None:
        appended = self.install.update_agents("# Rules\n\nOne rule.\n", self.block)
        self.assertEqual(appended, "# Rules\n\nOne rule.\n\n" + self.block)
        created = self.install.update_agents("", self.block)
        self.assertTrue(created.startswith("# Working instructions\n\n"))

    def test_settings_merge_keeps_existing_values(self) -> None:
        existing = json.dumps(
            {"permissions": {"allow": ["Bash(ls)"]}, "enabledPlugins": {"x@y": True}}
        )
        merged = json.loads(self.install.update_settings(existing))
        self.assertEqual(merged["permissions"], {"allow": ["Bash(ls)"]})
        self.assertTrue(merged["enabledPlugins"]["x@y"])
        self.assertTrue(merged["enabledPlugins"][self.install.PLUGIN])
        self.assertEqual(
            merged["extraKnownMarketplaces"]["agent-toolkit"]["source"]["repo"],
            "akoita/agent-toolkit",
        )
        self.assertEqual(
            self.install.update_settings(json.dumps(merged)),
            json.dumps(merged, indent=2) + "\n",
        )

    def test_check_write_check_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
            self.assertEqual(run(self.install, str(root), "--check")[0], 1)
            code, output = run(self.install, str(root))
            self.assertEqual(code, 0)
            self.assertIn("Dry run", output)
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), "# Rules\n")
            self.assertEqual(run(self.install, str(root), "--write")[0], 0)
            self.assertTrue((root / ".claude" / "settings.json").exists())
            code, output = run(self.install, str(root), "--check")
            self.assertEqual(code, 0)
            self.assertIn("up to date", output)


class DocsCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.check = load("docs_check")

    def project(self, files: dict[str, str]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def messages(self, root: Path) -> list[str]:
        return [
            f"{problem.level} {problem.path} {problem.message}"
            for problem in self.check.check(root, list(self.check.DEFAULT_EXCLUDES))
        ]

    def test_valid_catalog_and_guides_pass(self) -> None:
        root = self.project(
            {
                "AGENTS.md": "Read [routes](docs/engineering/api-route.md).\n",
                "docs/features/README.md": "\n".join(
                    [
                        "# Features",
                        "",
                        "| Feature | Status | Where it runs | Agent access | What it does |",
                        "| --- | --- | --- | --- | --- |",
                        "| [Export](export.md) | `available` | web | none | Exports. |",
                    ]
                ),
                "docs/features/export.md": "# Export\n\nSee [site](https://x.test).\n",
                "docs/engineering/api-route.md": "# Add an API route\n",
            }
        )
        self.assertEqual(self.messages(root), [])
        code, _ = run(self.check, str(root))
        self.assertEqual(code, 0)

    def test_reports_broken_links_but_ignores_code(self) -> None:
        root = self.project(
            {
                "README.md": "\n".join(
                    [
                        "[gone](docs/missing.md) and `[code](nope.md)`",
                        "```",
                        "[fenced](nope.md)",
                        "```",
                        "[ok](README.md#top) [anchor](#top)",
                        "[ref]: docs/also-missing.md",
                    ]
                )
            }
        )
        self.assertEqual(
            self.messages(root),
            [
                "error README.md broken link: docs/missing.md",
                "error README.md broken link: docs/also-missing.md",
            ],
        )
        code, _ = run(self.check, str(root))
        self.assertEqual(code, 1)

    def test_reports_bad_status_unlisted_and_long_feature_pages(self) -> None:
        root = self.project(
            {
                "docs/features/README.md": "\n".join(
                    [
                        "| Feature | Status |",
                        "| --- | --- |",
                        "| [Export](export.md) | shipped |",
                    ]
                ),
                "docs/features/export.md": "# Export\n",
                "docs/features/import.md": "line\n" * 151,
            }
        )
        self.assertEqual(
            self.messages(root),
            [
                "error docs/features/README.md status 'shipped' is not one of "
                "available, partial, planned, retired",
                "error docs/features/import.md feature page is not in the catalog",
                "warning docs/features/import.md feature page has 151 lines; "
                "keep it under 150",
            ],
        )

    def test_reports_catalog_without_status_column(self) -> None:
        root = self.project({"docs/features/README.md": "| Feature |\n| --- |\n"})
        self.assertEqual(
            self.messages(root),
            ["error docs/features/README.md missing column: status"],
        )

    def test_reports_unlinked_engineering_guide(self) -> None:
        root = self.project(
            {
                "AGENTS.md": "# Rules\n",
                "docs/engineering/README.md": "[A](a.md)\n",
                "docs/engineering/a.md": "# A\n",
                "docs/engineering/b.md": "# B\n",
            }
        )
        self.assertEqual(
            self.messages(root),
            [
                "error docs/engineering/b.md engineering guide is not linked "
                "from AGENTS.md or docs/engineering/README.md"
            ],
        )


if __name__ == "__main__":
    unittest.main()
