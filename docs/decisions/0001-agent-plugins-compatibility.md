# ADR 0001: Adapt Agent Plugins behind generated native compatibility

- Status: Accepted for an experimental pilot
- Date: 2026-08-08
- Scope: the shared security skill package

## Context

[Agent Plugins v1.0.0](https://agent-plugins.org/specification) is a Working
Draft for directory packages with a root `plugin.json`, fixed `skills/`
discovery, optional `mcp.json`, and reverse-domain client extensions. The
portable core standardizes package validation and discovery, not installation,
marketplaces, permissions, sandboxing, updates, or client user experience.

The [Agent Plugins compatible-client
directory](https://agent-plugins.org/compatible-clients) currently lists VS
Code, Cursor, GitHub Copilot, ChatGPT and Codex, and Kiro. Primary client
documentation also describes support:

- [VS Code agent plugins](https://code.visualstudio.com/docs/agent-customization/agent-plugins)
  recognize a root `plugin.json` and describe OpenPlugin cross-tool loading.
- [Cursor plugins](https://cursor.com/docs/plugins) and the compatible-client
  directory list skills and MCP support.
- [GitHub Copilot plugins](https://docs.github.com/en/copilot/concepts/agents/about-plugins)
  use a root `plugin.json` and discover skills under `skills/`.
- [Kiro powers](https://kiro.dev/docs/powers/) explicitly follow Agent Plugins
  and document `plugin.json`, `skills/`, `mcp.json`, and a `dev.kiro/`
  extension.

Client support is not yet interchangeable in this repository's two native
installation paths. The current [Claude Code plugin
reference](https://code.claude.com/docs/en/plugins-reference) documents the
native `.claude-plugin/plugin.json` format and separate Claude component
locations; no direct Agent Plugins root-manifest loading contract is stated.
The Agent Plugins directory lists ChatGPT and Codex, but the current official
[Codex plugin authoring guide](https://developers.openai.com/codex/build-plugins)
still creates `.codex-plugin/plugin.json` and local marketplace packages.
Therefore directory listings alone are not evidence that the existing Claude
and Codex marketplace commands can consume this repository's portable package
without adaptation.

Before this decision, the security skills were authored in the Claude package,
copied into the Codex package and the top-level skills catalog, and described by
two hand-maintained native manifests and two marketplace entries.

## Decision

Adopt a portable source package for security and adapt it behind generated
native compatibility:

1. `plugins/portable/security/` is the canonical skills-only Agent Plugins
   v1.0.0 package.
2. The package contains a root `plugin.json` and seven immediate skill
   directories. It intentionally has no `mcp.json`.
3. Portable metadata and repository-owned adapter data live in the manifest.
   The extension namespace `io.github.akoita.agent-toolkit` belongs to this
   repository's generator; it does not claim native semantics from any client.
4. `.github/scripts/sync_plugin_adapters.py` generates the existing Claude
   `security` and Codex `codex-security` manifests and updates only their
   marketplace entries. Public native install identities do not change.
5. `.github/scripts/sync_skills.py` copies the canonical skills into both native
   packages and the top-level skills catalog.
6. Native Claude agents remain hand-authored client-specific files. Agent
   definitions are outside Agent Plugins v1's portable component types.
7. Native marketplace installs remain the recommended complete installation
   path. The portable package is an interoperability and validation pilot, not
   a replacement distribution promise.

This is an **adapt** decision. It is neither a claim that every listed client
has identical support nor a third independently maintained packaging contract.

## Mapping

| Portable source | Claude adapter | Codex adapter | Notes |
| --- | --- | --- | --- |
| `plugin.json.name: security` | `security` | `codex-security` | Native public install identities are preserved. |
| Portable version | Native manifest and Claude catalog version | Native manifest version | All repository packages remain lockstep. Codex catalog entries have no version field. |
| Neutral description, author, homepage, repository, keywords | Claude-specific description and author shape | Codex-specific description plus portable metadata | Native differences come from the repository-owned extension. |
| Fixed `skills/<skill>/SKILL.md` | Generated `skills/` mirror | Generated `skills/` mirror | File sets, bytes, and executable bits must match. |
| `io.github.akoita.agent-toolkit.adapters.claude` | Native manifest/catalog fields | — | Generator-owned metadata, ignored by portable clients. |
| `io.github.akoita.agent-toolkit.adapters.codex` | — | Native manifest, `interface`, and catalog policy | `skills` and `interface` cannot be portable top-level fields because the v1 schema is closed. |
| No portable agent component | Hand-authored `agents/security-auditor.md` and `security-scan-runner.md` | No bundled agents | Agents are client-specific in this pilot. |
| No `mcp.json` | No MCP adapter | No MCP adapter | This decision makes no subprocess-support claim. |

## Validation and conformance boundary

The official v1.0.0 `plugin.schema.json` and `mcp.schema.json` are pinned under
`schemas/agent-plugins/1.0.0/` with upstream commit, Git blob, byte digest, and
license provenance. Tests and package loading do not fetch schemas from the
network.

`tests/test_agent_plugins_package.py` uses only the Python standard library. It
checks the vendored schema constraints exercised by this manifest: closed
top-level fields, required and constant values, types, name constraints,
nested author and extension shapes. It also checks fixed immediate-child skill
discovery, skill frontmatter names, absence of `mcp.json`, symlink/path
containment policy, pinned schema identifiers and digests, and generated adapter
drift.

Those checks validate this package and repository policy. They are not a full
JSON Schema implementation, do not exercise every schema branch, and do not
claim Agent Plugins client conformance. No runtime client behavior is inferred
from a green package test.

## Lifecycle and release implications

- The portable package participates in the existing version-bump gate and the
  repository-wide lockstep release version.
- A portable security change must update version `plugins/portable/security/plugin.json`
  and regenerate native adapters and skill mirrors. Generated native manifests
  receive the same version automatically.
- Check mode for both generators is an integrity gate. Marketplace updates
  preserve unrelated Maestro entries and deterministic JSON formatting.
- The release remains one repository tag and draft GitHub release. The tag now
  covers portable source plus native adapters; it does not publish to an Agent
  Plugins registry automatically.
- Vendored schemas change only through an explicit spec-version update with new
  provenance and digests. A Working Draft update is reviewed as a packaging
  contract change, not silently fetched during tests or loading.
- Existing Claude and Codex cache/update behavior remains authoritative for
  native installs. Portable version semantics do not override those clients.

## Security boundary and deferred MCP decision

Agent Plugins adds manifest/schema and path-containment validation. It is **not
a sandbox**. A valid package can still contain instructions or executable
content that becomes dangerous when a client grants tools, credentials,
network, filesystem, or subprocess access.

MCP and subprocess packaging is deferred to a separate ADR. Before adding
`mcp.json`, that decision must define and test:

- explicit user/admin approval and the narrowest permission boundary;
- subprocess sandboxing, executable provenance, command/path containment, and
  network egress controls;
- credential acquisition and storage without secrets in package `env` or
  headers;
- update, rollback, revocation, and dependency pinning behavior;
- ownership, retention, migration, and secure deletion for persistent
  `PLUGIN_DATA`;
- process failure isolation, logging, and incident response;
- release provenance, artifact integrity, schema/spec version matching, and a
  reproducible association between package version and shipped executable.

Until that ADR is accepted, the portable security package remains skills-only
and makes no MCP transport, process-launch, credential, or persistent-data
claim.

## Consequences

The security skill bodies and shared metadata now have one portable source, and
native clients retain their tested install experience. The cost is generator
and drift-test maintenance, plus continued client-specific files for features
outside the portable core. If direct client behavior later becomes sufficiently
stable and verified, a follow-up decision can remove an adapter; this ADR does
not assume that outcome.
