# agent-toolkit

Project-agnostic agent skills, workers, and future plugin packages for Claude
Code and Codex. Claude and Codex are first-class platforms in this repository;
platform-specific configuration stays isolated so each tool can install and
load the format it understands.

## Repository layout

```text
platforms/
├── claude/
│   ├── agents/
│   │   ├── maestro-economical-explorer.md
│   │   ├── maestro-opus-implementation.md
│   │   └── maestro-sonnet-mechanical.md
│   └── skills/maestro/
└── codex/
    └── skills/
        ├── codex-maestro/
        │   ├── SKILL.md
        │   ├── agents/openai.yaml
        │   ├── references/implementation-worker.toml
        │   ├── references/exploration-worker.toml
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
| Claude | [maestro](platforms/claude/skills/maestro/SKILL.md) | Capability-based orchestration across named subagents, experimental agent teams, and dynamic workflows. |
| Codex | [codex-maestro](platforms/codex/skills/codex-maestro/SKILL.md) | Native-first GPT-5.6 orchestration with demanding implementation workers and economical read-only exploration. |
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

Globally for all projects on a machine, copy or symlink the skill and copy its
three named agents into the personal Claude directories:

```bash
git clone git@github.com:akoita/agent-toolkit.git
mkdir -p ~/.claude/skills ~/.claude/agents
ln -s "$(pwd)/agent-toolkit/platforms/claude/skills/maestro" ~/.claude/skills/maestro
cp agent-toolkit/platforms/claude/agents/*.md ~/.claude/agents/
```

Use a normal copy instead of the skill symlink when the checkout should not
remain the live source. Inspect existing destinations before either operation;
do not overwrite a customized agent definition. Claude Code 2.1.212 or later is
recommended for all subagent, resume, and worktree behavior described here.

Claude routing is capability-based. Use `best` or `fable` for an unusually
difficult main session, `opus` at high effort for correctness-sensitive
implementation, `sonnet` at medium or high effort for mechanical work, and the
provided Haiku explorer for economical read-only discovery. Aliases resolve
differently by provider and organization policy, so pin provider model mappings
only when reproducibility requires it. Dynamic workflows and Ultracode are for
large repeatable fan-out; experimental agent teams are reserved for workers
that must communicate directly.

## Install Codex Maestro

Run the installer with the Python environment used to launch Codex:

```bash
python platforms/codex/skills/codex-maestro/scripts/install.py
```

It installs:

- `codex-maestro` under `~/.agents/skills/`, making the skill available in all
  projects for that user;
- `implementation_worker` under `$CODEX_HOME/agents/` (or `~/.codex/agents/`),
  using `gpt-5.6-sol` at medium effort by default;
- `exploration_worker` in the same agents directory, using `gpt-5.6-terra` at
  medium effort with a read-only sandbox.

Use `--link` while developing the skill from this checkout. The installer
refuses an existing destination by default. Use `--force` only after inspecting
the existing installation, previewing the replacement, creating a verified
backup, and explicitly approving the destructive replacement. Restart Codex or
open a new task after installation and invoke `$codex-maestro` explicitly or
let its description trigger on non-trivial implementation work. Model and
effort defaults are configurable; raise effort only for a concrete risk or
failure signal. A legacy `luna-worker.toml` is not removed automatically during
an upgrade—inspect, back up, and retire it separately after confirming nothing
still references it.

Run the installer once in Windows and once in WSL if you use separate Codex
installations in both environments; each environment has its own home and
Codex configuration directories.

## Per-project installation

Copy a skill into the platform's repository-scoped skills directory when it
should be checked in and shared with only that project:

```bash
cp -r platforms/codex/skills/codex-maestro /path/to/repo/.agents/skills/
cp -r platforms/claude/skills/maestro /path/to/repo/.claude/skills/
mkdir -p /path/to/repo/.codex/agents /path/to/repo/.claude/agents
cp platforms/codex/skills/codex-maestro/references/*-worker.toml /path/to/repo/.codex/agents/
cp platforms/claude/agents/*.md /path/to/repo/.claude/agents/
```

Copy only the platform and scope requested. Existing agent files are user-owned
configuration: compare and back them up rather than overwriting them.

## Make Maestro the default

Use a short, always-loaded agent instruction to choose when Maestro should run,
and keep the detailed orchestration procedure in the skill. This makes the
default predictable without loading the full workflow into every task.

For Codex, put personal defaults in `~/.codex/AGENTS.md` and project-specific
rules in the repository's `AGENTS.md`:

```markdown
## Orchestration policy

- Use `$codex-maestro` for non-trivial implementation and multi-step debugging.
- Keep requirements, architecture, planning, review, and publication in the
  root task; delegate only bounded work with disjoint ownership.
- Default to Balanced: use `gpt-5.6-sol` for the root orchestrator and demanding
  workers, and `gpt-5.6-terra` for economical read-heavy exploration.
- Handle trivial, localized, low-risk work directly.
- Escalate to Quality only for security-sensitive, architectural, migration,
  permissions, payments, public-contract, or highly ambiguous work.
- Keep subagent nesting disabled by default and avoid parallel write-heavy work
  unless file ownership and verification boundaries are disjoint.
- Follow the installed `codex-maestro` skill for the complete workflow.
- Do not delegate trivial work or pure analysis/review unnecessarily.
```

The instruction expresses the desired routing policy, but it cannot change the
model of an already-running root task. Confirm the configured root and custom
agent models before claiming which model or effort performed the work.

For Claude Code, put personal defaults in `~/.claude/CLAUDE.md` and shared
project instructions in `CLAUDE.md` or `.claude/CLAUDE.md`:

```markdown
## Orchestration policy

- Use `/maestro` for non-trivial implementation work such as features, bug
  fixes, refactors, tests, configuration, or infrastructure.
- Keep analysis, design decisions, planning, review, and publication in the
  root session; delegate bounded implementation work as directed by the
  installed `maestro` skill.
- Use a few subagents for independent bounded work, agent teams only when
  workers must communicate, and dynamic workflows for large repeatable fan-out.
- Prefer documented model aliases and capability-based effort: `opus` at high
  effort for correctness-sensitive work and `sonnet` at medium or high effort
  for mechanical work.
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
