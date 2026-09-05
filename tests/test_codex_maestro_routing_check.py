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

    def test_default_enforce_is_solo_and_needs_no_worker_setup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "root.jsonl"
            for model, effort, expected in (
                ("gpt-6-astra", "medium", 0),
                ("gpt-5.6-sol", "medium", 1),
                ("gpt-6-astra", "high", 1),
                ("gpt-5.6-luna", "max", 1),
            ):
                with self.subTest(model=model, effort=effort):
                    self.write_rollout(rollout, model=model, effort=effort)
                    output = io.StringIO()
                    with patch("subprocess.run") as run, contextlib.redirect_stdout(output):
                        code = routing.main([
                            "--enforce", "--root-rollout", str(rollout),
                            "--thread-id", "rollout-1",
                            "--codex-home", str(root), "--json",
                        ])
                    self.assertEqual(code, expected)
                    report = json.loads(output.getvalue())
                    self.assertEqual(report["profile"], "default")
                    self.assertEqual([c["name"] for c in report["checks"]], ["root.rollout"])
                    run.assert_not_called()

    def test_default_rejects_worker_operations_before_execution(self) -> None:
        for option in (["--live"], ["--worker-rollout", "worker.jsonl"],
                       ["--profile", "economy"], ["--profile", "astra-parallel"]):
            with self.subTest(option=option), \
                 patch("subprocess.run") as run, \
                 contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as raised:
                routing.main(option)
            self.assertEqual(raised.exception.code, 2)
            run.assert_not_called()

    def test_default_enforce_rejects_worker_as_root_and_wrong_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "root.jsonl"
            self.write_rollout(rollout, model="gpt-6-astra", effort="medium",
                               role="implementation_worker", parent="parent")
            self.assertEqual(routing.root_rollout_check(
                codex_home=root, rollout_path=rollout)["status"], "fail")
            self.write_rollout(rollout, model="gpt-6-astra", effort="medium")
            self.assertEqual(routing.root_rollout_check(
                codex_home=root, rollout_path=rollout, thread_id="wrong")["status"], "fail")

    def test_root_rollout_requires_identity_and_exact_route(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "sessions" / "root.jsonl"
            self.write_rollout(
                rollout,
                model=routing.DEFAULT_ROOT_MODEL,
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
                model="gpt-5.6-luna",
                effort="max",
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

    def test_changed_malformed_and_ambiguous_metadata_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "sessions" / "root.jsonl"
            for tail in (
                "not json",
                json.dumps({"type": "turn_context", "payload": {"model": "gpt-6-astra", "effort": "low"}}),
                json.dumps({"type": "turn_context", "payload": {"model": "gpt-6-astra"}}),
                json.dumps({"type": "session_meta", "payload": {"id": "other"}}),
            ):
                with self.subTest(tail=tail):
                    self.write_rollout(rollout, model="gpt-6-astra", effort="medium")
                    with rollout.open("a") as stream:
                        stream.write(tail + "\n")
                    self.assertEqual(routing.root_rollout_check(
                        codex_home=root, thread_id="rollout-1")["status"], "fail")
            self.write_rollout(rollout, model="gpt-6-astra", effort="medium")
            self.write_rollout(root / "archived_sessions" / "duplicate.jsonl",
                               model="gpt-6-astra", effort="medium")
            self.assertEqual(routing.root_rollout_check(
                codex_home=root, thread_id="rollout-1")["status"], "fail")

    def test_bad_encoding_and_filename_identity_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rollout = root / "sessions" / "requested-id.jsonl"
            self.write_rollout(rollout, model="gpt-6-astra", effort="medium", identifier="other")
            self.assertEqual(routing.root_rollout_check(
                codex_home=root, thread_id="requested-id")["status"], "fail")
            rollout.write_bytes(b"\xff\xfe")
            self.assertEqual(routing.root_rollout_check(
                codex_home=root, rollout_path=rollout)["status"], "fail")


if __name__ == "__main__":
    unittest.main()
