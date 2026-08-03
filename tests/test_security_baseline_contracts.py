from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SECURITY_ROOT = ROOT / "plugins" / "claude" / "security" / "skills"
SUPPLY_CHAIN = SECURITY_ROOT / "security-supply-chain"
SECURITY_AI = SECURITY_ROOT / "security-ai"
SECURITY_AUDIT = SECURITY_ROOT / "security-audit"
LOCAL_REFERENCE = re.compile(r"`((?:\.\./)?(?:references|assets|scripts)/[^`\s]+)`")


def run_validator(
    script: Path, document: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments, str(document)],
        cwd=script.parent.parent,
        check=False,
        capture_output=True,
        text=True,
    )


def resolve_placeholders(value: object) -> object:
    if isinstance(value, dict):
        return {key: resolve_placeholders(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_placeholders(item) for item in value]
    if isinstance(value, str) and "replace-with" in value:
        return "completed-profile-evidence"
    return value


class SecurityBaselineContractTests(unittest.TestCase):
    def test_shipped_json_templates_validate(self) -> None:
        supply_validator = SUPPLY_CHAIN / "scripts" / "validate_security_profile.py"
        ai_validator = (
            SECURITY_AI / "scripts" / "validate_restricted_analysis_profile.py"
        )

        for template in sorted((SUPPLY_CHAIN / "assets").glob("*.json")):
            with self.subTest(template=template.name):
                result = run_validator(
                    supply_validator, template, "--allow-placeholders"
                )
                self.assertEqual(result.returncode, 0, result.stderr)

        ai_template = (
            SECURITY_AI / "assets" / "restricted-analysis-profile.template.json"
        )
        result = run_validator(ai_validator, ai_template)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_completed_repository_profile_validates_without_template_mode(self) -> None:
        template = json.loads(
            (SUPPLY_CHAIN / "assets" / "repository-baseline.template.json").read_text(
                encoding="utf-8"
            )
        )
        completed = resolve_placeholders(template)
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            profile.write_text(json.dumps(completed), encoding="utf-8")
            result = run_validator(
                SUPPLY_CHAIN / "scripts" / "validate_security_profile.py", profile
            )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejected_control_requires_compensating_control(self) -> None:
        template = json.loads(
            (SUPPLY_CHAIN / "assets" / "repository-baseline.template.json").read_text(
                encoding="utf-8"
            )
        )
        completed = resolve_placeholders(template)
        completed["controls"][0]["decision"] = "reject"
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profile.json"
            profile.write_text(json.dumps(completed), encoding="utf-8")
            result = run_validator(
                SUPPLY_CHAIN / "scripts" / "validate_security_profile.py", profile
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("compensating_controls", result.stderr)

    def test_supply_chain_validator_rejects_evidence_free_control(self) -> None:
        template = json.loads(
            (SUPPLY_CHAIN / "assets" / "repository-baseline.template.json").read_text(
                encoding="utf-8"
            )
        )
        template["controls"][0]["evidence"] = []

        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_text(json.dumps(template), encoding="utf-8")
            result = run_validator(
                SUPPLY_CHAIN / "scripts" / "validate_security_profile.py",
                invalid,
                "--allow-placeholders",
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("$.controls[0].evidence", result.stderr)

    def test_supply_chain_validator_rejects_incomplete_tier_profile(self) -> None:
        template = json.loads(
            (SUPPLY_CHAIN / "assets" / "repository-baseline.template.json").read_text(
                encoding="utf-8"
            )
        )
        template["repository"]["tier"] = "T4"
        template["controls"] = template["controls"][:1]

        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_text(json.dumps(template), encoding="utf-8")
            result = run_validator(
                SUPPLY_CHAIN / "scripts" / "validate_security_profile.py",
                invalid,
                "--allow-placeholders",
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("missing catalog control", result.stderr)

    def test_supply_chain_validator_rejects_mutable_abom_reference(self) -> None:
        template = json.loads(
            (SUPPLY_CHAIN / "assets" / "action-bom.template.json").read_text(
                encoding="utf-8"
            )
        )
        template["entries"][0]["immutable_ref"] = "main"

        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_text(json.dumps(template), encoding="utf-8")
            result = run_validator(
                SUPPLY_CHAIN / "scripts" / "validate_security_profile.py",
                invalid,
                "--allow-placeholders",
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("full 40-character commit SHA", result.stderr)

    def test_action_bom_generator_is_stable_and_fails_on_mutable_inputs(self) -> None:
        generator = SUPPLY_CHAIN / "scripts" / "generate_action_bom.py"
        revision = "a" * 40
        digest = "b" * 64
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory) / "repository"
            workflows = repository / ".github" / "workflows"
            workflows.mkdir(parents=True)
            workflow = workflows / "ci.yml"
            workflow.write_text(
                f"steps:\n  - uses: actions/checkout@{revision} # v5\n",
                encoding="utf-8",
            )
            (repository / "Dockerfile").write_text(
                f"FROM python@sha256:{digest}\n", encoding="utf-8"
            )
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            base_command = [
                sys.executable,
                str(generator),
                str(repository),
                "--source-revision",
                revision,
                "--generated-at",
                "2026-08-03T00:00:00Z",
            ]
            first_result = subprocess.run(
                [*base_command, "--output", str(first)],
                check=False,
                capture_output=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                text=True,
            )
            second_result = subprocess.run(
                [*base_command, "--output", str(second)],
                check=False,
                capture_output=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                text=True,
            )
            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(len(json.loads(first.read_text())["entries"]), 2)

            workflow.write_text(
                "steps:\n  - uses: actions/checkout@main\n", encoding="utf-8"
            )
            mutable_result = subprocess.run(
                [*base_command, "--output", str(first)],
                check=False,
                capture_output=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                text=True,
            )
            self.assertEqual(mutable_result.returncode, 1)
            self.assertIn("immutable-input validation failed", mutable_result.stderr)

    def test_restricted_analysis_validator_rejects_open_network(self) -> None:
        template = json.loads(
            (
                SECURITY_AI / "assets" / "restricted-analysis-profile.template.json"
            ).read_text(encoding="utf-8")
        )
        template["network"]["mode"] = "unrestricted"

        with tempfile.TemporaryDirectory() as directory:
            invalid = Path(directory) / "invalid.json"
            invalid.write_text(json.dumps(template), encoding="utf-8")
            result = run_validator(
                SECURITY_AI / "scripts" / "validate_restricted_analysis_profile.py",
                invalid,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("$.network.mode", result.stderr)

    def test_tier_and_lifecycle_contracts_cover_the_required_shapes(self) -> None:
        baseline = (SUPPLY_CHAIN / "references" / "tiered-baseline.md").read_text(
            encoding="utf-8"
        )
        for tier in ("T0", "T1", "T2", "T3", "T4"):
            self.assertIn(tier, baseline)
        for decision in (
            "adopt",
            "adapt",
            "reject",
            "already-covered",
            "not-applicable",
        ):
            self.assertIn(f"`{decision}`", baseline)
        self.assertIn("SC-BUILD-01", baseline)

        monitoring = (
            SUPPLY_CHAIN / "references" / "monitoring-and-response.md"
        ).read_text(encoding="utf-8")
        for scenario in (
            "Package takeover",
            "Dependency confusion",
            "Pipeline credential harvesting",
            "Malicious skills or plugins",
            "Developer workstation or IDE compromise",
        ):
            self.assertIn(scenario, monitoring)

        lifecycle = (
            SECURITY_AUDIT / "references" / "vulnerability-lifecycle.md"
        ).read_text(encoding="utf-8")
        for state in (
            "candidate",
            "triaged",
            "reproduced",
            "accepted",
            "fixed",
            "released",
            "deployed_or_adopted",
            "closed",
        ):
            self.assertIn(f"`{state}`", lifecycle)
        for metric in ("p50", "p90"):
            self.assertIn(metric, lifecycle)

    def test_new_local_reference_paths_resolve_inside_their_skill(self) -> None:
        for skill in (SUPPLY_CHAIN, SECURITY_AI, SECURITY_AUDIT):
            for document in sorted(skill.rglob("*.md")):
                for token in LOCAL_REFERENCE.findall(
                    document.read_text(encoding="utf-8")
                ):
                    target = (
                        (document.parent / token).resolve()
                        if token.startswith("../")
                        else (skill / token).resolve()
                    )
                    with self.subTest(document=document, reference=token):
                        self.assertTrue(
                            target.is_relative_to(skill.resolve()),
                            f"reference escapes skill: {token}",
                        )
                        self.assertTrue(target.exists(), f"missing reference: {target}")


if __name__ == "__main__":
    unittest.main()
