from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

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
        session: dict[str, object] = {"session_id": identifier, "id": identifier}
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

    @staticmethod
    def write_agents(codex_home: Path) -> None:
        agents = codex_home / "agents"
        agents.mkdir(parents=True, exist_ok=True)
        for filename, values in routing.AGENT_REQUIREMENTS.items():
            lines = [f'{key} = "{value}"' for key, value in values.items()]
            (agents / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")

    def run_json(self, args: list[str]) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = routing.main([*args, "--json"])
        return code, json.loads(output.getvalue())

    def test_default_enforce_requires_sol_medium_and_luna_ultra_agents(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "root.jsonl"
            self.write_agents(root)
            for model, effort, expected in (
                ("gpt-5.6-sol", "medium", 0),
                ("gpt-6-astra", "medium", 1),
                ("gpt-5.6-sol", "high", 1),
                ("gpt-5.6-luna", "ultra", 1),
            ):
                with self.subTest(model=model, effort=effort):
                    self.write_rollout(rollout, model=model, effort=effort)
                    code, report = self.run_json(
                        [
                            "--enforce",
                            "--root-rollout",
                            str(rollout),
                            "--thread-id",
                            "rollout-1",
                            "--codex-home",
                            str(root),
                        ]
                    )
                    self.assertEqual(code, expected)
                    self.assertEqual(report["profile"], "default")
                    self.assertEqual(
                        [check["name"] for check in report["checks"]],
                        ["agents.configuration", "root.rollout"],
                    )

    def test_agent_configuration_rejects_missing_or_wrong_templates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                routing.agent_templates_check(root / "agents")["status"], "fail"
            )
            self.write_agents(root)
            implementation = root / "agents" / "implementation-worker.toml"
            implementation.write_text(
                'name = "implementation_worker"\n'
                'model = "gpt-5.6-luna"\n'
                'model_reasoning_effort = "max"\n'
                'sandbox_mode = "workspace-write"\n',
                encoding="utf-8",
            )
            result = routing.agent_templates_check(root / "agents")
            self.assertEqual(result["status"], "fail")
            self.assertIn("model_reasoning_effort", result["details"]["failures"][0])

    def test_worker_rollout_supports_both_roles_and_rejects_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "worker.jsonl"
            for role in routing.EXPECTED_WORKER_ROLES:
                with self.subTest(role=role):
                    self.write_rollout(
                        rollout,
                        model="gpt-5.6-luna",
                        effort="ultra",
                        role=role,
                        parent="root-1",
                    )
                    self.assertEqual(
                        routing.verify_worker_rollout(rollout, role)["status"], "ok"
                    )
            for model, effort, role in (
                ("gpt-5.6-luna", "max", "implementation_worker"),
                ("gpt-5.6-sol", "ultra", "implementation_worker"),
                ("gpt-5.6-luna", "ultra", "exploration_worker"),
            ):
                with self.subTest(model=model, effort=effort, role=role):
                    self.write_rollout(
                        rollout,
                        model=model,
                        effort=effort,
                        role=role,
                        parent="root-1",
                    )
                    self.assertEqual(
                        routing.verify_worker_rollout(
                            rollout, "implementation_worker"
                        )["status"],
                        "fail",
                    )
            self.write_rollout(rollout, model="gpt-5.6-luna", effort="ultra")
            self.assertEqual(
                routing.verify_worker_rollout(
                    rollout, "implementation_worker"
                )["status"],
                "fail",
            )

    def test_worker_cli_requires_rollout_and_role_together(self) -> None:
        for option in (
            ["--worker-rollout", "worker.jsonl"],
            ["--role", "implementation_worker"],
            ["--profile", "economy"],
            ["--profile", "astra-parallel"],
        ):
            with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    routing.main(option)
            self.assertEqual(raised.exception.code, 2)

    def test_root_rollout_requires_identity_and_rejects_workers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "sessions" / "root.jsonl"
            self.write_rollout(
                rollout,
                model=routing.DEFAULT_ROOT_MODEL,
                effort=routing.EXPECTED_ROOT_EFFORT,
                identifier="root-1",
            )
            self.assertEqual(routing.root_rollout_check(codex_home=root)["status"], "fail")
            self.assertEqual(
                routing.root_rollout_check(codex_home=root, thread_id="root-1")[
                    "status"
                ],
                "ok",
            )
            self.write_rollout(
                rollout,
                model=routing.DEFAULT_ROOT_MODEL,
                effort=routing.EXPECTED_ROOT_EFFORT,
                role="implementation_worker",
                identifier="root-1",
                parent="parent",
            )
            self.assertEqual(
                routing.root_rollout_check(codex_home=root, rollout_path=rollout)[
                    "status"
                ],
                "fail",
            )

    def test_changed_malformed_and_ambiguous_metadata_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "sessions" / "root.jsonl"
            self.write_rollout(
                rollout,
                model=routing.DEFAULT_ROOT_MODEL,
                effort=routing.EXPECTED_ROOT_EFFORT,
            )
            with rollout.open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "type": "turn_context",
                            "payload": {"model": "gpt-5.6-sol", "effort": "low"},
                        }
                    )
                    + "\n"
                )
            self.assertEqual(
                routing.root_rollout_check(codex_home=root, thread_id="rollout-1")[
                    "status"
                ],
                "fail",
            )
            rollout.write_bytes(b"\xff\xfe")
            self.assertEqual(
                routing.root_rollout_check(codex_home=root, rollout_path=rollout)[
                    "status"
                ],
                "fail",
            )


if __name__ == "__main__":
    unittest.main()
