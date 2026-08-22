#!/usr/bin/env python3
"""Check whether Codex Maestro's declared and effective routing is working.

The default check is local and does not run a model.  ``--live`` is an
explicit opt-in probe: it runs one minimal native child workflow and inspects
the persisted child rollout for effective role, model, and effort evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROUTING_CONTRACT_VERSION = 1
EXPECTED_MODEL = "gpt-5.6-luna"
EXPECTED_EFFORT = "xhigh"
EXPECTED_ROOT_MODEL = "gpt-5.6-sol"
EXPECTED_ROOT_EFFORT = "medium"
EXPECTED_IMPLEMENTATION_ROLE = "implementation_worker"
EXPECTED_EXPLORATION_ROLE = "exploration_worker"
EXPECTED_WORKER_ROLES = (
    EXPECTED_IMPLEMENTATION_ROLE,
    EXPECTED_EXPLORATION_ROLE,
)
AGENT_FILES = {
    EXPECTED_IMPLEMENTATION_ROLE: {
        "filename": "implementation-worker.toml",
        "read_only": False,
    },
    EXPECTED_EXPLORATION_ROLE: {
        "filename": "exploration-worker.toml",
        "read_only": True,
    },
}
CONFIG_OVERRIDES = (
    f'agents.default_subagent_model="{EXPECTED_MODEL}"',
    f'agents.default_subagent_reasoning_effort="{EXPECTED_EFFORT}"',
)
ROOT_CONFIG_OVERRIDES = ('model_reasoning_effort="medium"',)
VERSION_PATTERN = re.compile(r"(?<![0-9])([0-9]+\.[0-9]+\.[0-9]+)(?![0-9])")
AUTH_FAILURE_MARKERS = (
    "authentication required",
    "auth required",
    "no authentication",
    "authentication method",
    "not logged in",
    "unauthorized",
    "missing credentials",
    "no credentials",
    "api key",
    "log in",
    "login required",
)
SUPPORT_FAILURE_MARKERS = (
    "unknown option",
    "unrecognized option",
    "unsupported",
    "does not support",
    "multi-agent feature",
    "subagent support",
    "unknown config",
    "unknown field",
)
ATTESTATION_FILENAME = "routing-attestation.json"
ATTESTATION_MAX_AGE_SECONDS = 24 * 60 * 60
FUTURE_TIMESTAMP_TOLERANCE_SECONDS = 5 * 60


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="emit machine-readable JSON instead of concise human output",
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--live",
        action="store_true",
        help="opt in to one native child workflow (consumes model tokens)",
    )
    modes.add_argument(
        "--enforce",
        action="store_true",
        help="enforce a fresh attestation and the current root route",
    )
    modes.add_argument(
        "--worker-rollout",
        type=Path,
        help="verify one persisted worker rollout without running Codex",
    )
    parser.add_argument(
        "--role",
        "--expected-role",
        "--worker-role",
        dest="expected_role",
        help="expected worker role for --worker-rollout",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
        help="Codex home containing agents/ and persisted sessions",
    )
    parser.add_argument(
        "--agents-dir",
        type=Path,
        help="custom-agent directory (default: <codex-home>/agents)",
    )
    parser.add_argument(
        "--codex",
        dest="codex_path",
        help="Codex executable or PATH name (default: codex)",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=Path.cwd(),
        help="working directory for the opt-in live probe",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="per-command timeout in seconds (default: 180)",
    )
    parser.add_argument(
        "--attestation",
        "--attestation-path",
        dest="attestation_path",
        type=Path,
        help="override the compatibility attestation path (for tests)",
    )
    parser.add_argument(
        "--thread-id",
        "--root-thread-id",
        dest="root_thread_id",
        help="current root Codex thread ID for --enforce",
    )
    parser.add_argument(
        "--session-id",
        "--root-session-id",
        dest="root_session_id",
        help="current root Codex session ID for --enforce",
    )
    parser.add_argument(
        "--root-rollout",
        type=Path,
        help="explicit current root rollout path for --enforce",
    )
    return parser.parse_args(argv)


def check(
    name: str,
    status: str,
    message: str,
    **details: Any,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "name": name,
        "status": status,
        "message": message,
    }
    if details:
        value["details"] = details
    return value


def walk_json(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def json_documents(text: str) -> list[Any]:
    """Parse one JSON document or JSONL without accepting arbitrary text."""

    stripped = text.strip()
    if not stripped:
        return []
    try:
        return [json.loads(stripped)]
    except json.JSONDecodeError:
        documents = []
        for line in stripped.splitlines():
            try:
                documents.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return documents


def status_value(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_")
    if normalized in {"ok", "pass", "passed", "success", "healthy"}:
        return "ok"
    if normalized in {"skip", "skipped", "unavailable"}:
        return "skipped"
    if normalized in {"fail", "failed", "error", "unhealthy"}:
        return "fail"
    return None


def check_status(document: Any, check_id: str) -> tuple[str | None, dict[str, Any]]:
    """Find a named check in tolerant Codex doctor JSON shapes."""

    for node in walk_json(document):
        if not isinstance(node, dict):
            continue
        candidate = node.get(check_id)
        if isinstance(candidate, dict):
            status = status_value(
                candidate.get("status")
                or candidate.get("state")
                or candidate.get("result")
            )
            if status:
                return status, candidate
        elif isinstance(candidate, str):
            status = status_value(candidate)
            if status:
                return status, {"status": candidate}

        identifier = node.get("id") or node.get("name") or node.get("check")
        if identifier == check_id:
            status = status_value(
                node.get("status") or node.get("state") or node.get("result")
            )
            if status:
                return status, node
    return None, {}


def resolve_codex(explicit: str | None) -> str | None:
    if explicit:
        return shutil.which(explicit) or (
            str(Path(explicit).expanduser())
            if Path(explicit).expanduser().is_file()
            else None
        )
    return shutil.which("codex")


def run_command(
    command: list[str],
    *,
    timeout: float,
    cwd: Path | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None


def version_check(
    codex: str | None,
    *,
    timeout: float,
) -> tuple[dict[str, Any], str | None]:
    if not codex:
        return check("codex.version", "fail", "codex CLI was not found on PATH"), None

    process = run_command([codex, "--version"], timeout=timeout)
    if process is None:
        return check("codex.version", "fail", "codex --version could not run"), None
    output = f"{process.stdout}\n{process.stderr}"
    match = VERSION_PATTERN.search(output)
    if process.returncode != 0 or not match:
        return (
            check(
                "codex.version",
                "fail",
                "codex --version did not return a parseable version",
                returncode=process.returncode,
            ),
            None,
        )
    return (
        check(
            "codex.version",
            "ok",
            "Codex CLI is installed",
            version=match.group(1),
        ),
        match.group(1),
    )


def doctor_check(
    codex: str,
    *,
    timeout: float,
    overrides: tuple[str, ...] = (),
    name: str,
) -> dict[str, Any]:
    command = [codex, "doctor", "--json"]
    for override in overrides:
        command.extend(["--config", override])
    process = run_command(command, timeout=timeout)
    if process is None:
        return check(name, "fail", "codex doctor --json could not run")

    documents = json_documents(process.stdout)
    status: str | None = None
    evidence: dict[str, Any] = {}
    for document in documents:
        status, evidence = check_status(document, "config.load")
        if status:
            break
    if status is None:
        return check(
            name,
            "fail",
            "codex doctor --json did not report config.load",
            returncode=process.returncode,
        )
    if status != "ok":
        return check(
            name,
            "fail",
            "codex doctor reports config.load is not OK",
            returncode=process.returncode,
            doctor_status=status,
            summary=evidence.get("summary"),
        )
    details: dict[str, Any] = {"returncode": process.returncode}
    if evidence.get("summary"):
        details["summary"] = evidence["summary"]
    if process.returncode:
        details["note"] = "doctor had other failing checks; config.load is OK"
    return check(name, "ok", "codex doctor reports config.load OK", **details)


def agent_templates_check(agents_dir: Path) -> dict[str, Any]:
    failures: list[str] = []
    resolved: dict[str, str] = {}
    for role, expected in AGENT_FILES.items():
        path = agents_dir / str(expected["filename"])
        if not path.is_file():
            failures.append(f"{role}: missing {path}")
            continue
        try:
            with path.open("rb") as stream:
                values = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as error:
            failures.append(f"{role}: invalid TOML ({error})")
            continue

        resolved[role] = str(path)
        if values.get("name") != role:
            failures.append(
                f"{role}: name is {values.get('name')!r}, expected {role!r}"
            )
        if values.get("model") != EXPECTED_MODEL:
            failures.append(
                f"{role}: model is {values.get('model')!r}, expected {EXPECTED_MODEL!r}"
            )
        if values.get("model_reasoning_effort") != EXPECTED_EFFORT:
            failures.append(
                f"{role}: effort is {values.get('model_reasoning_effort')!r}, expected {EXPECTED_EFFORT!r}"
            )
        if expected["read_only"] and values.get("sandbox_mode") != "read-only":
            failures.append(
                f"{role}: sandbox_mode is {values.get('sandbox_mode')!r}, expected 'read-only'"
            )

    if failures:
        return check(
            "agents.templates",
            "fail",
            "required custom-agent TOMLs do not match the routing contract",
            agents_dir=str(agents_dir),
            failures=failures,
            resolved=resolved,
        )
    return check(
        "agents.templates",
        "ok",
        "required custom-agent TOMLs resolve with Luna/xhigh",
        agents_dir=str(agents_dir),
        resolved=resolved,
    )


def offline_checks(
    *,
    codex: str | None,
    agents_dir: Path,
    timeout: float,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    version_result, _ = version_check(codex, timeout=timeout)
    results.append(version_result)
    results.append(agent_templates_check(agents_dir))
    if codex:
        results.append(
            doctor_check(
                codex,
                timeout=timeout,
                name="doctor.config.load",
            )
        )
        override_result = doctor_check(
            codex,
            timeout=timeout,
            overrides=CONFIG_OVERRIDES,
            name="config.subagent_overrides",
        )
        if override_result["status"] == "ok":
            override_result["message"] = (
                "Codex accepts default subagent model/effort overrides"
            )
        results.append(override_result)
    return results


def sha256_file(path: Path) -> str | None:
    """Return a file digest, or ``None`` when the file is absent/unreadable."""

    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except (OSError, ValueError):
        return None


def default_attestation_path(codex_home: Path) -> Path:
    return codex_home / "maestro" / ATTESTATION_FILENAME


def _canonical_paths(
    codex_home: Path,
    agents_dir: Path | None = None,
    *,
    checker_path: Path | None = None,
    skill_path: Path | None = None,
    config_path: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    script_path = (checker_path or Path(__file__)).expanduser().resolve()
    canonical_skill = skill_path or script_path.parent.parent / "SKILL.md"
    config = config_path or codex_home / "config.toml"
    agents = agents_dir or codex_home / "agents"
    return script_path, canonical_skill, config, agents


def discover_package_version(start_path: Path | None = None) -> str | None:
    """Find a nearby Maestro/plugin version without persisting its path."""

    start = Path(start_path or __file__).expanduser()
    current = start if start.is_dir() else start.parent
    for ancestor in (current, *current.parents):
        candidates = (
            ancestor / "plugin.json",
            ancestor / ".codex-plugin" / "plugin.json",
        )
        for candidate in candidates:
            try:
                with candidate.open(encoding="utf-8") as stream:
                    metadata = json.load(stream)
            except (OSError, UnicodeError, json.JSONDecodeError):
                continue
            if not isinstance(metadata, dict):
                continue
            name = metadata.get("name")
            version = metadata.get("version")
            if name is not None and name != "codex-maestro":
                continue
            if isinstance(version, str) and version.strip():
                return version.strip()
    return None


def compatibility_fingerprint(
    codex_version: str | None,
    codex_home: Path,
    agents_dir: Path | None = None,
    checker_path: Path | None = None,
    skill_path: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Build a path-free fingerprint for the routing compatibility contract.

    The returned value intentionally contains only versions, declarations and
    digests.  In particular, it never includes configuration text or local
    paths, so it is safe to persist in the attestation file.
    """

    script, skill, config, agents = _canonical_paths(
        codex_home,
        agents_dir,
        checker_path=checker_path,
        skill_path=skill_path,
        config_path=config_path,
    )
    agent_hashes = {
        role: sha256_file(agents / str(expected["filename"]))
        for role, expected in AGENT_FILES.items()
    }
    return {
        "contract_version": ROUTING_CONTRACT_VERSION,
        "codex_version": codex_version,
        "package_version": discover_package_version(script),
        "routes": {
            "root": {
                "model": EXPECTED_ROOT_MODEL,
                "effort": EXPECTED_ROOT_EFFORT,
            },
            "workers": {
                role: {"model": EXPECTED_MODEL, "effort": EXPECTED_EFFORT}
                for role in EXPECTED_WORKER_ROLES
            },
        },
        "hashes": {
            "checker": sha256_file(script),
            "skill": sha256_file(skill),
            "config": sha256_file(config),
            "agents": agent_hashes,
        },
    }


