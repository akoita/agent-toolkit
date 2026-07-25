# Installation

Mechanics shared by every skill in this repository. For a skill's own models,
agents, and manual install, see its README:

- [maestro](../plugins/claude/maestro/README.md) (Claude Code)
- [codex-maestro](../plugins/codex/codex-maestro/README.md) (Codex)

To refresh an existing installation see [Updating](updating.md); to remove one
see [Uninstalling](uninstalling.md).

## Marketplace install

The repository exposes one marketplace catalog per platform:
`.claude-plugin/marketplace.json` for Claude Code and
`.agents/plugins/marketplace.json` for Codex. Adding the repository root
registers whichever catalog the tool understands.

```bash
claude plugin marketplace add .
claude plugin install <skill>@agent-toolkit
```

```bash
codex plugin marketplace add .
codex plugin add <skill>@agent-toolkit
```

Replace `.` with `akoita/agent-toolkit` to install from GitHub instead of a
local checkout. Prefer the GitHub form unless you are developing against a
checkout, because the two behave differently on update: a local marketplace is
read from its path, while a Git one is a snapshot refreshed with
`codex plugin marketplace upgrade`. See [Updating](updating.md).

Run `/reload-plugins` in an existing Claude Code session or start a new
session. Restart Codex or open a new task.

A Codex plugin install does not write custom-agent TOML files into
`$CODEX_HOME/agents/`. Skills that ship worker agents can use their bundled CLI
fallback immediately; use the agent-led setup below, or the skill's own
installer, when native custom agents should also be installed.

## Agent-led install

The [setup-agent-toolkit](../tools/setup-agent-toolkit/SKILL.md) skill lets an
agent perform setup behind a mandatory preview checkpoint. From a checkout, ask
Codex:

```text
Read tools/setup-agent-toolkit/SKILL.md completely and follow it to set up
Codex Maestro globally. Inspect and preview first. Do not modify developer
configuration until I approve the exact diff.
```

It can install itself under `~/.agents/skills/setup-agent-toolkit/` for future
use, after which it is invoked as `$setup-agent-toolkit`. The skill limits the
agent to the requested platform and scope, refuses destructive replacement by
default, and requires it to:

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

The command prints the resolved target and proposed diff without writing.
Malformed or duplicate managed markers, symlink targets, non-UTF-8 files, and
unexpected file types cause a hard stop for manual review.

## Per-project install

Copy a skill into the platform's repository-scoped skills directory when it
should be checked in and shared with only that project:

```bash
cp -r plugins/codex/codex-maestro/skills/codex-maestro /path/to/repo/.agents/skills/
cp -r plugins/claude/maestro/skills/maestro /path/to/repo/.claude/skills/
```

Skills that ship agent definitions need those copied too, into
`/path/to/repo/.codex/agents/` or `/path/to/repo/.claude/agents/`. See the
skill's README for what it ships.

Copy only the platform and scope requested. Existing agent files are user-owned
configuration: compare and back them up rather than overwriting them.

## Scopes

| Scope | Claude Code | Codex |
| --- | --- | --- |
| Personal, all projects | `~/.claude/skills/`, `~/.claude/agents/` | `~/.agents/skills/`, `$CODEX_HOME/agents/` |
| Single project | `.claude/skills/`, `.claude/agents/` | `.agents/skills/`, `.codex/agents/` |

Install once per environment. Windows and WSL have separate homes and
configuration directories, so a skill installed in one is not visible in the
other.
