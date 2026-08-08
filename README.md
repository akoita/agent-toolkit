# agent-toolkit

Project-agnostic agent skills, workers, and plugin packages for Claude Code and
Codex. Both platforms are first-class; platform-specific configuration stays
isolated so each tool loads only the format it understands.

> **Experimental.** Used regularly by the maintainer, but not comprehensively
> tested. Review generated changes before relying on them.

## What it ships

A plugin is the unit of installation and versioning; it ships one or more
skills. Everything below installs from the same marketplace.

### Orchestration

| Plugin | Platform | Install as | What it does |
| --- | --- | --- | --- |
| [maestro](plugins/claude/maestro/) | Claude Code | `maestro@agent-toolkit` | Capability-based orchestration across named subagents, agent teams, and dynamic workflows. |
| [codex-maestro](plugins/codex/codex-maestro/) | Codex | `codex-maestro@agent-toolkit` | Native-first GPT-5.6 orchestration with demanding implementation workers and economical read-only exploration. |

### Security

Seven skills — repository audit, diff review, the free deterministic toolchain,
supply chain, threat modeling, smart contracts, and AI systems — shipped as one
plugin per platform. The skill bodies are identical on both; the Claude package
additionally ships two named agents.

| Plugin | Platform | Install as |
| --- | --- | --- |
| [security](plugins/claude/security/) | Claude Code | `security@agent-toolkit` |
| [codex-security](plugins/codex/codex-security/) | Codex | `codex-security@agent-toolkit` |

The security skills are authored once in the experimental Agent Plugins v1.0.0
package at [`plugins/portable/security/`](plugins/portable/security/). Generated
Claude and Codex adapters preserve the native install names and remain the
recommended installation path while direct client support matures. The
[compatibility decision](docs/decisions/0001-agent-plugins-compatibility.md)
records the boundary and support evidence.

### Standalone

| Skill | Platform | What it does |
| --- | --- | --- |
| [setup-agent-toolkit](tools/setup-agent-toolkit/) | Codex | Safely inspects, previews, installs, and configures Agent Toolkit without overwriting developer configuration. |

Each plugin's own README covers its skills, configuration, models, and manual
install. The guides below cover mechanics shared by every plugin.

## Install

Native marketplaces are the recommended, complete installation path. Add the
repository root as a marketplace once, then install any plugin from the tables
above by name. Replace `.` with `akoita/agent-toolkit` to install straight from
GitHub.

Claude Code:

```bash
claude plugin marketplace add .
claude plugin install <plugin>@agent-toolkit
```

Codex:

```bash
codex plugin marketplace add .
codex plugin add <plugin>@agent-toolkit
```

Both capability areas on Claude Code, for example:

```bash
claude plugin install maestro@agent-toolkit
claude plugin install security@agent-toolkit
```

Restart the tool afterwards, then invoke a skill by name or let its description
trigger it.

For a portable, skill-only install through the
[skills CLI](https://www.skills.sh/docs), name the **skill** rather than the
plugin — the security plugins carry seven of them:

```bash
npx skills add akoita/agent-toolkit --skill maestro -g -a claude-code
npx skills add akoita/agent-toolkit --skill codex-maestro -g -a codex
npx skills add akoita/agent-toolkit --skill security-audit -g -a claude-code
npx skills add akoita/agent-toolkit --skill setup-agent-toolkit -g -a codex
```

This path installs skill directories, not separate Claude agents or Codex
custom-agent TOMLs. See [Installation](docs/installation.md) for the worker
setup and tradeoffs. Use `npx skills update -g <skill>` to update a global
install and `npx skills remove -g <skill>` to remove one.

## Update

```bash
claude plugin update <plugin>@agent-toolkit
```

Codex has no update subcommand. For a marketplace added from GitHub, refresh
the snapshot and reinstall:

```bash
codex plugin marketplace upgrade agent-toolkit
codex plugin add <plugin>@agent-toolkit
```

Packages are released in lockstep, so one repository tag covers every plugin —
but each installed plugin is still updated on its own. Restart the tool
afterwards; reloading plugins does not pick up a version change.

Installed another way — from a local path, or with a skill's own installer? The
steps differ. See [Updating](docs/updating.md).

## Remove

```bash
claude plugin uninstall <plugin>
codex plugin remove <plugin>@agent-toolkit
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
