# agent-toolkit

Project-agnostic agent skills, workers, and plugin packages for Claude Code and
Codex. Both platforms are first-class; platform-specific configuration stays
isolated so each tool loads only the format it understands.

> **Experimental.** Used regularly by the maintainer, but not comprehensively
> tested. Review generated changes before relying on them.

## Skills

| Skill | Platform | Install as | What it does |
| --- | --- | --- | --- |
| [maestro](plugins/claude/maestro/) | Claude Code | `maestro@agent-toolkit` | Capability-based orchestration across named subagents, agent teams, and dynamic workflows. |
| [codex-maestro](plugins/codex/codex-maestro/) | Codex | `codex-maestro@agent-toolkit` | Native-first GPT-5.6 orchestration with demanding implementation workers and economical read-only exploration. |
| [setup-agent-toolkit](tools/setup-agent-toolkit/) | Codex | standalone | Safely inspects, previews, installs, and configures Agent Toolkit without overwriting developer configuration. |

Each skill's own README covers its configuration, models, and manual install.
The guides below cover mechanics shared by every skill.

## Install

Add the repository root as a marketplace, then install any skill from the table
above. Replace `.` with `akoita/agent-toolkit` to install straight from GitHub.

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

Restart the tool afterwards, then invoke the skill by name or let its
description trigger it.

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

## Documentation

| Guide | Contents |
| --- | --- |
| [Installation](docs/installation.md) | Marketplace, per-project, and agent-led install; scopes |
| [Updating](docs/updating.md) | Refreshing an installed skill; checking what you have |
| [Contributing](docs/contributing.md) | Layout, conventions, adding a skill, releasing |
