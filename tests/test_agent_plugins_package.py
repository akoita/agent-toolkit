from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "plugins" / "portable" / "security"
MANIFEST_PATH = PACKAGE_ROOT / "plugin.json"
SCHEMA_ROOT = ROOT / "schemas" / "agent-plugins" / "1.0.0"
PLUGIN_SCHEMA_PATH = SCHEMA_ROOT / "plugin.schema.json"
MCP_SCHEMA_PATH = SCHEMA_ROOT / "mcp.schema.json"
SYNC_SCRIPT = ROOT / ".github" / "scripts" / "sync_plugin_adapters.py"
EXPECTED_SKILLS = {
    "security-ai",
    "security-audit",
    "security-review",
    "security-scan",
    "security-smart-contracts",
    "security-supply-chain",
    "security-threat-model",
}

SPEC = importlib.util.spec_from_file_location("sync_plugin_adapters", SYNC_SCRIPT)
assert SPEC and SPEC.loader
sync_plugin_adapters = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync_plugin_adapters)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def schema_errors(manifest: object, schema: dict[str, Any]) -> list[str]:
    """Validate the v1 manifest schema constraints this package exercises.

    This is deliberately a small stdlib validator for the closed fields,
    required values, primitive types, name constraints, author, keywords, and
    extensions used here. It is not a general JSON Schema implementation or a
    client conformance harness.
    """
    if not isinstance(manifest, dict):
        return ["manifest must be an object"]

    errors: list[str] = []
    properties = schema["properties"]
    for required in schema["required"]:
        if required not in manifest:
            errors.append(f"missing required field: {required}")
    for field in manifest:
        if field not in properties:
            errors.append(f"unknown field: {field}")

    expected_types = {
        "string": str,
        "object": dict,
        "array": list,
    }
    for field, value in manifest.items():
        field_schema = properties.get(field)
        if field_schema is None:
            continue
        if "const" in field_schema and value != field_schema["const"]:
            errors.append(f"{field} does not match const")
        expected = expected_types.get(field_schema.get("type"))
        if expected is not None and not isinstance(value, expected):
            errors.append(f"{field} has wrong type")

    name = manifest.get("name")
    name_schema = properties["name"]
    if isinstance(name, str):
        if not name_schema["minLength"] <= len(name) <= name_schema["maxLength"]:
            errors.append("name has invalid length")
        if re.fullmatch(name_schema["pattern"], name) is None:
            errors.append("name does not match pattern")

    author = manifest.get("author")
    author_schema = properties["author"]
    if isinstance(author, dict):
        allowed = author_schema["properties"]
        for field, value in author.items():
            if field not in allowed:
                errors.append(f"unknown author field: {field}")
            elif not isinstance(value, str):
                errors.append(f"author.{field} has wrong type")

    keywords = manifest.get("keywords")
    if isinstance(keywords, list) and any(not isinstance(item, str) for item in keywords):
        errors.append("keywords contains a non-string")

    extensions = manifest.get("extensions")
    if isinstance(extensions, dict):
        if any(not isinstance(value, dict) for value in extensions.values()):
            errors.append("extension values must be objects")

    return errors


