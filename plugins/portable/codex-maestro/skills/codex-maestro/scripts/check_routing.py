#!/usr/bin/env python3
"""Check whether Codex Maestro's declared and effective routing is working.

The default check is local and does not run a model.  ``--live`` is an
explicit opt-in probe: it runs one minimal native child workflow and inspects
the persisted child rollout for effective role, model, and effort evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any, Iterable

EXPECTED_MODEL = "gpt-5.6-luna"
EXPECTED_EFFORT = "xhigh"
EXPECTED_IMPLEMENTATION_ROLE = "implementation_worker"
EXPECTED_EXPLORATION_ROLE = "exploration_worker"
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="emit machine-readable JSON instead of concise human output",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="opt in to one native child workflow (consumes model tokens)",
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
    unavailable = unavailable_status(diagnostic_output)
    paths = changed_rollouts(codex_home, before)
    parent_id = parent_thread_id(process.stdout)
    evidence = []
    for path in paths:
        candidate = parse_child_rollout(path)
        if candidate is None:
            continue
        if parent_id is None or candidate.get("parent_thread_id") in {None, parent_id}:
            evidence.append(candidate)

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
            evidence_count=len(evidence),
        )
    if len(evidence) != 1:
        return check(
            "live.probe",
            "fail",
            "native live probe did not produce exactly one child rollout",
            evidence_count=len(evidence),
            parent_thread_id=parent_id,
            rollout_files=[str(path) for path in paths],
        )

    child = evidence[0]
    mismatches = []
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
            child_evidence=child,
        )
    return check(
        "live.probe",
        "ok",
        "persisted child rollout proves implementation_worker on Luna/xhigh",
        child_evidence=child,
        elapsed_ms=elapsed_ms,
    )


def overall_status(results: list[dict[str, Any]]) -> str:
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
    codex = resolve_codex(args.codex_path)
    results = offline_checks(
        codex=codex,
        agents_dir=agents_dir,
        timeout=args.timeout,
    )
    if args.live:
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
                    "skipped",
                    "offline checks failed; live probe was not started",
                )
            )
        else:
            results.append(
                live_check(
                    codex=codex,
                    codex_home=codex_home,
                    cwd=args.cwd.expanduser().resolve(),
                    timeout=args.timeout,
                )
            )

    report = {
        "status": overall_status(results),
        "mode": "live" if args.live else "offline",
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
