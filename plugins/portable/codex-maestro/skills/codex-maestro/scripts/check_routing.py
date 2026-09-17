#!/usr/bin/env python3
"""Verify the supported Sol/medium root and Luna/max workers."""
from __future__ import annotations

import argparse
import json
import os
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_ROOT_MODEL = "gpt-5.6-sol"
EXPECTED_ROOT_EFFORT = "medium"
EXPECTED_WORKER_MODEL = "gpt-5.6-luna"
EXPECTED_WORKER_EFFORT = "max"
EXPECTED_WORKER_ROLES = ("implementation_worker", "exploration_worker")
AGENT_REQUIREMENTS = {
    "implementation-worker.toml": {
        "name": "implementation_worker",
        "model": EXPECTED_WORKER_MODEL,
        "model_reasoning_effort": EXPECTED_WORKER_EFFORT,
        "sandbox_mode": "workspace-write",
    },
    "exploration-worker.toml": {
        "name": "exploration_worker",
        "model": EXPECTED_WORKER_MODEL,
        "model_reasoning_effort": EXPECTED_WORKER_EFFORT,
        "sandbox_mode": "read-only",
    },
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", dest="json_output", action="store_true")
    parser.add_argument("--profile", choices=("default",), default="default",
                        help="the Sol/Luna route is the only supported preset")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--enforce", action="store_true",
                      help="verify installed agents and the current root route")
    mode.add_argument("--worker-rollout", type=Path,
                      help="verify one persisted worker rollout")
    parser.add_argument("--role", choices=EXPECTED_WORKER_ROLES,
                        help="expected role for --worker-rollout")
    parser.add_argument("--codex-home", type=Path,
                        default=Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    parser.add_argument("--thread-id", "--root-thread-id", dest="root_thread_id")
    parser.add_argument("--session-id", "--root-session-id", dest="root_session_id")
    parser.add_argument("--root-rollout", type=Path)
    args = parser.parse_args(argv)
    if (args.worker_rollout is None) != (args.role is None):
        parser.error("--worker-rollout and --role must be supplied together")
    return args


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


def agent_templates_check(agents_dir: Path) -> dict[str, Any]:
    failures: list[str] = []
    for filename, expected in AGENT_REQUIREMENTS.items():
        path = agents_dir / filename
        try:
            with path.open("rb") as stream:
                actual = tomllib.load(stream)
        except FileNotFoundError:
            failures.append(f"{filename} is missing")
            continue
        except (OSError, tomllib.TOMLDecodeError):
            failures.append(f"{filename} is unreadable or invalid TOML")
            continue
        for key, value in expected.items():
            if actual.get(key) != value:
                failures.append(f"{filename} {key} does not match {value}")
    if failures:
        return check(
            "agents.configuration",
            "fail",
            "installed custom-agent definitions do not match Luna/max",
            failures=failures,
        )
    return check(
        "agents.configuration",
        "ok",
        "installed implementation and exploration agents match Luna/max",
    )


def rollout_roots(codex_home: Path) -> tuple[Path, ...]:
    return (codex_home / "sessions", codex_home / "archived_sessions")


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
        "own_id": first_string(payload.get("id"), payload.get("thread_id"), payload.get("session_id")),
        "agent_role": role,
        "parent_thread_id": _metadata_string(
            spawn.get("parent_thread_id") if isinstance(spawn, dict) else None
        )
        or _metadata_string(payload.get("parent_thread_id")),
        "identifiers": sorted(identifiers),
        "is_subagent": is_subagent,
    }, None


def parse_persisted_rollout(path: Path) -> dict[str, Any] | None:
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
    try:
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
    except (OSError, UnicodeError):
        return None
    if errors or session is None or model is None or effort is None:
        return None
    return {
        "path": str(path),
        "parent_thread_id": session.get("parent_thread_id"),
        "agent_role": session.get("agent_role"),
        "model": model,
        "effort": effort,
        "identifiers": session["identifiers"],
        "own_id": session["own_id"],
        "is_subagent": session["is_subagent"],
    }


def verify_worker_rollout(path: Path, expected_role: str) -> dict[str, Any]:
    evidence = parse_persisted_rollout(path)
    if evidence is None:
        return check(
            "worker.rollout",
            "fail",
            "worker rollout metadata is malformed or schema-changed",
        )
    failures: list[str] = []
    if not evidence.get("is_subagent"):
        failures.append("rollout is a root task, not a worker")
    if evidence.get("agent_role") != expected_role:
        failures.append(f"agent role does not match {expected_role}")
    if evidence.get("model") != EXPECTED_WORKER_MODEL:
        failures.append(f"model does not match {EXPECTED_WORKER_MODEL}")
    if evidence.get("effort") != EXPECTED_WORKER_EFFORT:
        failures.append(f"effort does not match {EXPECTED_WORKER_EFFORT}")
    if failures:
        return check(
            "worker.rollout",
            "fail",
            f"worker rollout does not match {expected_role} on Luna/max",
            failures=failures,
        )
    return check(
        "worker.rollout",
        "ok",
        f"worker rollout proves {expected_role} on Luna/max",
    )


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
        if identity in identifiers:
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
    expected_model: str = DEFAULT_ROOT_MODEL,
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
    if evidence.get("model") != expected_model:
        mismatches.append(f"model does not match {expected_model}")
    if evidence.get("effort") != EXPECTED_ROOT_EFFORT:
        mismatches.append("effort does not match medium")
    if mismatches:
        return check(
            "root.rollout",
            "fail",
            f"current root rollout does not match {expected_model}/medium",
            mismatches=mismatches,
        )
    return check(
        "root.rollout",
        "ok",
        f"current root rollout proves {expected_model}/medium",
    )


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
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    codex_home = args.codex_home.expanduser().resolve()
    if args.worker_rollout is not None:
        assert args.role is not None
        results = [verify_worker_rollout(
            args.worker_rollout.expanduser().resolve(), args.role
        )]
        mode = "worker"
    elif args.enforce:
        results = [
            agent_templates_check(codex_home / "agents"),
            root_rollout_check(
                codex_home=codex_home,
                thread_id=args.root_thread_id or os.environ.get("CODEX_THREAD_ID"),
                session_id=args.root_session_id or os.environ.get("CODEX_SESSION_ID"),
                rollout_path=args.root_rollout,
            ),
        ]
        mode = "enforce"
    else:
        results = [agent_templates_check(codex_home / "agents")]
        mode = "offline"
    report = {"status": overall_status(results),
              "mode": mode,
              "profile": "default", "checks": results}
    print(json.dumps(report, sort_keys=True) if args.json_output else human_report(report))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
