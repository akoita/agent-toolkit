from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "plugins" / "claude" / "security" / "skills" / "security-ai"
VALIDATOR_PATH = SKILL_ROOT / "scripts" / "validate_restricted_analysis_profile.py"
TEMPLATE_PATH = SKILL_ROOT / "assets" / "restricted-analysis-profile.template.json"


def load_validator() -> ModuleType:
    module = ModuleType("restricted_profile_validator")
    module.__file__ = str(VALIDATOR_PATH)
    source = VALIDATOR_PATH.read_text(encoding="utf-8")
    exec(compile(source, str(VALIDATOR_PATH), "exec"), module.__dict__)
    return module


class RestrictedAnalysisProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_validator()
        cls.template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))

    def assert_rejected(
        self,
        mutate: Callable[[dict[str, Any]], None],
        expected_location: str,
    ) -> None:
        profile = copy.deepcopy(self.template)
        mutate(profile)
        with self.assertRaises(self.validator.ValidationError) as raised:
            self.validator.validate(profile)
        self.assertIn(expected_location, str(raised.exception))

    def test_shipped_template_validates(self) -> None:
        self.validator.validate(copy.deepcopy(self.template))

    def test_rejects_null_model_proxy(self) -> None:
        def mutate(profile: dict[str, Any]) -> None:
            profile["network"]["mode"] = "model_proxy_only"
            profile["network"]["allowed_destinations"] = [None]

        self.assert_rejected(mutate, "$.network.allowed_destinations[0]")

    def test_rejects_allowed_denied_conflict(self) -> None:
        def mutate(profile: dict[str, Any]) -> None:
            profile["tools"]["denied"].append("scoped_file_read")

        self.assert_rejected(mutate, "$.tools")

    def test_rejects_negative_retention(self) -> None:
        self.assert_rejected(
            lambda profile: profile["artifacts"].__setitem__("retention_days", -1),
            "$.artifacts.retention_days",
        )

    def test_rejects_negative_timeout(self) -> None:
        self.assert_rejected(
            lambda profile: profile["limits"].__setitem__("timeout_seconds", -1),
            "$.limits.timeout_seconds",
        )

    def test_rejects_empty_capture(self) -> None:
        self.assert_rejected(
            lambda profile: profile.__setitem__("capture", {}),
            "$.capture",
        )

    def test_rejects_unknown_key(self) -> None:
        self.assert_rejected(
            lambda profile: profile["source"].__setitem__("unexpected", True),
            "$.source",
        )

    def test_rejects_excluded_path_outside_source_root(self) -> None:
        self.assert_rejected(
            lambda profile: profile["source"].__setitem__(
                "excluded_paths", ["/different/repository/.git"]
            ),
            "$.source.excluded_paths[0]",
        )

    def test_rejects_credential_bearing_environment_name(self) -> None:
        self.assert_rejected(
            lambda profile: profile["credentials"][
                "allowed_environment_variables"
            ].append("AWS_SECRET_ACCESS_KEY"),
            "$.credentials.allowed_environment_variables[3]",
        )

    def test_rejects_arbitrary_allowed_capability(self) -> None:
        self.assert_rejected(
            lambda profile: profile["tools"]["allowed"].append("arbitrary_shell"),
            "$.tools.allowed",
        )


if __name__ == "__main__":
    unittest.main()
