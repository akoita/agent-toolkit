# Updating

How you update depends on how you installed. Installed packages do not track
this repository, and a stale one fails quietly: the skill still loads, but it
describes agents, scripts, or defaults the package no longer has.

| Installed with | Update with |
| --- | --- |
| `claude plugin install` | `claude plugin update <skill>@agent-toolkit` |
| `codex plugin add`, Git marketplace | `codex plugin marketplace upgrade agent-toolkit` then `codex plugin add <skill>@agent-toolkit` |
| `codex plugin add`, local marketplace | `git pull` in the checkout, then `codex plugin add <skill>@agent-toolkit` |
| `npx skills add` | `npx skills update -g <skill>` for a global install, or omit `-g` for a project install |
| A skill's own installer, symlinked | `git pull` in the checkout |
| A skill's own installer, copied | Rerun the installer with `--force` |

Restart the tool afterwards. In Claude Code, `/reload-plugins` does not pick up
a new version.

## Which one am I?

```bash
claude plugin list
codex plugin list
ls -ld ~/.agents/skills/<skill>
```

The first two report the installed version. The third distinguishes a symlink,
which follows a checkout, from a copy, which never changes again.

`codex plugin marketplace list` shows whether a marketplace is local or Git.
Only Git marketplaces are snapshots, so only they can be upgraded — running
`codex plugin marketplace upgrade` against a local one reports that it is not a
Git marketplace. A local marketplace is read from its path, so pulling the
checkout is the update and the re-`add` reinstalls from it.

## skills CLI installs

Update all three global skill-only installs together:

```bash
npx skills update -g codex-maestro maestro setup-agent-toolkit
```

Or name one skill, and omit `-g` for a project-scoped installation. This updates
the installed skill directory only. If you installed Codex Maestro's native
custom-agent TOMLs separately, refresh them from the newly updated skill:

```bash
python ~/.agents/skills/codex-maestro/scripts/install.py --agent-only --force
```

Use the destination reported by the skills CLI if it differs. `--force`
replaces the existing TOMLs, so inspect and back up any local edits first.

## Reinstalling over an existing install

`codex plugin add` succeeds over an already-installed plugin and replaces it in
place; no removal step is needed first. Both platforms cache packages by
version, so a release that does not change the version can be ignored by an
existing installation.

## What an upgrade leaves behind

**Renamed files outlive their version.** An installer adds current files but
does not remove ones a previous version installed under a different name, so a
stale agent definition can survive an upgrade and keep being loaded. Installers
in this repository report legacy files they find rather than deleting them;
retire those separately after confirming nothing still references them.

**Customized agent files are yours.** Rerunning an installer with `--force`
overwrites agent definitions in `$CODEX_HOME/agents/` or `~/.claude/agents/`.
Back up local edits before forcing a replacement.

Skill-specific installers are documented with their skills:
[maestro](../plugins/claude/maestro/README.md),
[codex-maestro](../plugins/codex/codex-maestro/README.md).
