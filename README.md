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
| [security](plugins/claude/security/) | Claude Code | `security@agent-toolkit` | Seven security skills: repository audit, diff review, the free deterministic toolchain, supply chain, threat modeling, smart contracts, AI systems. |
| [codex-security](plugins/codex/codex-security/) | Codex | `codex-security@agent-toolkit` | The same seven security skills, packaged for Codex without the Claude agent definitions. |
| [setup-agent-toolkit](tools/setup-agent-toolkit/) | Codex | standalone | Safely inspects, previews, installs, and configures Agent Toolkit without overwriting developer configuration. |

Each skill's own README covers its configuration, models, and manual install.
The guides below cover mechanics shared by every skill.

## Install

Native marketplaces are the recommended, complete installation path for the
platform plugins. Add the repository root as a marketplace, then install the
plugin you want. Replace `.` with `akoita/agent-toolkit` to install straight
from GitHub.

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

For a portable, skill-only install through the
[skills CLI](https://www.skills.sh/docs):

```bash
npx skills add akoita/agent-toolkit --skill codex-maestro -g -a codex
npx skills add akoita/agent-toolkit --skill maestro -g -a claude-code
npx skills add akoita/agent-toolkit --skill setup-agent-toolkit -g -a codex
```

This path installs skill directories, not separate Claude agents or Codex
custom-agent TOMLs. See [Installation](docs/installation.md) for the worker
setup and tradeoffs. Use `npx skills update -g <skill>` to update a global
install and `npx skills remove -g <skill>` to remove one.

## Update

```bash
claude plugin update maestro@agent-toolkit
```

Codex has no update subcommand. For a marketplace added from GitHub, refresh
the snapshot and reinstall:

```bash
codex plugin marketplace upgrade agent-toolkit
codex plugin add codex-maestro@agent-toolkit
```

Installed another way — from a local path, or with a skill's own installer? The
steps differ. See [Updating](docs/updating.md).

## Remove

```bash
claude plugin uninstall maestro
codex plugin remove codex-maestro@agent-toolkit
```

Codex requires the `@agent-toolkit` qualifier. See
[Uninstalling](docs/uninstalling.md) for installer-based and manual installs.

## Documentation

| Guide | Contents |
| --- | --- |
| [Installation](docs/installation.md) | Marketplace, per-project, and agent-led install; scopes |
| [Updating](docs/updating.md) | Refreshing each install path; checking what you have |
| [Uninstalling](docs/uninstalling.md) | Removing each install path |
| [Contributing](docs/contributing.md) | Layout, conventions, adding a skill, releasing |
