# Updating

Installed packages do not track this repository. They stay at the version that
was installed until you refresh them, and a stale installation fails quietly:
the skill still loads, but it describes agents, scripts, or defaults that no
longer match the package.

## Check what you have

```bash
claude plugin list
codex plugin list
ls -ld ~/.agents/skills/<skill>
```

The last command matters for skills installed outside the marketplace. A manual
installation is either a symlink to a checkout, which follows that checkout, or
a copy, which never changes again.

## Claude Code

```bash
claude plugin update <skill>@agent-toolkit
```

This refreshes the marketplace and the package together, and reports the
version change. Restart Claude Code afterwards; `/reload-plugins` does not pick
up a new version.

## Codex

Codex has no single update command. Refresh the marketplace snapshot, then
reinstall the package:

```bash
codex plugin marketplace upgrade agent-toolkit
codex plugin add <skill>@agent-toolkit
```

`marketplace upgrade` refreshes Git-sourced marketplaces only. A marketplace
added from a local path is read from that path, so it needs no refresh step.
Use `codex plugin remove <skill>` first if reinstalling over an existing
package is refused.

## Manual installs

A skill installed with its own installer or by hand is refreshed the same way
it was installed. See the skill's README:

- [maestro](../plugins/claude/maestro/README.md)
- [codex-maestro](../plugins/codex/codex-maestro/README.md)

Two things apply to any manual install:

**A symlinked install cannot drift.** Where a skill supports it, installing as
a symlink to a checkout makes `git pull` the whole update procedure. Point it
at a stable checkout, not a temporary worktree.

**Renamed files outlive their version.** An installer adds current files but
does not remove ones a previous version installed under a different name, so a
stale agent definition can survive an upgrade and keep being loaded. Installers
in this repository report legacy files they find rather than deleting them;
retire those separately after confirming nothing still references them.
