#!/usr/bin/env python3
"""Generate a revision-bound Action Bill of Materials from repository inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from validate_security_profile import (
    FULL_COMMIT,
    PACKAGE_WITH_DIGEST,
    SHA256_DIGEST,
    ValidationError,
    validate_document,
)


USES_PATTERN = re.compile(
    r"^\s*(?:-\s*)?uses:\s*[\"']?([^\"'\s#]+)[\"']?\s*(?:#\s*(.*))?$"
)
FROM_PATTERN = re.compile(r"^\s*FROM(?:\s+--platform=\S+)?\s+(\S+)", re.IGNORECASE)


def run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or "git command failed"
        raise ValueError(message)
    return result.stdout.strip()


def stable_id(kind: str, consumer: str, source: str) -> str:
    value = f"{kind}\0{consumer}\0{source}".encode()
    return f"input-{hashlib.sha256(value).hexdigest()[:16]}"


def is_immutable(kind: str, reference: str) -> bool:
    if kind in {"github_action", "reusable_workflow", "composite_action"}:
        return FULL_COMMIT.fullmatch(reference) is not None
    if kind == "container_image":
        return SHA256_DIGEST.fullmatch(reference) is not None
    return bool(
        FULL_COMMIT.fullmatch(reference)
        or SHA256_DIGEST.fullmatch(reference)
        or PACKAGE_WITH_DIGEST.fullmatch(reference)
    )


def entry(
    *,
    kind: str,
    consumer: str,
    source: str,
    reference: str,
    annotation: str,
    minimum_age_days: int,
    evidence: str,
) -> dict[str, Any]:
    immutable = is_immutable(kind, reference)
    return {
        "entry_id": stable_id(kind, consumer, source),
        "kind": kind,
        "consumer": consumer,
        "source": source,
        "immutable_ref": reference,
        "version_annotation": annotation or "not-annotated",
        "minimum_age_days": minimum_age_days,
        "permissions": ["not-resolved-by-generator"],
        "provenance": "unverified",
        "review_status": "review_required" if immutable else "blocked",
        "evidence": [evidence],
    }


def action_documents(root: Path) -> list[Path]:
    documents: set[Path] = set()
    for directory in (root / ".github" / "workflows", root / ".github" / "actions"):
        if directory.is_dir():
            documents.update(directory.rglob("*.yml"))
            documents.update(directory.rglob("*.yaml"))
    for name in ("action.yml", "action.yaml"):
        candidate = root / name
        if candidate.is_file():
            documents.add(candidate)
    return sorted(documents)


def scan_actions(
    root: Path, source_revision: str, minimum_age_days: int
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in action_documents(root):
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = USES_PATTERN.match(line)
            if not match:
                continue
            specification, annotation = match.groups()
            consumer = f"{relative}:{line_number}"
            if specification.startswith("docker://"):
                image = specification.removeprefix("docker://")
                if "@" in image:
                    source, reference = image.rsplit("@", 1)
                else:
                    source, reference = image, image.rsplit(":", 1)[-1]
                kind = "container_image"
            elif specification.startswith("./"):
                source = specification
                reference = source_revision
                kind = (
                    "reusable_workflow"
                    if ".github/workflows/" in specification
                    else "composite_action"
                )
            elif "@" in specification:
                source, reference = specification.rsplit("@", 1)
                kind = (
                    "reusable_workflow"
                    if "/.github/workflows/" in source
                    else "github_action"
                )
            else:
                source, reference, kind = specification, specification, "github_action"
            entries.append(
                entry(
                    kind=kind,
                    consumer=consumer,
                    source=source,
                    reference=reference,
                    annotation=annotation or "not-annotated",
                    minimum_age_days=minimum_age_days,
                    evidence=consumer,
                )
            )
    return entries


def scan_dockerfiles(root: Path, minimum_age_days: int) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    ignored = {".git", "node_modules", ".venv", "vendor"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not (
            path.name == "Dockerfile" or path.name.startswith("Dockerfile.")
        ):
            continue
        if any(part in ignored for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            match = FROM_PATTERN.match(line)
            if not match:
                continue
            image = match.group(1)
            if image.lower() == "scratch":
                continue
            if "@" in image:
                source, reference = image.rsplit("@", 1)
            else:
                source, reference = image, image.rsplit(":", 1)[-1]
            consumer = f"{relative}:{line_number}"
            entries.append(
                entry(
                    kind="container_image",
                    consumer=consumer,
                    source=source,
                    reference=reference,
                    annotation="Dockerfile FROM",
                    minimum_age_days=minimum_age_days,
                    evidence=consumer,
                )
            )
    return entries


def declared_utility(specification: str, minimum_age_days: int) -> dict[str, Any]:
    if "=" not in specification:
        raise ValueError("build utility must use SOURCE=IMMUTABLE_REF")
    source, reference = specification.split("=", 1)
    if not source.strip() or not reference.strip():
        raise ValueError(
            "build utility source and immutable reference must be non-empty"
        )
    return entry(
        kind="build_utility",
        consumer="command-line declaration",
        source=source.strip(),
        reference=reference.strip(),
        annotation="declared build utility",
        minimum_age_days=minimum_age_days,
        evidence=f"--build-utility {specification}",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-revision")
    parser.add_argument("--generated-at")
    parser.add_argument("--minimum-age-days", type=int, default=0)
    parser.add_argument(
        "--build-utility",
        action="append",
        default=[],
        metavar="SOURCE=IMMUTABLE_REF",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.repository.resolve()
    if not root.is_dir():
        print(f"repository does not exist: {root}", file=sys.stderr)
        return 2
    if args.minimum_age_days < 0:
        print("--minimum-age-days must be non-negative", file=sys.stderr)
        return 2

    try:
        source_revision = args.source_revision or run_git(root, "rev-parse", "HEAD")
        generated_at = args.generated_at or run_git(
            root, "show", "-s", "--format=%cI", source_revision
        )
        entries = scan_actions(root, source_revision, args.minimum_age_days)
        entries.extend(scan_dockerfiles(root, args.minimum_age_days))
        entries.extend(
            declared_utility(item, args.minimum_age_days) for item in args.build_utility
        )
    except (OSError, UnicodeError, ValueError) as error:
        print(f"generation failed: {error}", file=sys.stderr)
        return 2

    document = {
        "document_type": "agent-toolkit.action-bom",
        "schema_version": "1.0",
        "generated_at": generated_at,
        "source_revision": source_revision,
        "entries": sorted(entries, key=lambda item: (item["consumer"], item["source"])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    try:
        validate_document(document)
    except ValidationError as error:
        print(
            f"wrote inventory to {args.output}, but immutable-input validation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(f"wrote valid ABOM with {len(entries)} entries to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
