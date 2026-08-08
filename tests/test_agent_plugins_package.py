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
PACKAGE_ROOTS = {
    "codex-maestro": ROOT / "plugins" / "portable" / "codex-maestro",
    "security": ROOT / "plugins" / "portable" / "security",
}
MANIFEST_PATHS = {
    name: package / "plugin.json" for name, package in PACKAGE_ROOTS.items()
}
SCHEMA_ROOT = ROOT / "schemas" / "agent-plugins" / "1.0.0"
PLUGIN_SCHEMA_PATH = SCHEMA_ROOT / "plugin.schema.json"
MCP_SCHEMA_PATH = SCHEMA_ROOT / "mcp.schema.json"
SYNC_SCRIPT = ROOT / ".github" / "scripts" / "sync_plugin_adapters.py"
EXPECTED_SKILLS = {
    "codex-maestro": {"codex-maestro"},
    "security": {
        "security-ai",
        "security-audit",
        "security-review",
        "security-scan",
        "security-smart-contracts",
        "security-supply-chain",
        "security-threat-model",
    },
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
        schema = read_json(PLUGIN_SCHEMA_PATH)
        for name, path in MANIFEST_PATHS.items():
            with self.subTest(package=name):
                self.assertEqual(schema_errors(read_json(path), schema), [])

    def test_validator_exercises_closed_and_nested_manifest_constraints(self) -> None:
        manifest = read_json(MANIFEST_PATHS["security"])
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
        for package_name, package_root in PACKAGE_ROOTS.items():
            expected = EXPECTED_SKILLS[package_name]
            immediate_directories = {
                path.name
                for path in (package_root / "skills").iterdir()
                if path.is_dir()
            }
            skill_roots = {
                path.name: path
                for path in (package_root / "skills").iterdir()
                if path.is_dir() and (path / "SKILL.md").is_file()
            }

            with self.subTest(package=package_name, check="immediate directories"):
                self.assertEqual(immediate_directories, expected)
            with self.subTest(package=package_name, check="skill roots"):
                self.assertEqual(set(skill_roots), expected)
            with self.subTest(package=package_name, check="nested skill files"):
                self.assertEqual(
                    {
                        path.parent.name
                        for path in (package_root / "skills").rglob("SKILL.md")
                    },
                    expected,
                )
            for name, root in skill_roots.items():
                with self.subTest(package=package_name, skill=name):
                    match = re.search(
                        r"(?m)^name:\s*([^\s]+)\s*$",
                        (root / "SKILL.md").read_text(encoding="utf-8"),
                    )
                    self.assertIsNotNone(match)
                    assert match is not None
                    self.assertEqual(match.group(1), name)

    def test_skills_only_package_omits_mcp_configuration(self) -> None:
        for name, package_root in PACKAGE_ROOTS.items():
            with self.subTest(package=name):
                self.assertFalse((package_root / "mcp.json").exists())

    def test_portable_codex_maestro_declares_no_claude_adapter(self) -> None:
        manifest = read_json(MANIFEST_PATHS["codex-maestro"])
        adapters = manifest["extensions"][
            sync_plugin_adapters.EXTENSION_NAMESPACE
        ]["adapters"]

        self.assertEqual(set(adapters), {"codex"})

    def test_generated_adapter_paths_are_repository_contained(self) -> None:
        for package_name, manifest_path in MANIFEST_PATHS.items():
            manifest = read_json(manifest_path)
            adapters = manifest["extensions"][
                sync_plugin_adapters.EXTENSION_NAMESPACE
            ]["adapters"]
            for kind, adapter in adapters.items():
                with self.subTest(package=package_name, adapter=kind):
                    package = sync_plugin_adapters.adapter_package_path(kind, adapter)
                    self.assertFalse(package.is_absolute())
                    self.assertNotIn("..", package.parts)

    def test_generated_adapter_paths_must_target_matching_native_namespace(self) -> None:
        invalid_sources = (
            {"source": "local", "path": "./docs/example"},
            {"source": "local", "path": "./plugins/claude/example"},
            {"source": "local", "path": "./plugins/codex/..\\..\\outside"},
            {"source": "local", "path": "./plugins/codex/C:\\outside"},
            {"source": "local", "path": "./plugins/codex/\\\\server\\share"},
            {"source": "local", "path": "./plugins/codex/name:stream"},
        )
        for source in invalid_sources:
            with self.subTest(source=source["path"]):
                adapter = {"name": "example", "marketplace": {"source": source}}
                with self.assertRaisesRegex(
                    ValueError, r"must target its matching plugins/codex/<package-name>"
                ):
                    sync_plugin_adapters.adapter_package_path("codex", adapter)

        mismatched = {
            "name": "different",
            "marketplace": {
                "source": {
                    "source": "local",
                    "path": "./plugins/codex/example",
                }
            },
        }
        with self.assertRaisesRegex(ValueError, r"must target its matching"):
            sync_plugin_adapters.adapter_package_path("codex", mismatched)


class RepositorySecurityPolicyTests(unittest.TestCase):
    """Repository path-containment policy beyond JSON Schema validation."""

    def test_portable_package_contains_no_symlinks_or_path_escapes(self) -> None:
        for name, package_root in PACKAGE_ROOTS.items():
            resolved_root = package_root.resolve()
            for path in package_root.rglob("*"):
                with self.subTest(package=name, path=path.relative_to(package_root)):
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

    def test_generated_outputs_exclude_native_claude_maestro(self) -> None:
        claude_maestro = Path(
            "plugins/claude/maestro/.claude-plugin/plugin.json"
        )

        self.assertNotIn(claude_maestro, sync_plugin_adapters.rendered_outputs(ROOT))

    def test_check_mode_reports_adapter_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = set(sync_plugin_adapters.PORTABLE_MANIFESTS) | set(
                sync_plugin_adapters.rendered_outputs(ROOT)
            )
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)

            drifted_relative = Path(
                "plugins/codex/codex-maestro/.codex-plugin/plugin.json"
            )
            drifted = root / drifted_relative
            drifted.write_text("{}\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SYNC_SCRIPT), "--check", "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn(f"{drifted_relative}: out of sync", result.stdout)

    def test_write_mode_preserves_unrelated_marketplace_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = set(sync_plugin_adapters.PORTABLE_MANIFESTS) | set(
                sync_plugin_adapters.rendered_outputs(ROOT)
            )
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)

            unrelated_entry = {
                "name": "unrelated-test-plugin",
                "source": "./plugins/test",
                "custom": {"preserve": True},
            }
            expected_catalogs = {
                path: read_json(ROOT / path)
                for path in sync_plugin_adapters.MARKETPLACES.values()
            }
            generated_names = {
                sync_plugin_adapters.CLAUDE_MARKETPLACE: ("security",),
                sync_plugin_adapters.CODEX_MARKETPLACE: (
                    "codex-maestro",
                    "codex-security",
                ),
            }
            for path, names in generated_names.items():
                catalog = read_json(root / path)
                catalog["plugins"].append(unrelated_entry)
                for generated_name in names:
                    index = next(
                        index
                        for index, entry in enumerate(catalog["plugins"])
                        if entry["name"] == generated_name
                    )
                    catalog["plugins"][index] = {"name": generated_name}
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
            for path in sync_plugin_adapters.MARKETPLACES.values():
                with self.subTest(catalog=path):
                    entries = read_json(root / path)["plugins"]
                    self.assertIn(unrelated_entry, entries)
                    restored = {entry["name"]: entry for entry in entries}
                    expected = {
                        entry["name"]: entry
                        for entry in expected_catalogs[path]["plugins"]
                    }
                    for name in generated_names[path]:
                        self.assertEqual(restored[name], expected[name])


if __name__ == "__main__":
    unittest.main()
