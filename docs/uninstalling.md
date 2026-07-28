# Uninstalling

Remove a skill the same way it was installed.

| Installed with | Remove with |
| --- | --- |
| `claude plugin install` | `claude plugin uninstall <skill>` |
| `codex plugin add` | `codex plugin remove <skill>@agent-toolkit` |
| `npx skills add` | `npx skills remove -g <skill>` for a global install, or omit `-g` for a project install |
| A skill's own installer | Rerun the installer with `--uninstall` |
| Copied by hand | Delete the copied files |

Restart the tool afterwards so it stops loading the removed skill.

## Claude Code

```bash
claude plugin uninstall <skill>
```

Add `--scope project` or `--scope local` to remove an installation made at
those scopes; the default is `user`. `--keep-data` preserves the plugin's data
directory, and `--prune` also removes auto-installed dependencies that nothing
else needs.

## Codex

```bash
codex plugin remove <skill>@agent-toolkit
```

The marketplace qualifier is required. `codex plugin remove <skill>` on its own
reports that it needs `--marketplace` or a `<plugin>@<marketplace>` name.

Removing a plugin leaves the marketplace registered, which is usually what you
want. To deregister the catalog as well:

```bash
codex plugin marketplace remove agent-toolkit
```

## skills CLI

Remove the global skill-only installs from their target agents:

```bash
npx skills remove -g codex-maestro setup-agent-toolkit
npx skills remove -g maestro
```

Omit `-g` for project-scoped installs. With no `-a` filter, the skills CLI
removes the selected skills from every agent path where it installed them,
including its canonical shared copy. It never installed Claude's separate
named-agent definitions, so there is nothing additional to remove for
`maestro`.

If you used Codex Maestro's `--agent-only` setup, remove those native custom
agents **before** removing the skill, while its installer is still available:

```bash
python ~/.agents/skills/codex-maestro/scripts/install.py --uninstall --agent-only
npx skills remove -g codex-maestro
```

Use the actual installed skill path if it differs. Modified custom-agent files
are preserved unless you inspect them and explicitly add `--force`.

## Installer-based installs

A skill that ships its own installer removes what that installer created:

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py --uninstall
```

This removes the skill directory, whether it was copied or symlinked, and the
agent definitions the installer wrote. `--skill-only` and `--agent-only` narrow
it to one or the other, and `--codex-home` and `--skills-root` target a
non-default location.

The command above assumes a checkout. An installer also ships inside its
package, so a marketplace install can run the same script without one: take the
base path from the `PATH` column of `codex plugin list` and call
`python <path>/skills/<skill>/scripts/install.py --uninstall`.

Agent files you edited are treated as yours: an agent definition that no longer
matches the shipped template is kept and reported rather than deleted. Rerun
with `--force` to remove it anyway.

Files a previous version installed under a different name are not removed,
because the current installer does not know they exist. Legacy files are
reported on every run; delete those by hand after confirming nothing still
references them.

## Files installed by hand

A per-project or manual install is a plain copy, so removal is a delete. Check
both the skill and any agent definitions it shipped:

```bash
rm -rf ~/.agents/skills/<skill> ~/.claude/skills/<skill>
rm -f ~/.codex/agents/<agent>.toml ~/.claude/agents/<agent>.md
```

Agent files in those directories are user-owned configuration and may have been
edited since installation. Inspect before deleting.
