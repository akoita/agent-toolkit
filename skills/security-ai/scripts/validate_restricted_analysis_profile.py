#!/usr/bin/env python3
"""Validate the fail-closed structure of a restricted analysis profile."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


ROOT_KEYS = {
    "schema_version",
    "profile_name",
    "source",
    "artifacts",
    "credentials",
    "network",
    "tools",
    "limits",
    "capture",
    "approval",
}
SOURCE_KEYS = {
    "repository",
    "commit",
    "analysis_mode",
    "root_absolute_path",
    "mount_mode",
    "allowed_paths",
    "excluded_paths",
    "reject_symlink_escape",
    "treat_contents_as_untrusted",
}
ARTIFACT_KEYS = {
    "directory_absolute_path",
    "must_be_outside_repository",
    "posix_mode",
    "public_upload_allowed",
    "retention_days",
}
CREDENTIAL_KEYS = {
    "repository_credentials_present",
    "cloud_credentials_present",
    "package_publish_credentials_present",
    "deployment_credentials_present",
    "signing_or_wallet_credentials_present",
    "host_environment_passthrough",
    "allowed_environment_variables",
    "model_auth_location",
    "model_auth_visible_to_model_tools",
}
NETWORK_KEYS = {
    "mode",
    "allowed_destinations",
    "general_dns_allowed",
    "private_networks_allowed",
    "cloud_metadata_allowed",
    "listeners_allowed",
    "log_policy_violations",
}
TOOL_KEYS = {"allowed", "denied", "model_may_expand_allowlist"}
LIMIT_KEYS = {
    "timeout_seconds",
    "max_cost_usd",
    "max_subagents",
    "cpu_limit",
    "memory_limit",
}
CAPTURE_KEYS = {
    "started_at",
    "completed_at",
    "host_os",
    "architecture",
    "sandbox_runtime",
    "sandbox_image_digest",
    "model_provider",
    "model_identifier",
    "inference_parameters",
    "harness_version",
    "tool_versions",
    "configuration_sha256",
    "security_context_sha256",
    "exit_status",
    "coverage",
}
APPROVAL_KEYS = {
    "findings_are_advisory",
    "model_may_block_merge_or_release",
    "model_may_mutate_source",
    "model_may_change_severity_or_disclosure",
    "human_approver",
    "approval_required_before_reproduction",
    "approval_required_before_code_or_state_change",
}

ALLOWED_TOOLS = {
    "scoped_file_read",
    "scoped_repository_search",
    "predeclared_deterministic_analysis",
}
MANDATORY_DENIALS = {
    "file_write",
    "file_edit",
    "arbitrary_shell",
    "package_install",
    "git_mutation",
    "repository_write_api",
    "messaging",
    "secret_access",
    "deployment",
    "cloud_control",
    "browser_automation",
    "unrestricted_mcp",
}
FORBIDDEN_ENV_NAMES = {
    "HOME",
    "USERPROFILE",
    "NETRC",
    "SSH_AUTH_SOCK",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "NPM_TOKEN",
    "PYPI_TOKEN",
}
FORBIDDEN_ENV_PREFIXES = {
    "AWS_",
    "AZURE_",
    "GCP_",
    "GOOGLE_",
    "GITHUB_",
    "GH_",
    "OPENAI_",
    "ANTHROPIC_",
    "NPM_",
    "PYPI_",
    "TWINE_",
    "DOCKER_",
    "KUBE_",
    "VAULT_",
    "SSH_",
}
FORBIDDEN_ENV_FRAGMENTS = {"TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY"}
CAPTURE_COVERAGE = {"planned", "complete", "partial", "unknown"}


class ValidationError(ValueError):
    """A profile validation error."""


def fail(location: str, message: str) -> None:
    raise ValidationError(f"{location}: {message}")


def obj(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(location, "must be an object")
    return value


def exact_object(value: Any, location: str, keys: set[str]) -> dict[str, Any]:
    record = obj(value, location)
    missing = sorted(keys - record.keys())
    if missing:
        fail(location, f"missing required key(s): {', '.join(missing)}")
    unknown = sorted(record.keys() - keys)
    if unknown:
        fail(location, f"unknown key(s): {', '.join(unknown)}")
    return record


def string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(location, "must be a non-empty string")
    if value != value.strip():
        fail(location, "must not have leading or trailing whitespace")
    return value


def nullable_string(value: Any, location: str) -> str | None:
    if value is None:
        return None
    return string(value, location)


def false(value: Any, location: str) -> None:
    if value is not False:
        fail(location, "must be false")


def true(value: Any, location: str) -> None:
    if value is not True:
        fail(location, "must be true")


def integer(value: Any, location: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        fail(location, "must be an integer")
    if minimum is not None and value < minimum:
        fail(location, f"must be at least {minimum}")
    return value


def finite_number(value: Any, location: str, *, minimum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(location, "must be a number")
    number = float(value)
    if not math.isfinite(number):
        fail(location, "must be finite")
    if number < minimum:
        fail(location, f"must be at least {minimum:g}")
    return number


def string_list(
    value: Any,
    location: str,
    *,
    non_empty: bool = False,
    reject_duplicates: bool = True,
) -> list[str]:
    if not isinstance(value, list):
        fail(location, "must be an array")
    if non_empty and not value:
        fail(location, "must be a non-empty array")
    items: list[str] = []
    seen: set[str] = set()
    for index, raw_item in enumerate(value):
        item = string(raw_item, f"{location}[{index}]")
        if reject_duplicates and item in seen:
            fail(f"{location}[{index}]", f"duplicate value: {item}")
        seen.add(item)
        items.append(item)
    return items


def absolute_normalized_path(value: Any, location: str) -> str:
    path = string(value, location)
    if not os.path.isabs(path):
        fail(location, "must be absolute")
    normalized = os.path.normpath(path)
    if normalized != path:
        fail(location, "must be normalized")
    return normalized


def is_within(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def contained_paths(
    value: Any, location: str, source_root: str, *, non_empty: bool
) -> list[str]:
    raw_paths = string_list(value, location, non_empty=non_empty)
    paths: list[str] = []
    for index, raw_path in enumerate(raw_paths):
        path = absolute_normalized_path(raw_path, f"{location}[{index}]")
        if not is_within(path, source_root):
            fail(f"{location}[{index}]", "must remain inside source root")
        paths.append(path)
    return paths


def https_endpoint(value: Any, location: str) -> str:
    endpoint = string(value, location)
    parsed = urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.netloc or not parsed.hostname:
        fail(location, "must be an absolute HTTPS endpoint")
    if parsed.username is not None or parsed.password is not None:
        fail(location, "must not contain embedded credentials")
    if parsed.fragment:
        fail(location, "must not contain a fragment")
    return endpoint


def validate_environment_names(value: Any, location: str) -> None:
    names = string_list(value, location, non_empty=True)
    for index, name in enumerate(names):
        upper = name.upper()
        if not upper.replace("_", "A").isalnum() or upper[0].isdigit():
            fail(f"{location}[{index}]", "must be an environment variable name")
        if (
            upper in FORBIDDEN_ENV_NAMES
            or any(upper.startswith(prefix) for prefix in FORBIDDEN_ENV_PREFIXES)
            or any(fragment in upper for fragment in FORBIDDEN_ENV_FRAGMENTS)
        ):
            fail(f"{location}[{index}]", "credential-bearing variable is not allowed")


def validate_string_map(value: Any, location: str) -> None:
    record = obj(value, location)
    for key, item in record.items():
        string(key, f"{location}.<key>")
        string(item, f"{location}.{key}")


def validate(document: Any) -> None:
    root = exact_object(document, "$", ROOT_KEYS)
    if root["schema_version"] != "1.0":
        fail("$.schema_version", "must equal '1.0'")
    if root["profile_name"] != "restricted-vulnerability-analysis":
        fail("$.profile_name", "must equal 'restricted-vulnerability-analysis'")

    source = exact_object(root["source"], "$.source", SOURCE_KEYS)
    string(source["repository"], "$.source.repository")
    string(source["commit"], "$.source.commit")
    if source["analysis_mode"] != "source_at_rest":
        fail("$.source.analysis_mode", "must equal 'source_at_rest'")
    if source["mount_mode"] != "read_only":
        fail("$.source.mount_mode", "must equal 'read_only'")
    source_root = absolute_normalized_path(
        source["root_absolute_path"], "$.source.root_absolute_path"
    )
    contained_paths(
        source["allowed_paths"],
        "$.source.allowed_paths",
        source_root,
        non_empty=True,
    )
    contained_paths(
        source["excluded_paths"],
        "$.source.excluded_paths",
        source_root,
        non_empty=False,
    )
    true(source["reject_symlink_escape"], "$.source.reject_symlink_escape")
    true(source["treat_contents_as_untrusted"], "$.source.treat_contents_as_untrusted")

    artifacts = exact_object(root["artifacts"], "$.artifacts", ARTIFACT_KEYS)
    artifact_path = absolute_normalized_path(
        artifacts["directory_absolute_path"], "$.artifacts.directory_absolute_path"
    )
    if is_within(artifact_path, source_root):
        fail("$.artifacts.directory_absolute_path", "must be outside source root")
    true(
        artifacts["must_be_outside_repository"],
        "$.artifacts.must_be_outside_repository",
    )
    if artifacts["posix_mode"] != "0700":
        fail("$.artifacts.posix_mode", "must equal '0700'")
    false(artifacts["public_upload_allowed"], "$.artifacts.public_upload_allowed")
    integer(artifacts["retention_days"], "$.artifacts.retention_days", minimum=1)

    credentials = exact_object(root["credentials"], "$.credentials", CREDENTIAL_KEYS)
    for name in {
        "repository_credentials_present",
        "cloud_credentials_present",
        "package_publish_credentials_present",
        "deployment_credentials_present",
        "signing_or_wallet_credentials_present",
        "host_environment_passthrough",
        "model_auth_visible_to_model_tools",
    }:
        false(credentials[name], f"$.credentials.{name}")
    validate_environment_names(
        credentials["allowed_environment_variables"],
        "$.credentials.allowed_environment_variables",
    )
    if credentials["model_auth_location"] != "trusted_proxy_or_launcher":
        fail(
            "$.credentials.model_auth_location",
            "must equal 'trusted_proxy_or_launcher'",
        )

    network = exact_object(root["network"], "$.network", NETWORK_KEYS)
    if network["mode"] not in {"disabled", "model_proxy_only"}:
        fail("$.network.mode", "must be 'disabled' or 'model_proxy_only'")
    destinations = network["allowed_destinations"]
    if not isinstance(destinations, list):
        fail("$.network.allowed_destinations", "must be an array")
    if network["mode"] == "disabled":
        if destinations:
            fail(
                "$.network.allowed_destinations",
                "must be empty when network is disabled",
            )
    else:
        if len(destinations) != 1:
            fail(
                "$.network.allowed_destinations",
                "must name exactly one model proxy",
            )
        https_endpoint(destinations[0], "$.network.allowed_destinations[0]")
    for name in {
        "general_dns_allowed",
        "private_networks_allowed",
        "cloud_metadata_allowed",
        "listeners_allowed",
    }:
        false(network[name], f"$.network.{name}")
    true(network["log_policy_violations"], "$.network.log_policy_violations")

    tools = exact_object(root["tools"], "$.tools", TOOL_KEYS)
    allowed_tools = set(
        string_list(tools["allowed"], "$.tools.allowed", non_empty=True)
    )
    unknown_allowed = sorted(allowed_tools - ALLOWED_TOOLS)
    if unknown_allowed:
        fail("$.tools.allowed", f"unsupported capability: {', '.join(unknown_allowed)}")
    denied_tools = set(string_list(tools["denied"], "$.tools.denied", non_empty=True))
    missing_denials = sorted(MANDATORY_DENIALS - denied_tools)
    if missing_denials:
        fail("$.tools.denied", f"missing denial(s): {', '.join(missing_denials)}")
    overlap = sorted(allowed_tools & denied_tools)
    if overlap:
        fail(
            "$.tools",
            f"capabilities cannot be both allowed and denied: {', '.join(overlap)}",
        )
    false(tools["model_may_expand_allowlist"], "$.tools.model_may_expand_allowlist")

    limits = exact_object(root["limits"], "$.limits", LIMIT_KEYS)
    integer(limits["timeout_seconds"], "$.limits.timeout_seconds", minimum=1)
    finite_number(limits["max_cost_usd"], "$.limits.max_cost_usd", minimum=0)
    max_subagents = integer(limits["max_subagents"], "$.limits.max_subagents")
    if max_subagents != 0:
        fail("$.limits.max_subagents", "must equal 0")
    string(limits["cpu_limit"], "$.limits.cpu_limit")
    string(limits["memory_limit"], "$.limits.memory_limit")

    capture = exact_object(root["capture"], "$.capture", CAPTURE_KEYS)
    string(capture["started_at"], "$.capture.started_at")
    nullable_string(capture["completed_at"], "$.capture.completed_at")
    for name in {
        "host_os",
        "architecture",
        "sandbox_runtime",
        "sandbox_image_digest",
        "model_provider",
        "model_identifier",
        "harness_version",
        "configuration_sha256",
        "security_context_sha256",
    }:
        string(capture[name], f"$.capture.{name}")
    obj(capture["inference_parameters"], "$.capture.inference_parameters")
    validate_string_map(capture["tool_versions"], "$.capture.tool_versions")
    exit_status = capture["exit_status"]
    if exit_status is not None:
        if isinstance(exit_status, bool) or not isinstance(exit_status, (int, str)):
            fail("$.capture.exit_status", "must be null, an integer, or a string")
        if isinstance(exit_status, str):
            string(exit_status, "$.capture.exit_status")
    if capture["coverage"] not in CAPTURE_COVERAGE:
        fail(
            "$.capture.coverage",
            f"must be one of: {', '.join(sorted(CAPTURE_COVERAGE))}",
        )

    approval = exact_object(root["approval"], "$.approval", APPROVAL_KEYS)
    for name in {
        "model_may_block_merge_or_release",
        "model_may_mutate_source",
        "model_may_change_severity_or_disclosure",
    }:
        false(approval[name], f"$.approval.{name}")
    for name in {
        "findings_are_advisory",
        "approval_required_before_reproduction",
        "approval_required_before_code_or_state_change",
    }:
        true(approval[name], f"$.approval.{name}")
    string(approval["human_approver"], "$.approval.human_approver")


def validate_path(path: Path) -> None:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValidationError(f"cannot read file: {error}") from error
    except json.JSONDecodeError as error:
        raise ValidationError(
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error
    validate(document)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    invalid = False
    for path in args.files:
        try:
            validate_path(path)
        except ValidationError as error:
            invalid = True
            print(f"{path}: invalid: {error}", file=sys.stderr)
        else:
            print(f"{path}: valid restricted analysis profile schema 1.0")
    return 1 if invalid else 0


if __name__ == "__main__":
    sys.exit(main())
