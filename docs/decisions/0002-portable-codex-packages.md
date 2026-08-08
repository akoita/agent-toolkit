# ADR 0002: Package every eligible Codex skill plugin with Agent Plugins

- Status: Accepted
- Date: 2026-08-09
- Scope: Codex skill-only packages
- Extends: [ADR 0001](0001-agent-plugins-compatibility.md)

## Context

ADR 0001 proved that the experimental
[Agent Plugins v1.0.0 specification](https://agent-plugins.org/specification)
can represent a skills-only package while generated adapters retain Agent
Toolkit's native marketplace identities. That decision deliberately limited
the implementation to one package while the repository evaluated the format.

The repository now has two eligible Codex skill plugins: `codex-security` and
`codex-maestro`. Both have a root skill tree and no MCP configuration. Keeping
only security portable would make compatibility depend on the historical spike
scope rather than a property users can understand consistently.

Claude Code does not currently consume the Agent Plugins package format. Its
native packages are therefore outside this compatibility claim. A generated
Claude security mirror exists only because the security skill bodies are shared
across platforms; it is not evidence of Agent Plugins support in Claude Code.

## Decision

Every eligible Codex skill plugin has a canonical Agent Plugins package:

1. `plugins/portable/security/` remains the canonical package for the shared
   security skills. It generates the `codex-security` adapter and the native
   Claude security mirror.
2. `plugins/portable/codex-maestro/` becomes the canonical package for the
   Codex-specific orchestration skill. It generates only the `codex-maestro`
   adapter.
3. Portable manifests declare only adapters that actually exist. The generator
   must not infer a Claude adapter for every portable package.
4. Native Codex manifests, marketplace entries, native skill trees, and the
   top-level skills catalog are generated mirrors of their portable sources.
5. Claude Maestro remains a separate native package and canonical skill. It is
   neither generated from nor represented by portable Codex Maestro.
6. Native marketplace installation remains the recommended complete install
   path. Portable packaging does not imply identical client behavior,
   permissions, updates, or user experience.

## Mapping

| Portable package | Generated Codex adapter | Generated Claude adapter |
| --- | --- | --- |
| `security` | `codex-security` | `security` skill mirror and manifest |
| `codex-maestro` | `codex-maestro` | None |

Repository-owned adapter metadata remains under the
`io.github.akoita.agent-toolkit` extension. Fields supported only by the native
Codex manifest, including `skills` and `interface`, are rendered from that
extension rather than added as non-standard portable fields.

## Consequences

- Agent Plugins compatibility is a visible repository capability rather than a
  security-only pilot.
- Adding another eligible Codex skill package requires a portable manifest and
  generator/tests coverage, not a hand-maintained native packaging contract.
- Claude packages remain honest native-only products; their existence does not
  broaden the compatibility claim.
- Agent Plugins validates package layout and discovery. It remains neither a
  sandbox nor a guarantee of equivalent behavior across clients.
