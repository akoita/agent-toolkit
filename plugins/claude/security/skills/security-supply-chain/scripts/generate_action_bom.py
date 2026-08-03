#!/usr/bin/env python3
"""Generate a revision-bound Action Bill of Materials from repository inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
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


def git_top_level(root: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return Path(result.stdout.strip()).resolve()


def is_action_document(path: str) -> bool:
    candidate = Path(path)
    if candidate.name in {"action.yml", "action.yaml"} and len(candidate.parts) == 1:
        return True
    return (
        candidate.suffix in {".yml", ".yaml"}
        and len(candidate.parts) >= 3
        and candidate.parts[:2]
        in {
            (".github", "workflows"),
            (".github", "actions"),
        }
    )


def is_dockerfile(path: str) -> bool:
    name = Path(path).name
    return name == "Dockerfile" or name.startswith("Dockerfile.")


def is_input_document(path: str) -> bool:
    return is_action_document(path) or is_dockerfile(path)


def git_documents(root: Path, top_level: Path, source_revision: str) -> dict[str, str]:
    try:
        prefix = root.relative_to(top_level)
    except ValueError as error:
        raise ValueError("repository is outside its Git worktree") from error

    pathspec = prefix.as_posix() if prefix.parts else "."
    result = subprocess.run(
        [
            "git",
            "-C",
            str(top_level),
            "ls-tree",
            "-r",
            "--name-only",
            "-z",
            source_revision,
            "--",
            pathspec,
        ],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.decode(errors="replace").strip() or "git ls-tree failed"
        raise ValueError(message)

    documents: dict[str, str] = {}
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        repository_path = raw_path.decode("utf-8")
        relative = Path(repository_path).relative_to(prefix).as_posix()
        if not is_input_document(relative):
            continue
        blob = subprocess.run(
            [
                "git",
                "-C",
                str(top_level),
                "show",
                f"{source_revision}:{repository_path}",
            ],
            check=False,
            capture_output=True,
        )
        if blob.returncode != 0:
            message = blob.stderr.decode(errors="replace").strip() or "git show failed"
            raise ValueError(message)
        documents[relative] = blob.stdout.decode("utf-8")
    return documents


def filesystem_documents(root: Path) -> dict[str, str]:
    documents: dict[str, str] = {}
    ignored = {".git", "node_modules", ".venv", "vendor"}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        relative = relative_path.as_posix()
        if any(part in ignored for part in relative_path.parts):
            continue
        if is_input_document(relative):
            documents[relative] = path.read_text(encoding="utf-8")
    return documents


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


def yaml_mapping(line: str) -> tuple[int, str, str] | None:
    indentation = len(line) - len(line.lstrip(" "))
    content = line[indentation:]
    if not content or content.startswith(("#", "-")):
        return None

    quote: str | None = None
    escaped = False
    separator = -1
    for index, character in enumerate(content):
        if escaped:
            escaped = False
            continue
        if quote == '"' and character == "\\":
            escaped = True
            continue
        if character in {"'", '"'}:
            quote = (
                None if quote == character else character if quote is None else quote
            )
            continue
        if character == ":" and quote is None:
            separator = index
            break
    if separator < 0:
        return None

    key = content[:separator].strip().strip("'\"")
    if not key:
        return None
    return indentation, key, yaml_scalar(content[separator + 1 :])


def yaml_scalar(value: str) -> str:
    value = value.strip()
    quote: str | None = None
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote == '"' and character == "\\":
            escaped = True
            continue
        if character in {"'", '"'}:
            quote = (
                None if quote == character else character if quote is None else quote
            )
            continue
        if (
            character == "#"
            and quote is None
            and (index == 0 or value[index - 1].isspace())
        ):
            value = value[:index].rstrip()
            break
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value


def workflow_images(lines: list[str]) -> list[tuple[int, str, str]]:
    images: list[tuple[int, str, str]] = []
    stack: list[tuple[int, str]] = []
    for line_number, line in enumerate(lines, start=1):
        mapping = yaml_mapping(line)
        if mapping is None:
            continue
        indentation, key, value = mapping
        while stack and stack[-1][0] >= indentation:
            stack.pop()
        ancestors = [item[1] for item in stack]

        annotation = ""
        image = ""
        if len(ancestors) == 2 and ancestors[0] == "jobs" and key == "container":
            annotation = "GitHub Actions job container"
            image = value
        elif (
            len(ancestors) == 3
            and ancestors[0] == "jobs"
            and ancestors[2] == "container"
            and key == "image"
        ):
            annotation = "GitHub Actions job container"
            image = value
        elif (
            len(ancestors) == 4
            and ancestors[0] == "jobs"
            and ancestors[2] == "services"
            and key == "image"
        ):
            annotation = "GitHub Actions service container"
            image = value
        if image:
            images.append((line_number, image, annotation))
        stack.append((indentation, key))
    return images


def image_parts(image: str) -> tuple[str, str]:
    if "@" in image:
        source, reference = image.rsplit("@", 1)
        return source, reference
    return image, image.rsplit(":", 1)[-1]


def scan_actions(
    documents: dict[str, str], source_revision: str, minimum_age_days: int
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for relative, content in sorted(documents.items()):
        if not is_action_document(relative):
            continue
        lines = content.splitlines()
        for line_number, line in enumerate(lines, start=1):
            match = USES_PATTERN.match(line)
            if not match:
                continue
            specification, annotation = match.groups()
            consumer = f"{relative}:{line_number}"
            if specification.startswith("docker://"):
                image = specification.removeprefix("docker://")
                source, reference = image_parts(image)
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
        if not relative.startswith(".github/workflows/"):
            continue
        for line_number, image, annotation in workflow_images(lines):
            source, reference = image_parts(image)
            consumer = f"{relative}:{line_number}"
            entries.append(
                entry(
                    kind="container_image",
                    consumer=consumer,
                    source=source,
                    reference=reference,
                    annotation=annotation,
                    minimum_age_days=minimum_age_days,
                    evidence=consumer,
                )
            )
    return entries


def docker_from(line: str) -> tuple[str, str | None] | None:
    # Dockerfiles commonly end RUN/COPY/HEALTHCHECK lines with a continuation
    # backslash. Avoid feeding non-FROM instructions to shlex: a trailing
    # backslash is intentionally incomplete until the next physical line and
    # would otherwise make unrelated valid Dockerfiles fail discovery.
    if re.match(r"^\s*from(?:\s|$)", line, flags=re.IGNORECASE) is None:
        return None
    try:
        tokens = shlex.split(line, comments=True, posix=True)
    except ValueError as error:
        raise ValueError(f"invalid Dockerfile FROM instruction: {error}") from error
    if not tokens or tokens[0].lower() != "from":
        return None

    index = 1
    while index < len(tokens) and tokens[index].startswith("--"):
        index += 1
    if index >= len(tokens):
        return None
    image = tokens[index]
    alias = None
    if index + 2 < len(tokens) and tokens[index + 1].lower() == "as":
        alias = tokens[index + 2]
    return image, alias


def scan_dockerfiles(
    documents: dict[str, str], minimum_age_days: int
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for relative, content in sorted(documents.items()):
        if not is_dockerfile(relative):
            continue
        stage_aliases: set[str] = set()
        for line_number, line in enumerate(content.splitlines(), start=1):
            instruction = docker_from(line)
            if instruction is None:
                continue
            image, alias = instruction
            internal_stage = image.casefold() in stage_aliases
            if alias:
                stage_aliases.add(alias.casefold())
            if image.lower() == "scratch" or internal_stage:
                continue
            source, reference = image_parts(image)
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
        top_level = git_top_level(root)
        if top_level is None:
            if not args.source_revision or not args.generated_at:
                raise ValueError(
                    "non-Git repositories require --source-revision and --generated-at"
                )
            source_revision = args.source_revision
            generated_at = args.generated_at
            documents = filesystem_documents(root)
        else:
            requested_revision = args.source_revision or "HEAD"
            source_revision = run_git(
                root, "rev-parse", "--verify", f"{requested_revision}^{{commit}}"
            )
            generated_at = args.generated_at or run_git(
                root, "show", "-s", "--format=%cI", source_revision
            )
            documents = git_documents(root, top_level, source_revision)
        entries = scan_actions(documents, source_revision, args.minimum_age_days)
        entries.extend(scan_dockerfiles(documents, args.minimum_age_days))
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
