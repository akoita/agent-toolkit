# Installation

The [README](../README.md) covers the marketplace install, which is the
recommended path. This page covers the alternatives: agent-led setup, manual
installation, and per-project installation.

To update an existing installation, see [Updating](updating.md).

## Marketplace details

The repository exposes one marketplace catalog for each platform. From a local
checkout, add the repository root and install the platform-specific package.

To distribute directly from GitHub, replace `.` in the marketplace-add command
with `akoita/agent-toolkit`.

The Claude package includes the Maestro skill and its three custom agents. Run
`/reload-plugins` in an existing session or start a new session after
installing.

The Codex package includes the skill, worker templates, installer, and CLI
fallback runner. Plugin installation does not write custom-agent TOML files into
`$CODEX_HOME/agents/`; the skill can use its bundled CLI fallback immediately.
Use the safe setup flow below when native custom agents and default routing
policy should also be installed.

## Safe agent-led setup

An agent can perform the setup, but configuration changes use a mandatory
preview checkpoint. From this checkout, ask Codex:

```text
Read tools/setup-agent-toolkit/SKILL.md completely and follow it to set up
Codex Maestro globally. Inspect and preview first. Do not modify developer
configuration until I approve the exact diff.
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
python tools/setup-agent-toolkit/scripts/configure_policy.py \
  --platform codex \
  --scope global
```

The command prints the resolved target and proposed diff without writing. The
agent may rerun it with `--apply` only after approval. Existing malformed or
duplicate managed markers, symlink targets, non-UTF-8 files, and unexpected
file types cause a hard stop for manual review.

## Manual Claude installation

Globally for all projects on a machine, copy or symlink the skill and copy its
three named agents into the personal Claude directories:

```bash
git clone git@github.com:akoita/agent-toolkit.git
mkdir -p ~/.claude/skills ~/.claude/agents
ln -s "$(pwd)/agent-toolkit/plugins/claude/maestro/skills/maestro" ~/.claude/skills/maestro
cp agent-toolkit/plugins/claude/maestro/agents/*.md ~/.claude/agents/
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

## Manual Codex installation

Run the installer with the Python environment used to launch Codex:

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py
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
failure signal. See [Updating](updating.md) for refreshing this installation
later, including the legacy files an upgrade leaves behind.

Run the installer once in Windows and once in WSL if you use separate Codex
installations in both environments; each environment has its own home and
Codex configuration directories.

## Per-project installation

Copy a skill into the platform's repository-scoped skills directory when it
should be checked in and shared with only that project:

```bash
cp -r plugins/codex/codex-maestro/skills/codex-maestro /path/to/repo/.agents/skills/
cp -r plugins/claude/maestro/skills/maestro /path/to/repo/.claude/skills/
mkdir -p /path/to/repo/.codex/agents /path/to/repo/.claude/agents
cp plugins/codex/codex-maestro/skills/codex-maestro/references/*-worker.toml /path/to/repo/.codex/agents/
cp plugins/claude/maestro/agents/*.md /path/to/repo/.claude/agents/
```

Copy only the platform and scope requested. Existing agent files are user-owned
configuration: compare and back them up rather than overwriting them.
