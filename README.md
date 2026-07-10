# Agent skills

Personal, project-agnostic agent skills for Claude and Codex, kept in one place
for reuse across machines and projects. The repository retains its historical
`claude-skills` name for now, but new platform-specific material is separated
by directory.

## Skills

| Platform | Skill | What it does |
| --- | --- | --- |
| Claude | [maestro](skills/maestro/SKILL.md) | A premium Claude session model plans and reviews while bounded Claude or external-CLI workers implement. |
| Codex | [codex-maestro](codex/skills/codex-maestro/SKILL.md) | GPT-5.6 Sol plans and reviews; GPT-5.6 Luna at max reasoning implements bounded work items. Includes a native custom-agent template and a Codex CLI fallback. |

## Install Claude Maestro

Globally for all projects on a machine, copy or symlink the skill into the
personal Claude skills directory:

```bash
git clone git@github.com:akoita/claude-skills.git
ln -s "$(pwd)/claude-skills/skills/maestro" ~/.claude/skills/maestro
# or: cp -r claude-skills/skills/maestro ~/.claude/skills/
```

## Install Codex Maestro

Run the installer with the Python environment used to launch Codex:

```bash
python codex/skills/codex-maestro/scripts/install.py
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
cp -r codex/skills/codex-maestro <repo>/.agents/skills/
cp -r skills/maestro <repo>/.claude/skills/
```

The Luna custom agent remains a user-level Codex configuration. To make its
template project-scoped, copy it to `<repo>/.codex/agents/luna-worker.toml`.

## Conventions

- Keep every skill project-agnostic: no repository-specific paths, secrets, or
  company context.
- Put Claude skills under `skills/` for backward compatibility.
- Put Codex skills under `codex/skills/` and reusable Codex agent templates in
  the skill's `references/` directory.
- Use a skill for one reusable workflow. Add a plugin wrapper only when the
  workflow is stable enough for marketplace or team distribution, or when it
  needs bundled connectors, MCP configuration, or hooks.
