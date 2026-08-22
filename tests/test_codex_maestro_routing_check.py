from __future__ import annotations

import contextlib
import io
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "portable"
    / "codex-maestro"
    / "skills"
    / "codex-maestro"
    / "scripts"
    / "check_routing.py"
)
SPEC = importlib.util.spec_from_file_location("codex_maestro_check_routing", SCRIPT)
assert SPEC and SPEC.loader
routing = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(routing)


class CodexMaestroRoutingCheckTests(unittest.TestCase):
    def make_agents(self, root: Path) -> Path:
        agents = root / "agents"
        agents.mkdir()
        references = SCRIPT.parent.parent / "references"
        for filename in routing.AGENT_FILES.values():
            shutil.copy2(references / str(filename["filename"]), agents)
        return agents

    @staticmethod
    def doctor_output(status: str = "ok") -> str:
        return json.dumps({"checks": {"config.load": {"status": status}}})

    @staticmethod
    def write_rollout(
        path: Path,
        *,
        model: str,
        effort: str,
        role: str | None = None,
        identifier: str = "rollout-1",
        parent: str | None = None,
    ) -> None:
        session: dict[str, object] = {
            "session_id": identifier,
            "id": identifier,
        }
        if role is not None:
            session["source"] = {
                "subagent": {
                    "thread_spawn": {
                        "parent_thread_id": parent,
                        "agent_role": role,
                    }
                }
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                [
                    json.dumps({"type": "session_meta", "payload": session}),
                    json.dumps(
                        {
                            "type": "turn_context",
                            "payload": {"model": model, "effort": effort},
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    def test_offline_success_checks_cli_doctor_agents_and_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agents = self.make_agents(Path(directory))
            processes = [
                subprocess.CompletedProcess(
                    ["codex", "--version"], 0, "codex-cli 0.149.0\n", ""
                ),
                subprocess.CompletedProcess(
                    ["codex", "doctor"], 1, self.doctor_output(), ""
                ),
                subprocess.CompletedProcess(
                    ["codex", "doctor"], 1, self.doctor_output(), ""
                ),
            ]
            with patch.object(routing.shutil, "which", return_value="/usr/bin/codex"):
                with patch.object(
                    routing.subprocess, "run", side_effect=processes
                ) as run:
                    results = routing.offline_checks(
                        codex="/usr/bin/codex",
                        agents_dir=agents,
                        timeout=1,
                    )

            self.assertEqual([result["status"] for result in results], ["ok"] * 4)
            override_command = run.call_args_list[-1].args[0]
            self.assertIn(
                'agents.default_subagent_model="gpt-5.6-luna"', override_command
            )
            self.assertIn(
                'agents.default_subagent_reasoning_effort="xhigh"',
                override_command,
            )

    def test_offline_failure_reports_unparseable_version_and_doctor_config(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agents = self.make_agents(Path(directory))
            processes = [
                subprocess.CompletedProcess(["codex", "--version"], 0, "codex dev", ""),
                subprocess.CompletedProcess(
                    ["codex", "doctor"], 1, self.doctor_output("fail"), ""
                ),
                subprocess.CompletedProcess(
                    ["codex", "doctor"], 1, self.doctor_output("fail"), ""
                ),
            ]
            with patch.object(routing.subprocess, "run", side_effect=processes):
                results = routing.offline_checks(
                    codex="codex", agents_dir=agents, timeout=1
                )

            self.assertEqual(results[0]["status"], "fail")
            self.assertEqual(results[2]["status"], "fail")
            self.assertEqual(results[3]["status"], "fail")

    def test_agent_check_rejects_wrong_exploration_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agents = self.make_agents(Path(directory))
            exploration = agents / "exploration-worker.toml"
            exploration.write_text(
                exploration.read_text(encoding="utf-8").replace(
                    'sandbox_mode = "read-only"', 'sandbox_mode = "workspace-write"'
                ),
                encoding="utf-8",
            )

            result = routing.agent_templates_check(agents)

            self.assertEqual(result["status"], "fail")
            self.assertTrue(
                any("sandbox_mode" in item for item in result["details"]["failures"])
            )

    def test_attestation_fresh_stale_missing_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fingerprint = routing.compatibility_fingerprint(
                codex_version="0.149.0", codex_home=root
            )
            destination = root / "maestro" / "routing-attestation.json"
            missing = routing.attestation_check(
                path=destination, fingerprint=fingerprint, now=100
            )
            self.assertEqual(missing["status"], "fail")
            routing.write_attestation(destination, fingerprint, timestamp=100)
            self.assertEqual(
                routing.attestation_check(
                    path=destination, fingerprint=fingerprint, now=100
                )["status"],
                "ok",
            )
            stale = routing.attestation_check(
                path=destination,
                fingerprint=fingerprint,
                now=100 + routing.ATTESTATION_MAX_AGE_SECONDS + 1,
                max_age=routing.ATTESTATION_MAX_AGE_SECONDS,
            )
            self.assertEqual(stale["status"], "fail")
            self.assertEqual(
                routing.attestation_check(
                    path=destination,
                    fingerprint=fingerprint,
                    now=100 + routing.ATTESTATION_MAX_AGE_SECONDS + 1,
                )["status"],
                "ok",
            )
            future = root / "future.json"
            routing.write_attestation(
                future,
                fingerprint,
                timestamp=100 + routing.FUTURE_TIMESTAMP_TOLERANCE_SECONDS + 1,
            )
            self.assertEqual(
                routing.attestation_check(
                    path=future, fingerprint=fingerprint, now=100
                )["status"],
                "fail",
            )
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_fingerprint_invalidates_codex_config_agent_checker_and_skill(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            agents = root / "agents"
            agents.mkdir()
            implementation = agents / "implementation-worker.toml"
            exploration = agents / "exploration-worker.toml"
            implementation.write_text("implementation", encoding="utf-8")
            exploration.write_text("exploration", encoding="utf-8")
            config = root / "config.toml"
            config.write_text("model = 'one'", encoding="utf-8")
            package = root / "plugin.json"
            package.write_text(
                json.dumps({"name": "codex-maestro", "version": "0.5.6"}),
                encoding="utf-8",
            )
            checker = root / "checker.py"
            skill = root / "SKILL.md"
            checker.write_text("checker", encoding="utf-8")
            skill.write_text("skill", encoding="utf-8")
            first = routing.compatibility_fingerprint(
                codex_version="0.149.0",
                codex_home=root,
                agents_dir=agents,
                checker_path=checker,
                skill_path=skill,
            )
            checker.write_text("checker changed", encoding="utf-8")
            second = routing.compatibility_fingerprint(
                codex_version="0.149.0",
                codex_home=root,
                agents_dir=agents,
                checker_path=checker,
                skill_path=skill,
            )
            self.assertNotEqual(first["hashes"]["checker"], second["hashes"]["checker"])
            self.assertEqual(first["package_version"], "0.5.6")
            config.write_text("model = 'two'", encoding="utf-8")
            implementation.write_text("implementation changed", encoding="utf-8")
            skill.write_text("skill changed", encoding="utf-8")
            package.write_text(
                json.dumps({"name": "codex-maestro", "version": "0.5.7"}),
                encoding="utf-8",
            )
            third = routing.compatibility_fingerprint(
                codex_version="0.150.0",
                codex_home=root,
                agents_dir=agents,
                checker_path=checker,
                skill_path=skill,
            )
            self.assertNotEqual(first["hashes"]["config"], third["hashes"]["config"])
            self.assertNotEqual(
                first["hashes"]["agents"][routing.EXPECTED_IMPLEMENTATION_ROLE],
                third["hashes"]["agents"][routing.EXPECTED_IMPLEMENTATION_ROLE],
            )
            self.assertNotEqual(first["hashes"]["skill"], third["hashes"]["skill"])
            self.assertNotEqual(first["codex_version"], third["codex_version"])
            self.assertNotEqual(first["package_version"], third["package_version"])
            self.assertNotIn(str(root), json.dumps(first, sort_keys=True))

    def test_root_rollout_requires_identity_and_exact_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "sessions" / "root.jsonl"
            self.write_rollout(
                rollout,
                model=routing.EXPECTED_ROOT_MODEL,
                effort=routing.EXPECTED_ROOT_EFFORT,
                identifier="root-1",
            )
            self.assertEqual(
                routing.root_rollout_check(codex_home=root)["status"], "fail"
            )
            self.assertEqual(
                routing.root_rollout_check(codex_home=root, thread_id="root-1")[
                    "status"
                ],
                "ok",
            )
            self.write_rollout(
                rollout,
                model=routing.EXPECTED_MODEL,
                effort=routing.EXPECTED_EFFORT,
                identifier="root-1",
            )
            self.assertEqual(
                routing.root_rollout_check(codex_home=root, thread_id="root-1")[
                    "status"
                ],
                "fail",
            )
            rollout.write_text('{"type": "turn_context"}\n', encoding="utf-8")
            self.assertEqual(
                routing.root_rollout_check(codex_home=root, thread_id="root-1")[
                    "status"
                ],
                "fail",
            )

    def test_worker_rollout_supports_both_roles_and_rejects_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for role in routing.EXPECTED_WORKER_ROLES:
                rollout = root / f"{role}.jsonl"
                self.write_rollout(
                    rollout,
                    model=routing.EXPECTED_MODEL,
                    effort=routing.EXPECTED_EFFORT,
                    role=role,
                    parent="root-1",
                )
                self.assertEqual(
                    routing.verify_worker_rollout(rollout, role)["status"], "ok"
                )
            wrong = root / "wrong.jsonl"
            self.write_rollout(
                wrong,
                model=routing.EXPECTED_ROOT_MODEL,
                effort=routing.EXPECTED_ROOT_EFFORT,
                role=routing.EXPECTED_EXPLORATION_ROLE,
            )
            self.assertEqual(
                routing.verify_worker_rollout(
                    wrong, routing.EXPECTED_IMPLEMENTATION_ROLE
                )["status"],
                "fail",
            )
            self.assertEqual(
                routing.verify_worker_rollout(wrong, "unknown_worker")["status"],
                "fail",
            )
            wrong.write_text("not json\n", encoding="utf-8")
            self.assertEqual(
                routing.verify_worker_rollout(wrong, routing.EXPECTED_EXPLORATION_ROLE)[
                    "status"
                ],
                "fail",
            )

    def test_worker_cli_json_exit_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rollout = Path(directory) / "worker.jsonl"
            self.write_rollout(
                rollout,
                model=routing.EXPECTED_MODEL,
                effort=routing.EXPECTED_EFFORT,
                role=routing.EXPECTED_IMPLEMENTATION_ROLE,
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                passed = routing.main(
                    [
                        "--worker-rollout",
                        str(rollout),
                        "--role",
                        routing.EXPECTED_IMPLEMENTATION_ROLE,
                        "--json",
                    ]
                )
            self.assertEqual(passed, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "ok")
            self.write_rollout(
                rollout,
                model=routing.EXPECTED_ROOT_MODEL,
                effort=routing.EXPECTED_ROOT_EFFORT,
                role=routing.EXPECTED_IMPLEMENTATION_ROLE,
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                failed = routing.main(
                    [
                        "--worker-rollout",
                        str(rollout),
                        "--role",
                        routing.EXPECTED_IMPLEMENTATION_ROLE,
                        "--json",
                    ]
                )
            self.assertEqual(failed, 1)
            self.assertEqual(json.loads(output.getvalue())["status"], "fail")

    def test_enforce_requires_fresh_attestation_and_current_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "sessions" / "root.jsonl"
            self.write_rollout(
                rollout,
                model=routing.EXPECTED_ROOT_MODEL,
                effort=routing.EXPECTED_ROOT_EFFORT,
                identifier="root-1",
            )
            offline = [
                {
                    "name": "codex.version",
                    "status": "ok",
                    "message": "ok",
                    "details": {"version": "0.149.0"},
                }
            ]
            fingerprint = routing.compatibility_fingerprint(
                codex_version="0.149.0", codex_home=root
            )
            destination = root / "attestation.json"
            routing.write_attestation(destination, fingerprint, timestamp=100)
            with patch.object(routing.time, "time", return_value=100):
                results = routing.enforce_check(
                    codex="codex",
                    codex_home=root,
                    agents_dir=root / "agents",
                    timeout=1,
                    thread_id="root-1",
                    attestation_path=destination,
                    offline_results=offline,
                )
            self.assertEqual(results[-2]["status"], "ok")
            self.assertEqual(results[-1]["status"], "ok")
            outside = routing.enforce_check(
                codex="codex",
                codex_home=root,
                agents_dir=root / "agents",
                timeout=1,
                attestation_path=destination,
                offline_results=offline,
            )
            self.assertEqual(outside[-1]["status"], "fail")

    def test_parse_child_rollout_uses_persisted_role_model_and_effort(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            rollout = Path(directory) / "child.jsonl"
            rollout.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "source": {
                                        "subagent": {
                                            "thread_spawn": {
                                                "parent_thread_id": "parent-1",
                                                "agent_role": "implementation_worker",
                                            }
                                        }
                                    }
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "turn_context",
                                "payload": {
                                    "model": "gpt-5.6-luna",
                                    "effort": "xhigh",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            evidence = routing.parse_child_rollout(rollout)

            self.assertIsNotNone(evidence)
            assert evidence is not None
            self.assertEqual(evidence["agent_role"], "implementation_worker")
            self.assertEqual(evidence["model"], "gpt-5.6-luna")
            self.assertEqual(evidence["effort"], "xhigh")

    def test_live_prompt_requires_explicit_spawn_routing(self) -> None:
        prompt = routing.LIVE_PROMPT

        self.assertIn('agent_type="implementation_worker"', prompt)
        self.assertIn('model="gpt-5.6-luna"', prompt)
        self.assertIn('reasoning_effort="xhigh"', prompt)
        self.assertIn("If the spawn API cannot set all three fields", prompt)
        self.assertIn("do not use the CLI fallback", prompt)

    def test_live_probe_rejects_mismatched_persisted_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "child.jsonl"
            root_rollout = root / "root.jsonl"
            root_rollout.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {"session_id": "parent-1", "id": "parent-1"},
                            }
                        ),
                        json.dumps(
                            {
                                "type": "turn_context",
                                "payload": {
                                    "model": "gpt-5.6-sol",
                                    "effort": "medium",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rollout.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "source": {
                                        "subagent": {
                                            "thread_spawn": {
                                                "parent_thread_id": "parent-1",
                                                "agent_role": "implementation_worker",
                                            }
                                        }
                                    }
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "turn_context",
                                "payload": {
                                    "model": "gpt-5.6-sol",
                                    "effort": "medium",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            process = subprocess.CompletedProcess(
                ["codex", "exec"],
                0,
                '{"type":"thread.started","thread_id":"parent-1"}\n',
                "",
            )
            attestation = root / "maestro" / "routing-attestation.json"
            routing.write_attestation(
                attestation,
                routing.compatibility_fingerprint("0.149.0", root),
                timestamp=100,
            )
            before_attestation = attestation.read_bytes()
            with patch.object(
                routing,
                "rollout_snapshot",
                side_effect=[{}, {root_rollout: (1, 1), rollout: (1, 1)}],
            ):
                with patch.object(routing, "run_command", return_value=process):
                    result = routing.live_check(
                        codex="codex",
                        codex_home=root,
                        cwd=root,
                        timeout=1,
                        codex_version="0.149.0",
                    )

            self.assertEqual(result["status"], "fail")
            self.assertIn("model", result["details"]["mismatches"][0])
            self.assertIn("effort", result["details"]["mismatches"][1])
            self.assertEqual(attestation.read_bytes(), before_attestation)

    def test_live_probe_accepts_matching_persisted_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "child.jsonl"
            root_rollout = root / "root.jsonl"
            root_rollout.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {"session_id": "parent-1", "id": "parent-1"},
                            }
                        ),
                        json.dumps(
                            {
                                "type": "turn_context",
                                "payload": {
                                    "model": "gpt-5.6-sol",
                                    "effort": "medium",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            rollout.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "session_meta",
                                "payload": {
                                    "source": {
                                        "subagent": {
                                            "thread_spawn": {
                                                "parent_thread_id": "parent-1",
                                                "agent_role": "implementation_worker",
                                            }
                                        }
                                    }
                                },
                            }
                        ),
                        json.dumps(
                            {
                                "type": "turn_context",
                                "payload": {
                                    "model": "gpt-5.6-luna",
                                    "effort": "xhigh",
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            process = subprocess.CompletedProcess(
                ["codex", "exec"],
                0,
                '{"type":"thread.started","thread_id":"parent-1"}\n',
                "",
            )
            with patch.object(
                routing,
                "rollout_snapshot",
                side_effect=[{}, {root_rollout: (1, 1), rollout: (1, 1)}],
            ):
                with patch.object(routing, "run_command", return_value=process):
                    result = routing.live_check(
                        codex="codex",
                        codex_home=root,
                        cwd=root,
                        timeout=1,
                        codex_version="0.149.0",
                    )

            self.assertEqual(result["status"], "ok")
            attestation = root / "maestro" / "routing-attestation.json"
            self.assertTrue(attestation.is_file())
            self.assertEqual(attestation.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                result["details"]["child_evidence"]["agent_role"],
                "implementation_worker",
            )
            self.assertEqual(
                result["details"]["child_evidence"]["model"], "gpt-5.6-luna"
            )
            self.assertEqual(result["details"]["child_evidence"]["effort"], "xhigh")

    def test_live_probe_marks_auth_absence_as_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = subprocess.CompletedProcess(
                ["codex", "exec"], 1, "", "Authentication required; run codex login."
            )
            attestation = root / "maestro" / "routing-attestation.json"
            routing.write_attestation(
                attestation,
                routing.compatibility_fingerprint("0.149.0", root),
                timestamp=100,
            )
            before_attestation = attestation.read_bytes()
            with patch.object(routing, "rollout_snapshot", return_value={}):
                with patch.object(routing, "run_command", return_value=process):
                    result = routing.live_check(
                        codex="codex",
                        codex_home=root,
                        cwd=root,
                        timeout=1,
                    )

            self.assertEqual(result["status"], "skipped")
            self.assertIn("authentication", result["message"])
            self.assertEqual(attestation.read_bytes(), before_attestation)


if __name__ == "__main__":
    unittest.main()
