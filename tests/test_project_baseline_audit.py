from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "plugins" / "portable" / "baseline" / "skills" / "project-baseline"


def load() -> ModuleType:
    path = SKILL_ROOT / "scripts" / "audit.py"
    spec = importlib.util.spec_from_file_location("project_baseline_audit", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


COMPLETE_AGENTS = """# Rules

## Architecture boundaries

## Commands and quality gates

## Change delivery

<!-- agent-toolkit:writing-policy -->

## Writing documentation

<!-- /agent-toolkit:writing-policy -->

| When you change | Read |
| --- | --- |
| Routes | [Add a route](docs/engineering/add-route.md) |
"""


class ProjectBaselineAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = load()

    def project(self, files: dict[str, str]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def statuses(self, root: Path) -> dict[str, str]:
        return {result.id: result.status for result in self.audit.audit(root)}

    def run_main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = self.audit.main(list(args))
        return code, out.getvalue()

    def test_every_catalog_practice_has_a_check_and_valid_applicability(self) -> None:
        catalog = json.loads(
            (SKILL_ROOT / "references" / "practices.json").read_text(encoding="utf-8")
        )
        ids = [practice["id"] for practice in catalog["practices"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(self.audit.CHECKS))
        for practice in catalog["practices"]:
            with self.subTest(practice=practice["id"]):
                self.assertIn(practice["applies"], self.audit.APPLIES)
                self.assertIn(f"### {practice['id']}", (SKILL_ROOT / "references" / "practices.md").read_text(encoding="utf-8"))

    def test_empty_repository_reports_gaps_and_skips_conditional_practices(self) -> None:
        root = self.project({"main.py": "print('hi')\n"})
        statuses = self.statuses(root)
        self.assertEqual(statuses["agents-md"], "missing")
        self.assertEqual(statuses["readme"], "missing")
        self.assertEqual(statuses["feature-catalog"], "not-applicable")
        self.assertEqual(statuses["docs-map"], "not-applicable")
        code, _ = self.run_main(str(root), "--check")
        self.assertEqual(code, 1)
        code, _ = self.run_main(str(root))
        self.assertEqual(code, 0)

    def test_complete_application_passes_check(self) -> None:
        root = self.project(
            {
                "AGENTS.md": COMPLETE_AGENTS,
                "CLAUDE.md": "@AGENTS.md\n",
                ".claude/settings.json": json.dumps(
                    {
                        "enabledPlugins": {
                            "utilities@agent-toolkit": True,
                            "baseline@agent-toolkit": True,
                        }
                    }
                ),
                "README.md": "# App\n" + "line\n" * 12,
                "Dockerfile": "FROM scratch\n",
                "docs/README.md": "# Docs\n",
                "docs/architecture/overview.md": "# Architecture\n",
                "docs/features/README.md": "| Feature | Status | Agent access |\n| --- | --- | --- |\n",
                "docs/engineering/add-route.md": "# Add a route\n",
                ".github/workflows/ci.yml": "on: [pull_request]\njobs:\n  t:\n    steps:\n      - run: python3 docs_check.py . && gitleaks detect\n",
                ".github/pull_request_template.md": "## Summary\n",
                "SECURITY.md": "# Security\n",
                "docs/security/threat-model.md": "# Threat model\n",
            }
        )
        statuses = self.statuses(root)
        self.assertEqual(set(statuses.values()), {"present", "not-applicable"}, statuses)
        self.assertEqual(statuses["threat-model"], "present")
        self.assertEqual(statuses["lockfile"], "not-applicable")
        code, _ = self.run_main(str(root), "--check")
        self.assertEqual(code, 0)

    def test_partial_results_name_the_gap(self) -> None:
        root = self.project(
            {
                "AGENTS.md": "# Rules\n\n## Commands\n\n## Writing documentation\n",
                "CLAUDE.md": "Read the rules.\n",
                ".claude/settings.json": json.dumps(
                    {"enabledPlugins": {"utilities@agent-toolkit": True}}
                ),
                "docs/a.md": "",
                "docs/b.md": "",
                "docs/engineering/orphan.md": "# Orphan\n",
            }
        )
        results = {result.id: result for result in self.audit.audit(root)}
        self.assertEqual(results["agents-md"].status, "partial")
        self.assertIn("change delivery", results["agents-md"].evidence)
        self.assertEqual(results["claude-imports-agents"].status, "partial")
        self.assertEqual(results["toolkit-plugins"].status, "partial")
        self.assertEqual(results["writing-policy"].status, "partial")
        self.assertEqual(results["engineering-guides"].status, "partial")
        self.assertIn("orphan.md", results["engineering-guides"].evidence)

    def test_recorded_decisions_override_detection(self) -> None:
        record = {
            "schema_version": 1,
            "decisions": {
                "readme": {"decision": "decline", "reason": "Docs site is the front door."},
                "feature-catalog": {"decision": "adopt"},
            },
        }
        root = self.project({".agent-toolkit/baseline.json": json.dumps(record)})
        results = {result.id: result for result in self.audit.audit(root)}
        self.assertEqual(results["readme"].status, "declined")
        self.assertEqual(results["readme"].evidence, "Docs site is the front door.")
        self.assertEqual(results["feature-catalog"].status, "missing")

    def test_json_output_and_invalid_record(self) -> None:
        root = self.project({})
        code, out = self.run_main(str(root), "--json")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), len(self.audit.CHECKS))
        (root / ".agent-toolkit").mkdir()
        (root / ".agent-toolkit" / "baseline.json").write_text("{", encoding="utf-8")
        code, _ = self.run_main(str(root))
        self.assertEqual(code, 2)


class ProjectBaselineEngineeringChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = load()

    def project(self, files: dict[str, str]) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root

    def results(self, root: Path) -> dict[str, object]:
        return {result.id: result for result in self.audit.audit(root)}

    def test_node_project_with_good_practices(self) -> None:
        root = self.project(
            {
                "package.json": json.dumps(
                    {"packageManager": "pnpm@10.0.0", "scripts": {"validate": "x", "security:secrets": "y"}}
                ),
                "pnpm-lock.yaml": "",
                ".github/dependabot.yml": "version: 2\n",
                ".github/workflows/release.yml": "on: push\njobs:\n  r:\n    steps:\n      - uses: actions/checkout@0123456789abcdef0123456789abcdef01234567 # v5\n      - uses: ./local\n",
                "RELEASING.md": "# Releasing\n",
            }
        )
        results = self.results(root)
        for practice in (
            "one-command-gate",
            "pinned-toolchain",
            "lockfile",
            "dependency-updates",
            "secrets-scan",
            "pinned-actions",
            "release-procedure",
        ):
            with self.subTest(practice=practice):
                self.assertEqual(results[practice].status, "present", results[practice].evidence)
        self.assertEqual(results["ci-on-prs"].status, "missing")

    def test_gaps_in_a_code_repository(self) -> None:
        root = self.project(
            {
                "pyproject.toml": "[project]\nrequires-python = '>=3.11'\n",
                ".github/workflows/ci.yml": "on: pull_request\njobs:\n  t:\n    steps:\n      - uses: actions/checkout@v5\n      - uses: actions/setup-python@0123456789abcdef0123456789abcdef01234567\n",
            }
        )
        results = self.results(root)
        self.assertEqual(results["pinned-toolchain"].status, "partial")
        self.assertEqual(results["lockfile"].status, "missing")
        self.assertEqual(results["one-command-gate"].status, "missing")
        self.assertEqual(results["ci-on-prs"].status, "present")
        self.assertEqual(results["pinned-actions"].status, "partial")
        self.assertIn("actions/checkout@v5", results["pinned-actions"].evidence)
        self.assertEqual(results["pr-template"].status, "missing")
        self.assertEqual(results["security-policy"].status, "missing")
        self.assertEqual(results["release-procedure"].status, "not-applicable")

    def test_terraform_repository_counts_as_code(self) -> None:
        root = self.project(
            {
                "envs/prod/main.tf": 'terraform {\n  required_version = "1.9.0"\n}\n',
                "envs/prod/.terraform.lock.hcl": "",
                "Makefile": "check:\n\tterraform fmt -check\n",
            }
        )
        results = self.results(root)
        self.assertEqual(results["pinned-toolchain"].status, "present")
        self.assertEqual(results["lockfile"].status, "present")
        self.assertEqual(results["one-command-gate"].status, "present")
        self.assertEqual(results["dependency-updates"].status, "missing")


if __name__ == "__main__":
    unittest.main()
