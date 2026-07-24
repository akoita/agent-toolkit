# Repository conventions

## Layout

```text
plugins/
├── claude/maestro/
│   ├── .claude-plugin/plugin.json
│   ├── agents/
│   └── skills/maestro/
└── codex/
    └── codex-maestro/
        ├── .codex-plugin/plugin.json
        └── skills/codex-maestro/
tools/setup-agent-toolkit/            # Safe standalone setup workflow
docs/                                 # Detailed guides
.claude-plugin/marketplace.json       # Claude Code catalog
.agents/plugins/marketplace.json      # Codex catalog
```

The plugin directories are both the canonical source and the installable
packages. Claude and Codex remain separate because their manifests, agent
definitions, installation scopes, and runtime capabilities differ.

## Rules

- Keep every skill project-agnostic: no repository-specific paths, secrets, or
  company context.
- Keep canonical skills inside their installable plugin packages.
- Give a workflow its own plugin when it needs an independent install or
  release lifecycle; bundle skills only when users should normally install and
  version them together.
- Use platform-specific IDs when runtime namespaces differ; the shared product
  concept can still be called Maestro in user-facing documentation.
- Keep the README short enough to read before installing. Detailed procedures
  belong in `docs/` or in the relevant `SKILL.md`.

## Releasing

See [Maintaining a release](updating.md#maintaining-a-release). The three
version fields move together, and the package tests assert that the marketplace
entry and plugin manifest agree.