class AgentPluginsSchemaAndPackageTests(unittest.TestCase):
    """Schema/package assertions, not a full Agent Plugins client harness."""

    def test_vendored_schema_ids_and_bytes_are_pinned(self) -> None:
        expected = {
            PLUGIN_SCHEMA_PATH: (
                "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                "0a4aad95ce337878ad38802ebf0daa3fde76abe3f65400c86bcbb1ec0b3ab883",
            ),
            MCP_SCHEMA_PATH: (
                "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json",
                "6539175bfcdf43085855183e86da40ea94b166547a72b47ae9a0a390516d3acb",
            ),
        }
        for path, (schema_id, digest) in expected.items():
            with self.subTest(schema=path.name):
                self.assertEqual(read_json(path)["$id"], schema_id)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_manifest_satisfies_exercised_vendored_schema_requirements(self) -> None:
        manifest = read_json(MANIFEST_PATH)
        schema = read_json(PLUGIN_SCHEMA_PATH)

        self.assertEqual(schema_errors(manifest, schema), [])

    def test_validator_exercises_closed_and_nested_manifest_constraints(self) -> None:
        manifest = read_json(MANIFEST_PATH)
        schema = read_json(PLUGIN_SCHEMA_PATH)
        mutations = []

        missing_required = copy.deepcopy(manifest)
        del missing_required["$schema"]
        mutations.append(missing_required)
        wrong_const = copy.deepcopy(manifest)
        wrong_const["$schema"] = "https://example.test/schema.json"
        mutations.append(wrong_const)
        wrong_type = copy.deepcopy(manifest)
        wrong_type["version"] = 1
        mutations.append(wrong_type)
        bad_name = copy.deepcopy(manifest)
        bad_name["name"] = "Bad--Name"
        mutations.append(bad_name)
        unknown = copy.deepcopy(manifest)
        unknown["skills"] = "./skills"
        mutations.append(unknown)
        bad_author = copy.deepcopy(manifest)
        bad_author["author"]["company"] = "example"
        mutations.append(bad_author)
        bad_extension = copy.deepcopy(manifest)
        bad_extension["extensions"]["io.github.example"] = "invalid"
        mutations.append(bad_extension)

        for index, invalid in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertTrue(schema_errors(invalid, schema))

    def test_fixed_skill_discovery_and_frontmatter_names(self) -> None:
        immediate_directories = {
            path.name for path in (PACKAGE_ROOT / "skills").iterdir() if path.is_dir()
        }
        skill_roots = {
            path.name: path
            for path in (PACKAGE_ROOT / "skills").iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }

        self.assertEqual(immediate_directories, EXPECTED_SKILLS)
        self.assertEqual(set(skill_roots), EXPECTED_SKILLS)
        self.assertEqual(
            {
                path.parent.name
                for path in (PACKAGE_ROOT / "skills").rglob("SKILL.md")
            },
            EXPECTED_SKILLS,
        )
        for name, root in skill_roots.items():
            with self.subTest(skill=name):
                match = re.search(
                    r"(?m)^name:\s*([^\s]+)\s*$",
                    (root / "SKILL.md").read_text(encoding="utf-8"),
                )
                self.assertIsNotNone(match)
                assert match is not None
                self.assertEqual(match.group(1), name)

    def test_skills_only_package_omits_mcp_configuration(self) -> None:
        self.assertFalse((PACKAGE_ROOT / "mcp.json").exists())


class RepositorySecurityPolicyTests(unittest.TestCase):
    """Repository path-containment policy beyond JSON Schema validation."""

    def test_portable_package_contains_no_symlinks_or_path_escapes(self) -> None:
        resolved_root = PACKAGE_ROOT.resolve()
        for path in PACKAGE_ROOT.rglob("*"):
            with self.subTest(path=path.relative_to(PACKAGE_ROOT)):
                self.assertFalse(path.is_symlink())
                try:
                    path.resolve().relative_to(resolved_root)
                except ValueError:
                    self.fail(f"package path escapes plugin root: {path}")


class GeneratedAdapterTests(unittest.TestCase):
    def test_generated_native_adapters_are_in_sync(self) -> None:
        for relative, expected in sync_plugin_adapters.rendered_outputs(ROOT).items():
            with self.subTest(path=relative):
                self.assertEqual((ROOT / relative).read_bytes(), expected)

    def test_check_mode_reports_adapter_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (
                sync_plugin_adapters.PORTABLE_MANIFEST,
                sync_plugin_adapters.CLAUDE_MANIFEST,
                sync_plugin_adapters.CODEX_MANIFEST,
                sync_plugin_adapters.CLAUDE_MARKETPLACE,
                sync_plugin_adapters.CODEX_MARKETPLACE,
            )
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)

            drifted = root / sync_plugin_adapters.CODEX_MANIFEST
            drifted.write_text("{}\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SYNC_SCRIPT), "--check", "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            f"{sync_plugin_adapters.CODEX_MANIFEST}: out of sync", result.stdout
        )

    def test_write_mode_preserves_unrelated_marketplace_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (
                sync_plugin_adapters.PORTABLE_MANIFEST,
                sync_plugin_adapters.CLAUDE_MANIFEST,
                sync_plugin_adapters.CODEX_MANIFEST,
                sync_plugin_adapters.CLAUDE_MARKETPLACE,
                sync_plugin_adapters.CODEX_MARKETPLACE,
            )
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)

            before = {
                path: read_json(root / path)["plugins"][0]
                for path in (
                    sync_plugin_adapters.CLAUDE_MARKETPLACE,
                    sync_plugin_adapters.CODEX_MARKETPLACE,
                )
            }
            for path in before:
                catalog = read_json(root / path)
                catalog["plugins"][1] = {
                    "name": catalog["plugins"][1]["name"]
                }
                (root / path).write_text(
                    json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            result = subprocess.run(
                [sys.executable, str(SYNC_SCRIPT), "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            for path, unrelated_entry in before.items():
                with self.subTest(catalog=path):
                    self.assertEqual(
                        read_json(root / path)["plugins"][0], unrelated_entry
                    )


if __name__ == "__main__":
    unittest.main()
