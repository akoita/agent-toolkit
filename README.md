# agent-toolkit

Project-agnostic agent skills, workers, and plugin packages for Claude Code and
Codex. Both platforms are first-class; platform-specific configuration stays
isolated so each tool loads only the format it understands.

> **Experimental.** Used regularly by the maintainer, but not comprehensively
> tested. Review generated changes before relying on them.

## Skills

| Platform | Skill | What it does |
| --- | --- | --- |
| Claude | [maestro](plugins/claude/maestro/skills/maestro/SKILL.md) | Capability-based orchestration across named subagents, experimental agent teams, and dynamic workflows. |
| Codex | [codex-maestro](plugins/codex/codex-maestro/skills/codex-maestro/SKILL.md) | Native-first GPT-5.6 orchestration with demanding implementation workers and economical read-only exploration. |
| Codex | [setup-agent-toolkit](tools/setup-agent-toolkit/SKILL.md) | Safely inspects, previews, installs, and configures Agent Toolkit without overwriting developer configuration. |

## Install

From a local checkout, add the repository root as a marketplace and install the
package for your platform. Replace `.` with `akoita/agent-toolkit` to install
straight from GitHub.

Claude Code:

```bash
claude plugin marketplace add .
claude plugin install maestro@agent-toolkit
```

Codex:

```bash
codex plugin marketplace add .
codex plugin add codex-maestro@agent-toolkit
```

Restart the tool afterwards. Then invoke `/maestro` or `$codex-maestro`, or let
the skill description trigger on non-trivial implementation work.

Prefer a manual install, a per-project install, or an agent-led setup with a
preview checkpoint? See [Installation](docs/installation.md).

## Update

Installed packages do not track this repository, and a stale one fails quietly
— the skill still loads but describes agents and defaults the package no longer
has.

```bash
claude plugin update maestro@agent-toolkit
```

Codex has no update subcommand; refresh the snapshot and reinstall:

```bash
codex plugin marketplace upgrade agent-toolkit
codex plugin add codex-maestro@agent-toolkit
```

For manual installs, checking what you have, and what an upgrade leaves behind,
see [Updating](docs/updating.md).

## Documentation

| Guide | Contents |
| --- | --- |
| [Installation](docs/installation.md) | Agent-led setup, manual install, per-project install |
| [Updating](docs/updating.md) | Refreshing each install path, release requirements |
| [Orchestration policy](docs/orchestration-policy.md) | Making Maestro the default via `AGENTS.md` / `CLAUDE.md` |
| [Conventions](docs/conventions.md) | Repository layout and contribution rules |