# Descriptive alias retained for callers that use the older terminology.
build_compatibility_fingerprint = compatibility_fingerprint
routing_fingerprint = compatibility_fingerprint


def _timestamp_value(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        number = float(value)
        return number if math.isfinite(number) else None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except ValueError:
        pass
    try:
        normalized = value.strip().replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _fingerprint_differences(expected: Any, actual: Any, prefix: str = "") -> list[str]:
    if isinstance(expected, dict) and isinstance(actual, dict):
        keys = sorted(set(expected) | set(actual))
        differences: list[str] = []
        for key in keys:
            name = f"{prefix}.{key}" if prefix else str(key)
            if key not in expected or key not in actual:
                differences.append(name)
            else:
                differences.extend(
                    _fingerprint_differences(expected[key], actual[key], name)
                )
        return differences
    if expected != actual:
        return [prefix or "fingerprint"]
    return []


def read_attestation(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read and minimally validate an attestation without exposing its data."""

    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream)
    except FileNotFoundError:
        return None, "missing"
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, "unreadable or malformed"
    if not isinstance(value, dict):
        return None, "malformed"
    if value.get("version") != ROUTING_CONTRACT_VERSION:
        return None, "unsupported version"
    timestamp = _timestamp_value(value.get("timestamp", value.get("created_at")))
    fingerprint = value.get("fingerprint")
    if timestamp is None or not isinstance(fingerprint, dict):
        return None, "malformed"
    if value.get("status", "ok") != "ok":
        return None, "not successful"
    return value, None


def attestation_check(
    *,
    path: Path,
    fingerprint: dict[str, Any],
    now: float | None = None,
    max_age: float | None = None,
) -> dict[str, Any]:
    value, error = read_attestation(path)
    if value is None:
        return check(
            "attestation.compatibility",
            "fail",
            f"compatibility attestation is {error}",
        )
    timestamp = _timestamp_value(value.get("timestamp", value.get("created_at")))
    assert timestamp is not None
    current = time.time() if now is None else now
    age = current - timestamp
    if age < -FUTURE_TIMESTAMP_TOLERANCE_SECONDS:
        return check(
            "attestation.compatibility",
            "fail",
            "compatibility attestation timestamp is materially in the future",
            reason="timestamp is ahead of the local clock",
        )
    if max_age is not None and age > max_age:
        return check(
            "attestation.compatibility",
            "fail",
            "compatibility attestation is stale",
            reason="timestamp outside explicit freshness window",
        )
    differences = _fingerprint_differences(fingerprint, value["fingerprint"])
    if differences:
        return check(
            "attestation.compatibility",
            "fail",
            "compatibility attestation is stale",
            reason="compatibility fingerprint changed",
            changed_fields=differences,
        )
    return check(
        "attestation.compatibility",
        "ok",
        "fresh compatibility attestation matches the routing contract",
    )


check_attestation = attestation_check
load_attestation = read_attestation


def write_attestation(
    path: Path,
    fingerprint: dict[str, Any],
    *,
    proof: dict[str, Any] | None = None,
    timestamp: float | str | None = None,
) -> None:
    """Atomically write a mode-0600 routing attestation.

    The temporary file is created in the destination directory, flushed to
    disk, and replaced into place.  A failed write leaves no temporary file.
    """

    path = path.expanduser()
    parent = path.parent
    parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    if timestamp is None:
        timestamp = time.time()
    payload: dict[str, Any] = {
        "version": ROUTING_CONTRACT_VERSION,
        "timestamp": timestamp,
        "fingerprint": fingerprint,
    }
    if proof is not None:
        payload["proof"] = proof
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = stream.name
            os.chmod(stream.name, 0o600)
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary:
            try:
                Path(temporary).unlink()
            except FileNotFoundError:
                pass
            except OSError:
                pass


# Explicit alias for tests and callers that prefer the operation name.
atomic_write_attestation = write_attestation


def rollout_roots(codex_home: Path) -> tuple[Path, ...]:
    return (codex_home / "sessions", codex_home / "archived_sessions")


def rollout_snapshot(codex_home: Path) -> dict[Path, tuple[int, int]]:
    snapshot: dict[Path, tuple[int, int]] = {}
    for root in rollout_roots(codex_home):
        if not root.is_dir():
            continue
        for path in root.rglob("*.jsonl"):
            try:
                stat = path.stat()
            except OSError:
                continue
            snapshot[path] = (stat.st_mtime_ns, stat.st_size)
    return snapshot


def changed_rollouts(
    codex_home: Path,
    before: dict[Path, tuple[int, int]],
) -> list[Path]:
    after = rollout_snapshot(codex_home)
    return sorted(
        path for path, signature in after.items() if before.get(path) != signature
    )


def first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _metadata_string(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _turn_context_values(payload: Any) -> tuple[str | None, str | None, str | None]:
    if not isinstance(payload, dict):
        return None, None, "turn_context payload is not an object"
    settings = payload.get("collaboration_mode")
    settings = settings.get("settings") if isinstance(settings, dict) else {}
    model = first_string(
        payload.get("model"),
        settings.get("model") if isinstance(settings, dict) else None,
    )
    effort = first_string(
        payload.get("effort"),
        payload.get("reasoning_effort"),
        settings.get("reasoning_effort") if isinstance(settings, dict) else None,
    )
    if model is None or effort is None:
        return model, effort, "turn_context is missing model or effort"
    return model, effort, None


def _session_metadata(payload: Any) -> tuple[dict[str, Any], str | None]:
    if not isinstance(payload, dict):
        return {}, "session_meta payload is not an object"
    source = payload.get("source")
    subagent = source.get("subagent") if isinstance(source, dict) else None
    spawn = subagent.get("thread_spawn") if isinstance(subagent, dict) else None
    role = None
    if isinstance(spawn, dict):
        role = _metadata_string(spawn.get("agent_role"))
    if role is None:
        role = _metadata_string(payload.get("agent_role"))
    identifiers = {
        value
        for value in (
            payload.get("id"),
            payload.get("session_id"),
            payload.get("thread_id"),
            payload.get("parent_thread_id"),
        )
        if isinstance(value, str) and value
    }
    if isinstance(spawn, dict):
        identifiers.update(
            value
            for value in (
                spawn.get("id"),
                spawn.get("session_id"),
                spawn.get("thread_id"),
                spawn.get("parent_thread_id"),
            )
            if isinstance(value, str) and value
        )
    # A subagent session without either the nested source or the legacy marker
    # is schema-changed.  Root sessions legitimately have no source subobject.
    is_subagent = payload.get("thread_source") == "subagent" or isinstance(spawn, dict)
    if is_subagent and role is None:
        return {}, "worker session_meta is missing agent_role"
    return {
        "agent_role": role,
        "parent_thread_id": _metadata_string(
            spawn.get("parent_thread_id") if isinstance(spawn, dict) else None
        )
        or _metadata_string(payload.get("parent_thread_id")),
        "identifiers": sorted(identifiers),
        "is_subagent": is_subagent,
    }, None


def parse_persisted_rollout(
    path: Path, *, worker: bool = False
) -> dict[str, Any] | None:
    """Strictly parse routing metadata from a persisted rollout.

    Only ``session_meta`` and ``turn_context`` are consumed.  Any malformed
    JSON or missing required metadata is rejected, and no prompt/message text
    is considered evidence.
    """

    session: dict[str, Any] | None = None
    model: str | None = None
    effort: str | None = None
    errors: list[str] = []
    try:
        stream = path.open(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    with stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                errors.append(f"line {line_number} is not valid JSON")
                continue
            if not isinstance(event, dict):
                errors.append(f"line {line_number} is not an event object")
                continue
            event_type = event.get("type")
            if event_type == "session_meta":
                parsed, error = _session_metadata(event.get("payload"))
                if error:
                    errors.append(error)
                elif session is not None and parsed != session:
                    errors.append("conflicting session_meta metadata")
                else:
                    session = parsed
            elif event_type == "turn_context":
                parsed_model, parsed_effort, error = _turn_context_values(
                    event.get("payload")
                )
                if error:
                    errors.append(error)
                elif model is not None and (
                    model != parsed_model or effort != parsed_effort
                ):
                    errors.append("conflicting turn_context metadata")
                else:
                    model, effort = parsed_model, parsed_effort
    if errors or session is None or model is None or effort is None:
        return None
    if worker and (
        session.get("agent_role") not in EXPECTED_WORKER_ROLES
        or not session.get("is_subagent")
    ):
        return None
    return {
        "path": str(path),
        "parent_thread_id": session.get("parent_thread_id"),
        "agent_role": session.get("agent_role"),
        "model": model,
        "effort": effort,
        "identifiers": session["identifiers"],
        "is_subagent": session["is_subagent"],
    }


def parse_worker_rollout(path: Path) -> dict[str, Any] | None:
    return parse_persisted_rollout(path, worker=True)


def parse_root_rollout(path: Path) -> dict[str, Any] | None:
    return parse_persisted_rollout(path)


def verify_worker_rollout(path: Path, expected_role: str) -> dict[str, Any]:
    if expected_role not in EXPECTED_WORKER_ROLES:
        return check(
            "worker.rollout",
            "fail",
            "unknown worker role",
            expected_role=expected_role,
        )
    evidence = parse_worker_rollout(path)
    if evidence is None:
        return check(
            "worker.rollout",
            "fail",
            "worker rollout metadata is missing, malformed, or schema-changed",
        )
    mismatches: list[str] = []
    if evidence.get("agent_role") != expected_role:
        mismatches.append("role does not match expected worker role")
    if evidence.get("model") != EXPECTED_MODEL:
        mismatches.append("model does not match gpt-5.6-luna")
    if evidence.get("effort") != EXPECTED_EFFORT:
        mismatches.append("effort does not match xhigh")
    if mismatches:
        return check(
            "worker.rollout",
            "fail",
            "worker rollout routing does not match the contract",
            mismatches=mismatches,
        )
    return check(
        "worker.rollout",
        "ok",
        "persisted worker rollout matches the requested role and Luna/xhigh",
        role=expected_role,
    )


# Naming aliases used by integrations and the CLI-focused tests.
worker_rollout_check = verify_worker_rollout


def _all_rollouts(codex_home: Path) -> list[Path]:
    paths: list[Path] = list(codex_home.glob("*.jsonl"))
    for root in rollout_roots(codex_home):
        if root.is_dir():
            paths.extend(root.rglob("*.jsonl"))
    return sorted(path for path in paths if path.is_file())


def locate_root_rollout(
    codex_home: Path,
    *,
    identity: str | None = None,
    rollout_path: Path | None = None,
) -> tuple[Path | None, str | None]:
    """Locate exactly one root rollout using only persisted metadata."""

    if rollout_path is not None:
        candidate = rollout_path.expanduser().resolve()
        if not candidate.is_file():
            return None, "explicit root rollout is missing"
        evidence = parse_persisted_rollout(candidate)
        if evidence is None:
            return None, "explicit root rollout metadata is malformed or schema-changed"
        if identity and identity not in set(evidence.get("identifiers", [])):
            return None, "explicit root rollout does not match the requested identity"
        if evidence.get("is_subagent"):
            return None, "explicit rollout is a worker, not the current root"
        return candidate, None
    if not identity:
        return None, "current root thread/session identity was not supplied"
    matches: list[Path] = []
    for path in _all_rollouts(codex_home):
        evidence = parse_persisted_rollout(path)
        if evidence is None or evidence.get("is_subagent"):
            continue
        identifiers = set(evidence.get("identifiers", []))
        if identity in identifiers or identity in path.name:
            matches.append(path)
    if not matches:
        return None, "current root rollout was not found"
    if len(matches) != 1:
        return None, "current root identity matches multiple persisted rollouts"
    return matches[0], None


def root_rollout_check(
    *,
    codex_home: Path,
    thread_id: str | None = None,
    session_id: str | None = None,
    rollout_path: Path | None = None,
) -> dict[str, Any]:
    identity = thread_id or session_id
    path, error = locate_root_rollout(
        codex_home,
        identity=identity,
        rollout_path=rollout_path,
    )
    if path is None:
        return check(
            "root.rollout",
            "fail",
            error or "current root rollout could not be located",
        )
    evidence = parse_persisted_rollout(path)
    if evidence is None:
        return check(
            "root.rollout",
            "fail",
            "current root rollout metadata is malformed or schema-changed",
        )
    mismatches: list[str] = []
    if evidence.get("model") != EXPECTED_ROOT_MODEL:
        mismatches.append("model does not match gpt-5.6-sol")
    if evidence.get("effort") != EXPECTED_ROOT_EFFORT:
        mismatches.append("effort does not match medium")
    if mismatches:
        return check(
            "root.rollout",
            "fail",
            "current root rollout does not match Sol/medium",
            mismatches=mismatches,
        )
    return check(
        "root.rollout",
        "ok",
        "current root rollout proves gpt-5.6-sol/medium",
    )


verify_root_rollout = root_rollout_check


def parse_child_rollout(path: Path) -> dict[str, Any] | None:
    """Extract only persisted metadata, never prompt or message text."""

    spawn: dict[str, Any] | None = None
    model: str | None = None
    effort: str | None = None
    try:
        stream = path.open(encoding="utf-8")
    except OSError:
        return None
    with stream:
        for line in stream:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get("type") == "session_meta":
                payload = event.get("payload")
                if not isinstance(payload, dict):
                    continue
                source = payload.get("source")
                if isinstance(source, dict):
                    subagent = source.get("subagent")
                    if isinstance(subagent, dict):
                        candidate = subagent.get("thread_spawn")
                        if isinstance(candidate, dict) and spawn is None:
                            spawn = candidate
                # Older persisted formats duplicated these fields on payload.
                if spawn is None and payload.get("thread_source") == "subagent":
                    spawn = {
                        "parent_thread_id": payload.get("parent_thread_id"),
                        "agent_role": payload.get("agent_role"),
                    }
            elif event.get("type") == "turn_context" and model is None:
                payload = event.get("payload")
                if not isinstance(payload, dict):
                    continue
                settings = payload.get("collaboration_mode")
                settings = (
                    settings.get("settings") if isinstance(settings, dict) else {}
                )
                model = first_string(
                    payload.get("model"),
                    settings.get("model") if isinstance(settings, dict) else None,
                )
                effort = first_string(
                    payload.get("effort"),
                    payload.get("reasoning_effort"),
                    (
                        settings.get("reasoning_effort")
                        if isinstance(settings, dict)
                        else None
                    ),
                )
    if spawn is None:
        return None
    return {
        "path": str(path),
        "parent_thread_id": spawn.get("parent_thread_id"),
        "agent_role": first_string(spawn.get("agent_role")),
        "model": model,
        "effort": effort,
    }


def parent_thread_id(output: str) -> str | None:
    for document in json_documents(output):
        if not isinstance(document, dict):
            continue
        if document.get("type") in {"thread.started", "session.started"}:
            for key in ("thread_id", "session_id", "threadId", "sessionId"):
                value = document.get(key)
                if isinstance(value, str) and value:
                    return value
        payload = document.get("payload")
        if isinstance(payload, dict) and document.get("type") == "session_meta":
            value = payload.get("id") or payload.get("session_id")
            if isinstance(value, str) and value:
                return value
    return None


def unavailable_status(output: str) -> str | None:
    lowered = output.lower()
    if any(marker in lowered for marker in AUTH_FAILURE_MARKERS):
        return "authentication is unavailable; live probe was skipped"
    if any(marker in lowered for marker in SUPPORT_FAILURE_MARKERS):
        return "Codex does not support the requested live probe on this version"
    return None


LIVE_PROMPT = """Run a routing self-check and then stop.

Use native collaboration to spawn exactly one child with all three routing
fields explicitly set at spawn time: `agent_type="implementation_worker"`,
`model="gpt-5.6-luna"`, and `reasoning_effort="xhigh"`. Do not rely on
custom-agent TOMLs or global defaults, do not use the CLI fallback, and do not
spawn any other child. If the spawn API cannot set all three fields, report
ROUTING_UNSUPPORTED without spawning a generic child. Give the child a minimal
read-only task: inspect the current working directory, make no edits, call no
external services, create no children, and report only that it completed. Wait
for that child to finish, then reply with CHECK_DONE.
"""


def live_check(
    *,
    codex: str,
    codex_home: Path,
    cwd: Path,
    timeout: float,
    codex_version: str | None = None,
    agents_dir: Path | None = None,
    attestation_path: Path | None = None,
) -> dict[str, Any]:
    if not cwd.is_dir():
        return check("live.probe", "fail", f"live probe cwd does not exist: {cwd}")

    before = rollout_snapshot(codex_home)
    command = [
        codex,
        "exec",
        "--json",
        "--model",
        "gpt-5.6-sol",
        "--sandbox",
        "read-only",
        "--cd",
        str(cwd),
    ]
    for override in CONFIG_OVERRIDES:
        command.extend(["--config", override])
    for override in ROOT_CONFIG_OVERRIDES:
        command.extend(["--config", override])
    started = time.monotonic()
    process = run_command(
        command,
        timeout=timeout,
        cwd=cwd,
        input_text=LIVE_PROMPT,
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if process is None:
        return check(
            "live.probe",
            "fail",
            "native live probe could not run",
            evidence="no persisted child rollout was inspected",
            elapsed_ms=elapsed_ms,
        )

    # On a successful run, stdout may contain a model response that merely
    # mentions auth or support. Only classify an unavailable runtime from
    # diagnostics when the command itself failed.
    diagnostic_output = process.stderr
    if process.returncode:
        diagnostic_output = f"{process.stdout}\n{diagnostic_output}"
    unavailable = unavailable_status(diagnostic_output) if process.returncode else None
    paths = changed_rollouts(codex_home, before)
    parent_id = parent_thread_id(process.stdout)

    if unavailable:
        return check(
            "live.probe",
            "skipped",
            unavailable,
            returncode=process.returncode,
            evidence="auth/support unavailable; no routing claim made",
        )
    if process.returncode != 0:
        return check(
            "live.probe",
            "fail",
            "native live probe failed before verifiable child evidence",
            returncode=process.returncode,
            evidence_count=len(paths),
        )

    # A successful live run must prove both the root invocation and its child.
    # Prefer files changed by this invocation, but search all persisted files
    # for the exact parent ID when the root rollout is flushed asynchronously.
    child_evidence: list[dict[str, Any]] = []
    root_evidence: list[dict[str, Any]] = []
    candidate_paths = paths
    if parent_id is not None:
        candidate_paths = sorted(set(paths) | set(_all_rollouts(codex_home)))
    for path in candidate_paths:
        candidate = parse_persisted_rollout(path, worker=True)
        if candidate is not None:
            if parent_id is None or candidate.get("parent_thread_id") == parent_id:
                child_evidence.append(candidate)
            continue
        root = parse_persisted_rollout(path)
        if root is not None and not root.get("is_subagent"):
            if parent_id is None or parent_id in set(root.get("identifiers", [])):
                root_evidence.append(root)

    # Keep compatibility with older persisted fixtures where a worker's
    # parent_thread_id is omitted, but still require exactly one changed child.
    if parent_id is None:
        child_evidence = [
            candidate
            for path in paths
            if (candidate := parse_persisted_rollout(path, worker=True)) is not None
        ]
        root_evidence = [
            candidate
            for path in paths
            if (candidate := parse_persisted_rollout(path)) is not None
            and not candidate.get("is_subagent")
        ]

    if len(child_evidence) != 1 or len(root_evidence) != 1:
        return check(
            "live.probe",
            "fail",
            "native live probe did not produce exactly one root and child rollout",
            child_evidence_count=len(child_evidence),
            root_evidence_count=len(root_evidence),
            parent_thread_id=parent_id,
            rollout_files=[str(path) for path in paths],
        )

    child = child_evidence[0]
    root = root_evidence[0]
    mismatches = []
    if root.get("model") != EXPECTED_ROOT_MODEL:
        mismatches.append(
            f"root model={root.get('model')!r}, expected {EXPECTED_ROOT_MODEL!r}"
        )
    if root.get("effort") != EXPECTED_ROOT_EFFORT:
        mismatches.append(
            f"root effort={root.get('effort')!r}, expected {EXPECTED_ROOT_EFFORT!r}"
        )
    if child.get("agent_role") != EXPECTED_IMPLEMENTATION_ROLE:
        mismatches.append(
            f"role={child.get('agent_role')!r}, expected {EXPECTED_IMPLEMENTATION_ROLE!r}"
        )
    if child.get("model") != EXPECTED_MODEL:
        mismatches.append(f"model={child.get('model')!r}, expected {EXPECTED_MODEL!r}")
    if child.get("effort") != EXPECTED_EFFORT:
        mismatches.append(
            f"effort={child.get('effort')!r}, expected {EXPECTED_EFFORT!r}"
        )
    if mismatches:
        return check(
            "live.probe",
            "fail",
            "persisted child routing evidence does not match Luna/xhigh",
            mismatches=mismatches,
            root_evidence=root,
            child_evidence=child,
        )
    if codex_version is None:
        version_result, detected_version = version_check(codex, timeout=timeout)
        if version_result["status"] == "ok" and detected_version is not None:
            codex_version = detected_version
        else:
            # ``main`` always supplies the version from offline checks.  Keep
            # the helper usable with isolated fixtures, while making the
            # resulting attestation fail closed in a real enforce pass when
            # the current CLI version is known.
            codex_version = "unknown"
    fingerprint = compatibility_fingerprint(
        codex_version=codex_version,
        codex_home=codex_home,
        agents_dir=agents_dir,
    )
    destination = attestation_path or default_attestation_path(codex_home)
    proof = {
        "root": {"model": EXPECTED_ROOT_MODEL, "effort": EXPECTED_ROOT_EFFORT},
        "worker": {
            "role": EXPECTED_IMPLEMENTATION_ROLE,
            "model": EXPECTED_MODEL,
            "effort": EXPECTED_EFFORT,
        },
    }
    try:
        write_attestation(destination, fingerprint, proof=proof)
    except (OSError, TypeError, ValueError):
        return check(
            "live.probe",
            "fail",
            "routing proof succeeded but compatibility attestation could not be written",
        )
    return check(
        "live.probe",
        "ok",
        "persisted root and child rollouts prove the routing contract",
        root_evidence={
            "model": root.get("model"),
            "effort": root.get("effort"),
        },
        child_evidence={
            "agent_role": child.get("agent_role"),
            "model": child.get("model"),
            "effort": child.get("effort"),
        },
        elapsed_ms=elapsed_ms,
    )


def enforce_check(
    *,
    codex: str | None,
    codex_home: Path,
    agents_dir: Path,
    timeout: float,
    thread_id: str | None = None,
    session_id: str | None = None,
    rollout_path: Path | None = None,
    root_thread_id: str | None = None,
    root_session_id: str | None = None,
    root_rollout_path: Path | None = None,
    attestation_path: Path | None = None,
    offline_results: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Run fail-closed compatibility and current-root enforcement checks."""

    results = (
        offline_results
        if offline_results is not None
        else offline_checks(
            codex=codex,
            agents_dir=agents_dir,
            timeout=timeout,
        )
    )
    version = next(
        (
            result.get("details", {}).get("version")
            for result in results
            if result.get("name") == "codex.version"
            and isinstance(result.get("details"), dict)
        ),
        None,
    )
    fingerprint = compatibility_fingerprint(
        codex_version=version,
        codex_home=codex_home,
        agents_dir=agents_dir,
    )
    destination = attestation_path or default_attestation_path(codex_home)
    results = list(results)
    results.append(attestation_check(path=destination, fingerprint=fingerprint))
    effective_thread_id = (
        thread_id or root_thread_id or os.environ.get("CODEX_THREAD_ID")
    )
    effective_session_id = (
        session_id or root_session_id or os.environ.get("CODEX_SESSION_ID")
    )
    # A path is an explicit root rollout supplied by the caller; otherwise an
    # identity is mandatory.  This prevents an offline invocation outside a
    # Codex task from accidentally accepting an arbitrary historical rollout.
    results.append(
        root_rollout_check(
            codex_home=codex_home,
            thread_id=effective_thread_id,
            session_id=effective_session_id,
            rollout_path=rollout_path or root_rollout_path,
        )
    )
    return results


enforcement_check = enforce_check


def overall_status(results: list[dict[str, Any]]) -> str:
    if not results:
        return "fail"
    statuses = {result["status"] for result in results}
    if "fail" in statuses:
        return "fail"
    if "skipped" in statuses:
        return "skipped"
    return "ok"


def human_report(report: dict[str, Any]) -> str:
    mode = report["mode"]
    label = {"ok": "PASS", "fail": "FAIL", "skipped": "SKIPPED"}[report["status"]]
    lines = [f"Codex Maestro routing check: {label} ({mode})"]
    for result in report["checks"]:
        lines.append(f"  {result['name']}: {result['status']} - {result['message']}")
        details = result.get("details")
        if result["status"] != "ok" and isinstance(details, dict):
            failures = details.get("failures") or details.get("mismatches")
            if isinstance(failures, list):
                lines.extend(f"    {failure}" for failure in failures)
    if mode == "live":
        lines.append("  Live mode is opt-in and consumes model tokens.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    codex_home = args.codex_home.expanduser().resolve()
    agents_dir = (args.agents_dir or codex_home / "agents").expanduser().resolve()
    destination = (
        args.attestation_path.expanduser().resolve()
        if args.attestation_path
        else (
            Path(
                os.environ.get(
                    "CODEX_MAESTRO_ATTESTATION_PATH",
                    os.environ.get("CODEX_MAESTRO_ATTESTATION", ""),
                )
            )
            .expanduser()
            .resolve()
            if os.environ.get("CODEX_MAESTRO_ATTESTATION_PATH")
            or os.environ.get("CODEX_MAESTRO_ATTESTATION")
            else default_attestation_path(codex_home)
        )
    )
    if args.worker_rollout is not None:
        if not args.expected_role:
            results = [
                check(
                    "worker.rollout",
                    "fail",
                    "--worker-rollout requires --role",
                )
            ]
        else:
            results = [
                verify_worker_rollout(
                    args.worker_rollout.expanduser().resolve(), args.expected_role
                )
            ]
        mode = "worker-rollout"
    else:
        codex = resolve_codex(args.codex_path)
        results = offline_checks(
            codex=codex,
            agents_dir=agents_dir,
            timeout=args.timeout,
        )
        mode = "enforce" if args.enforce else ("live" if args.live else "offline")
    if args.enforce:
        results = enforce_check(
            codex=codex,
            codex_home=codex_home,
            agents_dir=agents_dir,
            timeout=args.timeout,
            thread_id=args.root_thread_id,
            session_id=args.root_session_id,
            rollout_path=args.root_rollout,
            attestation_path=destination,
            offline_results=results,
        )
    elif args.live:
        if codex is None:
            results.append(
                check(
                    "live.probe",
                    "skipped",
                    "codex CLI is unavailable; live probe was skipped",
                )
            )
        elif overall_status(results) == "fail":
            results.append(
                check(
                    "live.probe",
                    "fail",
                    "offline checks failed; live probe was not started",
                )
            )
        else:
            version = next(
                (
                    result.get("details", {}).get("version")
                    for result in results
                    if result.get("name") == "codex.version"
                    and isinstance(result.get("details"), dict)
                ),
                None,
            )
            results.append(
                live_check(
                    codex=codex,
                    codex_home=codex_home,
                    cwd=args.cwd.expanduser().resolve(),
                    timeout=args.timeout,
                    codex_version=version,
                    agents_dir=agents_dir,
                    attestation_path=destination,
                )
            )

    report = {
        "status": overall_status(results),
        "mode": mode,
        "checks": results,
    }
    if args.json_output:
        print(json.dumps(report, sort_keys=True))
    else:
        print(human_report(report))
    # 2 distinguishes an explicit live skip from a contract mismatch/failure.
    return {"ok": 0, "fail": 1, "skipped": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
