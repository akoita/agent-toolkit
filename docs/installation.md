# Installation

Mechanics shared by every skill in this repository. For a skill's own models,
agents, and manual install, see its README:

- [maestro](../plugins/claude/maestro/README.md) (Claude Code)
- [codex-maestro](../plugins/codex/codex-maestro/README.md) (Codex)
- [security](../plugins/claude/security/README.md) (Claude Code)
- [codex-security](../plugins/codex/codex-security/README.md) (Codex)

To refresh an existing installation see [Updating](updating.md); to remove one
see [Uninstalling](uninstalling.md).

## Recommended: marketplace install

The repository exposes one marketplace catalog per platform:
`.claude-plugin/marketplace.json` for Claude Code and
`.agents/plugins/marketplace.json` for Codex. Adding the repository root
registers whichever catalog the tool understands.

```bash
claude plugin marketplace add .
claude plugin install <plugin>@agent-toolkit
```

```bash
codex plugin marketplace add .
codex plugin add <plugin>@agent-toolkit
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

### Running a skill's installer after a marketplace install

Not every skill ships an installer script — the security packages, for
example, don't. Where one does, it ships inside the package, so you do not
need a checkout to run it. `codex plugin list` reports the installed package
path in its `PATH` column:

```bash
codex plugin list
```

Use that path as the base. For codex-maestro:

```bash
python <path>/skills/codex-maestro/scripts/install.py --agent-only
```

`--agent-only` writes the worker definitions without installing a second copy
of the skill, which the plugin already provides. Read the path from
`codex plugin list` rather than writing one down: the package also exists under
`$CODEX_HOME/plugins/cache/<marketplace>/<plugin>/<version>/`, and that location
changes with every release.

## Portable skill-only install

The [skills CLI](https://www.skills.sh/docs) can discover any skill from the
repository's top-level `skills/` catalog. Use it when you want a portable
skill-directory install without registering a native marketplace:

```bash
npx skills add akoita/agent-toolkit --skill codex-maestro -g -a codex
npx skills add akoita/agent-toolkit --skill maestro -g -a claude-code
npx skills add akoita/agent-toolkit --skill security-audit -g -a claude-code
npx skills add akoita/agent-toolkit --skill setup-agent-toolkit -g -a codex
```

A single-skill plugin like `maestro` or `codex-maestro` has one skill name to
choose. A multi-skill plugin like `security` or `codex-security` ships seven —
`security-audit`, `security-review`, `security-scan`, `security-supply-chain`,
`security-threat-model`, `security-smart-contracts`, and `security-ai` — and
each is installed separately, by name.

The `-g` flag installs for the current user; omit it for the current project.
The `-a` values are skills CLI agent identifiers. Review the discovered skill
contents before confirming the install.

This is deliberately a **skill-only** distribution. The CLI installs the
selected skill directory, including its nested scripts, references, and
metadata, but it does not install files from a plugin's separate `agents/`
directory or write Codex native custom-agent TOMLs. Native marketplace installs
remain the recommended complete path:

- `maestro` installed this way does not include the Claude plugin's named
  subagent definitions.
- `codex-maestro` retains its bundled implementation-worker CLI fallback. To
  enable its native Codex workers too, run the installer from the installed
  skill:

  ```bash
  python ~/.agents/skills/codex-maestro/scripts/install.py --agent-only
  ```

  If the skills CLI reports a different destination, use that installed path
  instead. The installer writes only the custom-agent templates in this mode.
- `security` installed this way does not include the Claude plugin's
  `security-auditor` and `security-scan-runner` named agents either, for the
  same reason as `maestro` — and the security packages ship no installer
  script, so there is no equivalent of the `codex-maestro` step above.
- `codex-security` ships no agent definitions at all, so a skill-only install
  of it is already complete.
- `setup-agent-toolkit` is self-contained and needs no separate worker install.

See [Updating](updating.md) and [Uninstalling](uninstalling.md) for the matching
skills CLI commands and native-agent lifecycle.

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

That covers a single-skill plugin. A plugin with several skills — `security`
and `codex-security` each ship seven, under `plugins/claude/security/skills/`
and `plugins/codex/codex-security/skills/` — needs one such `cp -r` per skill
directory you want, or a loop over the plugin's `skills/*` directory.

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
