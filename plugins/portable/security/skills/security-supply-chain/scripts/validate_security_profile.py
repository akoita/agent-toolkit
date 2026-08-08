#!/usr/bin/env python3
"""Validate agent-toolkit repository security profiles and Action BOMs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
PROFILE_TYPE = "agent-toolkit.repository-security-profile"
ABOM_TYPE = "agent-toolkit.action-bom"

TIERS = {"T0", "T1", "T2", "T3", "T4"}
DECISIONS = {"adopt", "adapt", "reject", "already-covered", "not-applicable"}
APPLICABILITY = {
    "required",
    "conditional-triggered",
    "conditional-not-triggered",
    "out-of-tier",
}
LEVELS = {"low", "medium", "high"}
CONTROL_IDS = {
    "SC-INV-01",
    "SC-VCS-01",
    "SC-CI-01",
    "SC-CI-02",
    "SC-CI-03",
    "SC-BUILD-01",
    "SC-DEP-01",
    "SC-DEP-02",
    "SC-ABOM-01",
    "SC-SBOM-01",
    "SC-PROV-01",
    "SC-DEPLOY-01",
    "SC-MON-01",
    "SC-IR-01",
    "SC-AI-01",
    "SC-T4-01",
}
REQUIRED_BY_TIER = {
    "T0": {"SC-INV-01"},
    "T1": {
        "SC-INV-01",
        "SC-VCS-01",
        "SC-CI-01",
        "SC-BUILD-01",
        "SC-DEP-01",
        "SC-DEP-02",
        "SC-ABOM-01",
        "SC-SBOM-01",
    },
    "T2": {
        "SC-INV-01",
        "SC-VCS-01",
        "SC-CI-01",
        "SC-CI-02",
        "SC-CI-03",
        "SC-BUILD-01",
        "SC-DEP-01",
        "SC-DEP-02",
        "SC-ABOM-01",
        "SC-SBOM-01",
        "SC-PROV-01",
        "SC-DEPLOY-01",
        "SC-MON-01",
        "SC-IR-01",
    },
    "T3": CONTROL_IDS - {"SC-T4-01"},
    "T4": CONTROL_IDS,
}
CONDITIONAL_BY_TIER = {
    "T0": {"SC-VCS-01", "SC-CI-01", "SC-BUILD-01", "SC-ABOM-01", "SC-MON-01"},
    "T1": {"SC-CI-02", "SC-CI-03", "SC-PROV-01", "SC-MON-01", "SC-IR-01", "SC-AI-01"},
    "T2": {"SC-AI-01"},
    "T3": set(),
    "T4": set(),
}
CADENCES = {
    "per_change",
    "monthly",
    "quarterly",
    "semiannual",
    "annual",
}
ABOM_KINDS = {
    "github_action",
    "reusable_workflow",
    "composite_action",
    "container_image",
    "build_utility",
}
PROVENANCE_STATES = {
    "verified",
    "unverified",
    "not_available",
    "not_applicable",
}
REVIEW_STATES = {"approved", "review_required", "blocked"}
FULL_COMMIT = re.compile(r"[0-9a-fA-F]{40}")
SHA256_DIGEST = re.compile(r"sha256:[0-9a-fA-F]{64}")
PACKAGE_WITH_DIGEST = re.compile(r"pkg:[^\s#]+@[^\s#]+#sha256=[0-9a-fA-F]{64}")
PLACEHOLDER_MARKERS = {"replace-with", "full commit sha", "sha256:digest"}


class ValidationError(ValueError):
    """A schema validation error with a JSON-path-like location."""


def is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


def fail(location: str, message: str) -> None:
    raise ValidationError(f"{location}: {message}")


def require_object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(location, "must be an object")
    return value


def require_list(value: Any, location: str, *, non_empty: bool = False) -> list[Any]:
    if not isinstance(value, list):
        fail(location, "must be an array")
    if non_empty and not value:
        fail(location, "must not be empty")
    return value


def require_string(
    value: Any, location: str, *, allow_placeholders: bool = True
) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(location, "must be a non-empty string")
    if not allow_placeholders:
        if is_placeholder(value):
            fail(location, "contains an unresolved template placeholder")
    return value


def require_string_list(
    value: Any,
    location: str,
    *,
    non_empty: bool = False,
    allow_placeholders: bool = True,
) -> list[str]:
    items = require_list(value, location, non_empty=non_empty)
    for index, item in enumerate(items):
        require_string(
            item,
            f"{location}[{index}]",
            allow_placeholders=allow_placeholders,
        )
    return items


def check_keys(
    value: dict[str, Any],
    location: str,
    *,
    required: set[str],
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    missing = sorted(required - value.keys())
    if missing:
        fail(location, f"missing required key(s): {', '.join(missing)}")
    unknown = sorted(value.keys() - required - optional)
    if unknown:
        fail(
            location,
            f"unknown key(s): {', '.join(unknown)}; use 'extensions' for custom data",
        )
    if "extensions" in value:
        require_object(value["extensions"], f"{location}.extensions")


def require_enum(value: Any, location: str, allowed: set[str]) -> str:
    item = require_string(value, location)
    if item not in allowed:
        fail(location, f"must be one of: {', '.join(sorted(allowed))}")
    return item


def require_iso8601(value: Any, location: str) -> str:
    timestamp = require_string(value, location)
    normalized = timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
    try:
        datetime.fromisoformat(normalized)
    except ValueError:
        fail(location, "must be an ISO 8601 timestamp")
    return timestamp


def check_unique(identifier: str, seen: set[str], location: str) -> None:
    if identifier in seen:
        fail(location, f"duplicate id: {identifier}")
    seen.add(identifier)


def validate_profile(
    document: dict[str, Any], *, allow_placeholders: bool = False
) -> None:
    check_keys(
        document,
        "$",
        required={
            "document_type",
            "schema_version",
            "repository",
            "controls",
            "exceptions",
        },
        optional={"extensions"},
    )

    repository = require_object(document["repository"], "$.repository")
    check_keys(
        repository,
        "$.repository",
        required={"id", "tier", "scope"},
        optional={"extensions"},
    )
    require_string(
        repository["id"],
        "$.repository.id",
        allow_placeholders=allow_placeholders,
    )
    tier = require_enum(repository["tier"], "$.repository.tier", TIERS)
    require_string(
        repository["scope"],
        "$.repository.scope",
        allow_placeholders=allow_placeholders,
    )

    controls = require_list(document["controls"], "$.controls", non_empty=True)
    seen_controls: set[str] = set()
    for index, raw_control in enumerate(controls):
        location = f"$.controls[{index}]"
        control = require_object(raw_control, location)
        check_keys(
            control,
            location,
            required={
                "control_id",
                "applicability",
                "decision",
                "trigger_evidence",
                "decision_rationale",
                "evidence",
                "risk_reduction",
                "operating_cost",
                "prerequisites",
                "failure_mode",
                "compensating_controls",
                "owner",
                "review_cadence",
            },
            optional={"extensions"},
        )
        control_id = require_enum(
            control["control_id"], f"{location}.control_id", CONTROL_IDS
        )
        check_unique(control_id, seen_controls, f"{location}.control_id")
        applicability = require_enum(
            control["applicability"],
            f"{location}.applicability",
            APPLICABILITY,
        )
        decision = require_enum(control["decision"], f"{location}.decision", DECISIONS)
        require_string_list(
            control["trigger_evidence"],
            f"{location}.trigger_evidence",
            non_empty=True,
            allow_placeholders=allow_placeholders,
        )
        require_string(
            control["decision_rationale"],
            f"{location}.decision_rationale",
            allow_placeholders=allow_placeholders,
        )
        require_string_list(
            control["evidence"],
            f"{location}.evidence",
            non_empty=True,
            allow_placeholders=allow_placeholders,
        )
        require_enum(control["risk_reduction"], f"{location}.risk_reduction", LEVELS)
        require_enum(control["operating_cost"], f"{location}.operating_cost", LEVELS)
        require_string_list(
            control["prerequisites"],
            f"{location}.prerequisites",
            non_empty=True,
            allow_placeholders=allow_placeholders,
        )
        require_string(
            control["failure_mode"],
            f"{location}.failure_mode",
            allow_placeholders=allow_placeholders,
        )
        compensating_controls = require_string_list(
            control["compensating_controls"],
            f"{location}.compensating_controls",
            allow_placeholders=allow_placeholders,
        )
        require_string(
            control["owner"],
            f"{location}.owner",
            allow_placeholders=allow_placeholders,
        )
        require_enum(control["review_cadence"], f"{location}.review_cadence", CADENCES)

        if decision == "not-applicable" and applicability not in {
            "conditional-not-triggered",
            "out-of-tier",
        }:
            fail(
                f"{location}.decision",
                "not-applicable requires conditional-not-triggered or out-of-tier applicability",
            )
        if (
            applicability in {"conditional-not-triggered", "out-of-tier"}
            and decision != "not-applicable"
        ):
            fail(
                f"{location}.decision",
                f"{applicability} applicability requires not-applicable",
            )
        if decision == "reject" and not compensating_controls:
            fail(
                f"{location}.compensating_controls",
                "must not be empty when decision is reject",
            )

    missing_controls = sorted(CONTROL_IDS - seen_controls)
    if missing_controls:
        fail("$.controls", f"missing catalog control(s): {', '.join(missing_controls)}")

    controls_by_id = {control["control_id"]: control for control in controls}
    required_for_tier = REQUIRED_BY_TIER[tier]
    conditional_for_tier = CONDITIONAL_BY_TIER[tier]
    for control_id in sorted(CONTROL_IDS):
        applicability = controls_by_id[control_id]["applicability"]
        location = f"$.controls[{control_id}].applicability"
        if control_id in required_for_tier and applicability != "required":
            fail(location, f"must be required for tier {tier}")
        if control_id in conditional_for_tier and applicability not in {
            "conditional-triggered",
            "conditional-not-triggered",
        }:
            fail(location, f"must be conditional for tier {tier}")
        if (
            control_id not in required_for_tier
            and control_id not in conditional_for_tier
            and applicability != "out-of-tier"
        ):
            fail(location, f"must be out-of-tier for tier {tier}")

    exceptions = require_list(document["exceptions"], "$.exceptions")
    seen_exceptions: set[str] = set()
    for index, raw_exception in enumerate(exceptions):
        location = f"$.exceptions[{index}]"
        exception = require_object(raw_exception, location)
        check_keys(
            exception,
            location,
            required={
                "exception_id",
                "control_id",
                "rationale",
                "compensating_control",
                "approved_by",
                "expires_or_review_at",
                "evidence",
            },
            optional={"extensions"},
        )
        exception_id = require_string(
            exception["exception_id"], f"{location}.exception_id"
        )
        check_unique(exception_id, seen_exceptions, f"{location}.exception_id")
        control_id = require_string(exception["control_id"], f"{location}.control_id")
        if control_id not in seen_controls:
            fail(f"{location}.control_id", "must reference a control in $.controls")
        require_string(exception["rationale"], f"{location}.rationale")
        require_string(
            exception["compensating_control"], f"{location}.compensating_control"
        )
        require_string(exception["approved_by"], f"{location}.approved_by")
        require_iso8601(
            exception["expires_or_review_at"], f"{location}.expires_or_review_at"
        )
        require_string_list(
            exception["evidence"], f"{location}.evidence", non_empty=True
        )


def validate_abom(
    document: dict[str, Any], *, allow_placeholders: bool = False
) -> None:
    check_keys(
        document,
        "$",
        required={
            "document_type",
            "schema_version",
            "generated_at",
            "source_revision",
            "entries",
        },
        optional={"extensions"},
    )
    require_iso8601(document["generated_at"], "$.generated_at")
    source_revision = require_string(
        document["source_revision"],
        "$.source_revision",
        allow_placeholders=allow_placeholders,
    )
    if not FULL_COMMIT.fullmatch(source_revision) and not (
        allow_placeholders and is_placeholder(source_revision)
    ):
        fail("$.source_revision", "must be a full 40-character commit SHA")

    entries = require_list(document["entries"], "$.entries", non_empty=True)
    seen_entries: set[str] = set()
    for index, raw_entry in enumerate(entries):
        location = f"$.entries[{index}]"
        entry = require_object(raw_entry, location)
        check_keys(
            entry,
            location,
            required={
                "entry_id",
                "kind",
                "consumer",
                "source",
                "immutable_ref",
                "version_annotation",
                "minimum_age_days",
                "permissions",
                "provenance",
                "review_status",
                "evidence",
            },
            optional={"extensions"},
        )
        entry_id = require_string(entry["entry_id"], f"{location}.entry_id")
        check_unique(entry_id, seen_entries, f"{location}.entry_id")
        require_enum(entry["kind"], f"{location}.kind", ABOM_KINDS)
        require_string(
            entry["consumer"],
            f"{location}.consumer",
            allow_placeholders=allow_placeholders,
        )
        require_string(
            entry["source"],
            f"{location}.source",
            allow_placeholders=allow_placeholders,
        )
        immutable_ref = require_string(
            entry["immutable_ref"],
            f"{location}.immutable_ref",
            allow_placeholders=allow_placeholders,
        )
        require_string(
            entry["version_annotation"],
            f"{location}.version_annotation",
            allow_placeholders=allow_placeholders,
        )
        if not (allow_placeholders and is_placeholder(immutable_ref)):
            kind = entry["kind"]
            if kind in {"github_action", "reusable_workflow", "composite_action"}:
                if not FULL_COMMIT.fullmatch(immutable_ref):
                    fail(
                        f"{location}.immutable_ref",
                        "GitHub and local action inputs require a full 40-character commit SHA",
                    )
            elif kind == "container_image":
                if not SHA256_DIGEST.fullmatch(immutable_ref):
                    fail(
                        f"{location}.immutable_ref",
                        "container inputs require a sha256 digest",
                    )
            elif kind == "build_utility" and not (
                FULL_COMMIT.fullmatch(immutable_ref)
                or SHA256_DIGEST.fullmatch(immutable_ref)
                or PACKAGE_WITH_DIGEST.fullmatch(immutable_ref)
            ):
                fail(
                    f"{location}.immutable_ref",
                    "build utilities require a commit, sha256 digest, or package URL with sha256",
                )
        minimum_age = entry["minimum_age_days"]
        if isinstance(minimum_age, bool) or not isinstance(minimum_age, int):
            fail(f"{location}.minimum_age_days", "must be a non-negative integer")
        if minimum_age < 0:
            fail(f"{location}.minimum_age_days", "must be a non-negative integer")
        require_string_list(entry["permissions"], f"{location}.permissions")
        require_enum(entry["provenance"], f"{location}.provenance", PROVENANCE_STATES)
        require_enum(entry["review_status"], f"{location}.review_status", REVIEW_STATES)
        require_string_list(
            entry["evidence"],
            f"{location}.evidence",
            non_empty=True,
            allow_placeholders=allow_placeholders,
        )


def validate_document(document: Any, *, allow_placeholders: bool = False) -> str:
    root = require_object(document, "$")
    document_type = require_string(root.get("document_type"), "$.document_type")
    schema_version = require_string(root.get("schema_version"), "$.schema_version")
    if schema_version != SCHEMA_VERSION:
        fail("$.schema_version", f"must equal {SCHEMA_VERSION!r}")

    if document_type == PROFILE_TYPE:
        validate_profile(root, allow_placeholders=allow_placeholders)
    elif document_type == ABOM_TYPE:
        validate_abom(root, allow_placeholders=allow_placeholders)
    else:
        fail(
            "$.document_type",
            f"must be {PROFILE_TYPE!r} or {ABOM_TYPE!r}",
        )
    return document_type


def validate_path(path: Path, *, allow_placeholders: bool = False) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            document = json.load(handle)
    except OSError as error:
        raise ValidationError(f"cannot read file: {error}") from error
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    return validate_document(document, allow_placeholders=allow_placeholders)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate agent-toolkit repository security profiles and generated "
            "Action Bills of Materials."
        )
    )
    parser.add_argument(
        "files", nargs="+", type=Path, help="JSON document(s) to validate"
    )
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="lint a shipped template without accepting it as a completed profile",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    invalid = False
    for path in args.files:
        try:
            document_type = validate_path(
                path, allow_placeholders=args.allow_placeholders
            )
        except ValidationError as error:
            invalid = True
            print(f"{path}: invalid: {error}", file=sys.stderr)
        else:
            print(f"{path}: valid {document_type} schema {SCHEMA_VERSION}")
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main())
