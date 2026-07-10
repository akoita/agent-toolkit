# agent-toolkit

Project-agnostic agent skills, workers, and future plugin packages for Claude
Code and Codex. Claude and Codex are first-class platforms in this repository;
platform-specific configuration stays isolated so each tool can install and
load the format it understands.

## Repository layout

```text
platforms/
├── claude/
│   └── skills/maestro/
└── codex/
    └── skills/codex-maestro/
        ├── SKILL.md
        ├── agents/openai.yaml
        ├── references/luna-worker.toml
        └── scripts/
```

The current `maestro` and `codex-maestro` directories are standalone skills.
When a workflow is ready for marketplace or team distribution, package it under
`plugins/claude/` or `plugins/codex/` with the platform's manifest format. Do
not force Claude and Codex into one plugin: their manifests, agent definitions,
installation scopes, and runtime capabilities differ.

## Skills

| Platform | Skill | What it does |
| --- | --- | --- |
| Claude | [maestro](platforms/claude/skills/maestro/SKILL.md) | A premium Claude session model plans and reviews while bounded Claude or external-CLI workers implement. |
| Codex | [codex-maestro](platforms/codex/skills/codex-maestro/SKILL.md) | GPT-5.6 Sol plans and reviews; GPT-5.6 Luna at max reasoning implements bounded work items. |

## Install Claude Maestro

Globally for all projects on a machine, copy or symlink the skill into the
personal Claude skills directory:

```bash
git clone git@github.com:akoita/agent-toolkit.git
ln -s "$(pwd)/agent-toolkit/platforms/claude/skills/maestro" ~/.claude/skills/maestro
# or: cp -r agent-toolkit/platforms/claude/skills/maestro ~/.claude/skills/
```

Claude also supports packaging this workflow as a plugin when it is ready for
cross-project or team distribution.

## Install Codex Maestro

Run the installer with the Python environment used to launch Codex:

```bash
python platforms/codex/skills/codex-maestro/scripts/install.py
```

It installs:

- `codex-maestro` under `~/.agents/skills/`, making the skill available in all
  projects for that user;
- `luna_worker` under `$CODEX_HOME/agents/` (or `~/.codex/agents/`), pinning
  `gpt-5.6-luna` with max reasoning.

Use `--link` while developing the skill from this checkout. Rerun with
`--force` to replace an existing installation. Restart Codex or open a new task
after installation, select GPT-5.6 Sol for the root task, and invoke
`$codex-maestro` explicitly or let its description trigger on non-trivial
implementation work.

Run the installer once in Windows and once in WSL if you use separate Codex
installations in both environments; each environment has its own home and
Codex configuration directories.

## Per-project installation

Copy a skill into the platform's repository-scoped skills directory when it
should be checked in and shared with only that project:

```bash
cp -r platforms/codex/skills/codex-maestro <repo>/.agents/skills/
cp -r platforms/claude/skills/maestro <repo>/.claude/skills/
```

The Luna custom agent remains a user-level Codex configuration. To make its
template project-scoped, copy it to `<repo>/.codex/agents/luna-worker.toml`.

## Conventions

- Keep every skill project-agnostic: no repository-specific paths, secrets, or
  company context.
- Put Claude material under `platforms/claude/` and Codex material under
  `platforms/codex/`.
- Keep standalone skills as the source workflow. Add a platform-specific
  plugin package only when installation, versioning, marketplace distribution,
  connectors, hooks, or bundled agents justify it.
- Use platform-specific IDs when runtime namespaces differ; the shared product
  concept can still be called Maestro in user-facing documentation.
