from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".github" / "scripts"))

from check_sources import load_manifest  # noqa: E402
from source_review import check_patch, check_secrets, path_allowed, select  # noqa: E402


WORKFLOWS = ROOT / ".github" / "workflows"
REVIEW_WORKFLOW = WORKFLOWS / "source-review.yml"
PROMPT = ROOT / ".github" / "source-review-prompt.md"


def diff(path: str, *extra: str) -> str:
    return "\n".join(
        [
            f"diff --git a/{path} b/{path}",
            *extra,
            "index 1111111..2222222 100644",
            f"--- a/{path}",
            f"+++ b/{path}",
            "@@ -1 +1 @@",
            "-old",
            "+new",
        ]
    )


class PatchAllowlistTests(unittest.TestCase):
    def test_allows_skill_markdown_manifests_and_catalogs(self) -> None:
        for path in (
            "plugins/portable/security/skills/security-scan/references/toolchain.md",
            "skills/security-scan/references/toolchain.md",
            "plugins/portable/security/plugin.json",
            "plugins/claude/security/.claude-plugin/plugin.json",
            "plugins/codex/codex-security/.codex-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            ".agents/plugins/marketplace.json",
            ".github/authority-sources.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(path_allowed(path))
                self.assertEqual(check_patch(diff(path)), [])

    def test_rejects_code_workflows_tests_and_traversal(self) -> None:
        for path in (
            ".github/workflows/source-review.yml",
            ".github/scripts/source_review.py",
            "tests/test_source_review.py",
            "plugins/portable/security/skills/security-ai/scripts/validate.py",
            "plugins/portable/security/skills/x/agents/openai.yaml",
            "plugins/../.github/workflows/x.md",
            "README.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(path_allowed(path))
                self.assertTrue(check_patch(diff(path)))

    def test_rejects_structural_changes_to_allowed_paths(self) -> None:
        path = "skills/security-scan/SKILL.md"
        for extra in (
            "new file mode 100644",
            "deleted file mode 100644",
            "old mode 100644",
            "GIT binary patch",
        ):
            with self.subTest(extra=extra):
                self.assertTrue(check_patch(diff(path, extra)))

    def test_rejects_renames_and_headerless_patches(self) -> None:
        rename = "diff --git a/skills/a.md b/skills/b.md\n"

        self.assertIn(
            "skills/a.md -> skills/b.md: renames are not allowed", check_patch(rename)
        )
        self.assertEqual(
            check_patch("+++ b/x\n+payload\n"),
            ["patch has no recognizable file headers"],
        )


class SecretGuardTests(unittest.TestCase):
    def test_detects_a_credential_in_any_published_text(self) -> None:
        problems = check_secrets(
            {"change.patch": "+key sk-ant-123456789", "summary.md": "clean"},
            ["sk-ant-123456789", ""],
        )

        self.assertEqual(problems, ["change.patch: contains a credential value"])

    def test_ignores_unset_and_trivially_short_values(self) -> None:
        self.assertEqual(check_secrets({"summary.md": "a b c"}, ["", "a"]), [])


class SelectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest()
        self.report = {
            "checked_on": "2026-10-20",
            "results": [
                {"id": "gitleaks", "needs_attention": True, "latest": "8.31.0"},
                {"id": "trivy", "needs_attention": False},
                {"id": "chrome-stronger-with-every-update", "needs_attention": True},
            ],
        }

    def test_selects_only_flagged_sources_with_manifest_fields(self) -> None:
        brief = select(self.report, self.manifest, set())

        self.assertEqual(
            [entry["id"] for entry in brief],
            ["gitleaks", "chrome-stronger-with-every-update"],
        )
        self.assertEqual(brief[0]["package"], "gitleaks/gitleaks")
        self.assertIn("marker", brief[0])
        self.assertEqual(brief[0]["latest"], "8.31.0")

    def test_narrows_to_requested_ids(self) -> None:
        brief = select(self.report, self.manifest, {"gitleaks", "trivy"})

        self.assertEqual([entry["id"] for entry in brief], ["gitleaks"])

    def test_rejects_unknown_ids(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown source ids: nope"):
            select(self.report, self.manifest, {"nope"})


def run_blocks(text: str) -> list[str]:
    """The shell scripts in a workflow's `run: |` blocks."""
    blocks, lines = [], text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^(\s*)(?:- )?run: \|$", line)
        if not match:
            continue
        indent = len(match.group(1))
        body = []
        for following in lines[index + 1 :]:
            if following.strip() and len(following) - len(following.lstrip()) <= indent:
                break
            body.append(following)
        blocks.append("\n".join(body))
    return blocks


def job(text: str, name: str) -> str:
    match = re.search(rf"(?ms)^  {name}:\n(.*?)(?=^  [a-z-]+:\n|\Z)", text)
    assert match, name
    return match.group(1)


class WorkflowHygieneTests(unittest.TestCase):
    def test_no_expression_is_interpolated_into_a_script(self) -> None:
        # Values reach scripts through env, never through ${{ }} in the body.
        for workflow in ("source-drift.yml", "source-review.yml"):
            text = (WORKFLOWS / workflow).read_text(encoding="utf-8")
            with self.subTest(workflow=workflow):
                blocks = run_blocks(text)
                self.assertTrue(blocks)
                for block in blocks:
                    self.assertNotIn("${{", block)
                for line in re.findall(r"(?m)^\s*(?:- )?run: (?!\|).*$", text):
                    self.assertNotIn("${{", line)


class SourceReviewWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = REVIEW_WORKFLOW.read_text(encoding="utf-8")
        self.review = job(self.text, "review")
        self.publish = job(self.text, "publish")

    def test_actions_are_pinned_to_commit_shas(self) -> None:
        for action in re.findall(r"uses:\s*(\S+)", self.text):
            self.assertRegex(action, r"@[0-9a-f]{40}$")
        self.assertNotIn("pull_request_target", self.text)

    def test_only_the_publish_job_can_write(self) -> None:
        self.assertRegex(self.text, r"(?m)^permissions:\n  contents: read$")
        self.assertNotIn(": write", self.review)
        self.assertIn("contents: write", self.publish)
        self.assertIn("pull-requests: write", self.publish)

    def test_publish_job_never_runs_the_agent_or_its_code(self) -> None:
        self.assertNotIn("claude", self.publish.replace("claude-plugin", ""))
        self.assertNotIn("ANTHROPIC_API_KEY", self.publish)
        self.assertNotIn("unittest", self.publish)
        self.assertIn("source_review.py verify", self.publish)

    def test_agent_runs_pinned_isolated_and_allowlisted(self) -> None:
        self.assertRegex(self.review, r"CLAUDE_CODE_VERSION: \d+\.\d+\.\d+\n")
        for flag in (
            "--bare",
            "--strict-mcp-config",
            "--permission-mode dontAsk",
            "--max-budget-usd",
        ):
            self.assertIn(flag, self.review)
        self.assertNotIn("bypassPermissions", self.text)
        # A failed run still exits 0; only is_error reveals it.
        self.assertIn('sys.exit(1 if r.get("is_error") else 0)', self.review)
        self.assertNotIn('"Bash"', self.review)
        self.assertNotIn('"Edit"', self.review)
        # Skill scripts run under the test suite, so the agent may not edit them.
        edits = re.findall(r'"Edit\(([^)]*)\)"', self.review)
        self.assertTrue(edits)
        for pattern in edits:
            self.assertTrue(pattern.endswith((".md", ".json")), pattern)
        self.assertIn("persist-credentials: false", self.review)

    def test_mcp_key_is_expanded_by_claude_not_written_to_disk(self) -> None:
        self.assertIn("<<'JSON'", self.review)
        self.assertIn('"X-Goog-Api-Key": "${GOOGLE_DEVELOPER_KNOWLEDGE_API_KEY}"', self.review)

    def test_credentials_reach_only_the_agent_and_the_leak_check(self) -> None:
        steps = re.split(r"(?m)^      - ", self.review)
        holders = [step.splitlines()[0] for step in steps if "secrets.ANTHROPIC_API_KEY }}" in step]
        self.assertEqual(
            holders,
            [
                "name: Review flagged sources",
                "name: Check the change against the allowlist and for credentials",
            ],
        )
        leak_check = next(s for s in steps if s.startswith("name: Check the change"))
        self.assertNotIn("unittest", leak_check)

    def test_proposal_is_verified_before_upload_and_before_apply(self) -> None:
        self.assertLess(
            self.review.index("source_review.py verify"),
            self.review.index("upload-artifact"),
        )
        self.assertLess(
            self.publish.index("source_review.py verify"),
            self.publish.index("git apply"),
        )
        self.assertIn("--draft", self.publish)

    def test_prompt_names_every_scratch_file_the_workflow_reads(self) -> None:
        prompt = PROMPT.read_text(encoding="utf-8")
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split()
        for name in ("source-review-brief.json", "source-review-summary.md"):
            self.assertIn(name, prompt)
            self.assertIn(name, self.review)
            self.assertIn(name, ignored)


if __name__ == "__main__":
    unittest.main()
