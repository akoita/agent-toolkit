# Updating

Installed packages do not track this repository. They stay at the version that
was installed until you refresh them, and a stale installation fails quietly:
the skill still loads, but it describes agents, scripts, or defaults that no
longer match the package. Check what you actually have before assuming an
installation is current.

```bash
claude plugin list
codex plugin list
ls -ld ~/.agents/skills/codex-maestro
```

The last command matters because a manual Codex installation is either a
symlink to a checkout, which follows that checkout, or a copy, which never
changes again.

## Claude Code

```bash
claude plugin update maestro@agent-toolkit
```

This refreshes the marketplace and the package together, and reports the
version change. Restart Claude Code afterwards; `/reload-plugins` does not pick
up a new version.

## Codex

Codex has no single update command. Refresh the marketplace snapshot, then
reinstall the package:

```bash
codex plugin marketplace upgrade agent-toolkit
codex plugin add codex-maestro@agent-toolkit
```

`marketplace upgrade` refreshes Git-sourced marketplaces only. A marketplace
added from a local path is read from that path, so it needs no refresh step.
Use `codex plugin remove codex-maestro` first if reinstalling over an existing
package is refused.

## Codex installed with the installer

Rerun the installer against the existing destination:

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py --force
```

`--force` is required because the installer refuses to replace an existing
destination. It deletes and rewrites the installed skill directory, so inspect
and back up any local edits first. The installer rewrites the worker TOML files
in `$CODEX_HOME/agents/` as well; those are user-owned configuration, so treat
customized copies as work to preserve rather than replace.

Adding `--link` once installs the skill as a symlink to the checkout, after
which `git pull` is the whole update procedure and the installation cannot
drift. Point it at a stable checkout, not a temporary worktree.

Renamed files are the reason an upgrade needs attention rather than a rerun.
The installer adds current files but does not remove ones a previous version
installed under a different name, so a stale worker TOML can outlive the
version that introduced it. It reports any legacy file it finds; retire those
separately after confirming nothing still references them.

## Maintaining a release

Updates only reach users when the version changes, so bump
`plugins/claude/maestro/.claude-plugin/plugin.json`,
`plugins/codex/codex-maestro/.codex-plugin/plugin.json`, and the matching entry
in `.claude-plugin/marketplace.json` together. Claude Code caches packages by
version, so content shipped under an unchanged version can be ignored by an
existing installation. `tests/test_claude_plugin_package.py` asserts that the
marketplace entry and the plugin manifest agree.
