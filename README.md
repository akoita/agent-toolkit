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
    └── skills/
        ├── codex-maestro/
        │   ├── SKILL.md
        │   ├── agents/openai.yaml
        │   ├── references/luna-worker.toml
        │   └── scripts/
        └── setup-agent-toolkit/
            ├── SKILL.md
            ├── agents/openai.yaml
            └── scripts/configure_policy.py
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
| Claude | [remote-session-keeper](platforms/claude/skills/remote-session-keeper/SKILL.md) | Keeps remote (SSH/WSL) Claude Code sessions alive across desktop-GUI restarts with a per-project tmux launcher, and documents the `claude --continue` / `--resume` recovery path. Works around [claude-code#49790](https://github.com/anthropics/claude-code/issues/49790). |
| Codex | [codex-maestro](platforms/codex/skills/codex-maestro/SKILL.md) | Adaptive GPT-5.6 orchestration: Luna direct for economy, Sol Medium for serious development, Sol High for critical escalation, and Luna Max workers. |
| Codex | [setup-agent-toolkit](platforms/codex/skills/setup-agent-toolkit/SKILL.md) | Safely inspects, previews, installs, and configures Agent Toolkit without overwriting developer configuration. |

## Safe agent-led setup

An agent can perform the setup, but configuration changes use a mandatory
preview checkpoint. From this checkout, ask Codex:

```text
Read platforms/codex/skills/setup-agent-toolkit/SKILL.md completely and follow
it to set up Codex Maestro globally. Inspect and preview first. Do not modify
developer configuration until I approve the exact diff.
```

The workflow can optionally install itself under
`~/.agents/skills/setup-agent-toolkit/` for future use; after that, invoke it as
`$setup-agent-toolkit`. The skill limits the agent to the requested platform
and scope, refuses destructive replacement by default, and requires it to:

- inspect existing skills, workers, instruction files, symlinks, and conflicts;
- avoid secrets and unrelated Codex, Claude, MCP, hook, permission, or shell
  configuration;
- preview a unified diff before changing `AGENTS.md` or `CLAUDE.md`;
- use managed markers, timestamped backups, atomic writes, and post-write
  validation;
- report an explicit rollback path.

Its policy editor is dry-run by default. `--apply` is accepted only after the
preview has been approved:

```bash
python platforms/codex/skills/setup-agent-toolkit/scripts/configure_policy.py \
  --platform codex \
  --scope global
```

The command prints the resolved target and proposed diff without writing. The
agent may rerun it with `--apply` only after approval. Existing malformed or
duplicate managed markers, symlink targets, non-UTF-8 files, and unexpected
file types cause a hard stop for manual review.

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
  `gpt-5.6-luna` with max reasoning. The default Balanced profile uses Sol
  Medium as the root planner; select Sol High for Quality work and Luna directly
  for Economy work.

Use `--link` while developing the skill from this checkout. The installer
refuses an existing destination by default. Use `--force` only after inspecting
the existing installation, previewing the replacement, creating a verified
backup, and explicitly approving the destructive replacement. Restart Codex or
open a new task after installation, select Sol Medium for the Balanced profile,
and invoke `$codex-maestro` explicitly or let its description trigger on
non-trivial implementation work.

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

## Make Maestro the default

Use a short, always-loaded agent instruction to choose when Maestro should run,
and keep the detailed orchestration procedure in the skill. This makes the
default predictable without loading the full workflow into every task.

For Codex, put personal defaults in `~/.codex/AGENTS.md` and project-specific
rules in the repository's `AGENTS.md`:

```markdown
## Orchestration policy

- Use `$codex-maestro` for non-trivial implementation, investigation,
  architecture, planning, delegation, review, or multi-step debugging.
- Default to Balanced: Sol Medium orchestrates and Luna Max implements.
- Use Luna directly for trivial, localized, low-risk work.
- Escalate to Quality only for security-sensitive, architectural, migration,
  permissions, payments, public-contract, or highly ambiguous work.
- Quality uses Sol High as master/reviewer and Luna Max as worker.
- Do not use Sol Max or Sol Ultra unless the user explicitly changes this
  policy.
- Follow the installed `codex-maestro` skill for the complete workflow.
- Do not delegate trivial work unnecessarily.
```

The instruction expresses the desired routing policy, but it cannot change the
model of an already-running root task. Select Sol Medium before starting normal
Balanced work, or Sol High before critical Quality work.

For Claude Code, put personal defaults in `~/.claude/CLAUDE.md` and shared
project instructions in `CLAUDE.md` or `.claude/CLAUDE.md`:

```markdown
## Orchestration policy

- Use `/maestro` for non-trivial implementation work such as features, bug
  fixes, refactors, tests, configuration, or infrastructure.
- Keep analysis, design decisions, planning, review, and publication in the
  root session; delegate bounded implementation work as directed by the
  installed `maestro` skill.
- Do not orchestrate trivial edits, pure analysis or review, or tasks where the
  user explicitly requests direct implementation.
- Follow the installed `maestro` skill for worker selection, verification, and
  retry behavior.
```

Keep repository architecture, commands, security constraints, and coding
standards in `AGENTS.md` or `CLAUDE.md`. Keep multi-phase procedures, worker
contracts, fallback runners, and result formats in `SKILL.md`, where they are
loaded only when relevant. If both platforms are used, keep the two base files
as thin platform adapters rather than duplicating the full skill in each one.

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
