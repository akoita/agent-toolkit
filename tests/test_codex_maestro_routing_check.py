from __future__ import annotations

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
            with patch.object(
                routing, "rollout_snapshot", side_effect=[{}, {rollout: (1, 1)}]
            ):
                with patch.object(routing, "run_command", return_value=process):
                    result = routing.live_check(
                        codex="codex",
                        codex_home=root,
                        cwd=root,
                        timeout=1,
                    )

            self.assertEqual(result["status"], "fail")
            self.assertIn("model", result["details"]["mismatches"][0])
            self.assertIn("effort", result["details"]["mismatches"][1])

    def test_live_probe_accepts_matching_persisted_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "child.jsonl"
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
                routing, "rollout_snapshot", side_effect=[{}, {rollout: (1, 1)}]
            ):
                with patch.object(routing, "run_command", return_value=process):
                    result = routing.live_check(
                        codex="codex",
                        codex_home=root,
                        cwd=root,
                        timeout=1,
                    )

            self.assertEqual(result["status"], "ok")
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


if __name__ == "__main__":
    unittest.main()
