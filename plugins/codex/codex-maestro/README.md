# codex-maestro

Native-first GPT-5.6 orchestration for Codex. Keeps requirements, architecture,
review, and publication in the root task and delegates bounded implementation to
custom worker agents.

The full workflow is in [SKILL.md](skills/codex-maestro/SKILL.md).

## What it ships

- the `codex-maestro` skill;
- worker templates in
  [`skills/codex-maestro/references/`](skills/codex-maestro/references/);
- an installer and a CLI fallback runner in
  [`skills/codex-maestro/scripts/`](skills/codex-maestro/scripts/).

## Install

```bash
codex plugin marketplace add .
codex plugin add codex-maestro@agent-toolkit
```

A plugin install does not write custom-agent TOML files into
`$CODEX_HOME/agents/`; the skill uses its bundled CLI fallback immediately. To
add the native worker agents, run the bundled installer — it ships inside the
package, so no checkout is needed. Take the base path from the `PATH` column of
`codex plugin list`:

```bash
python <path>/skills/codex-maestro/scripts/install.py --agent-only
```

`--agent-only` skips the skill, which the plugin already provides.

See [Installation](../../../docs/installation.md) for per-project and agent-led
installs.

## Installer

From a checkout, run it with the Python environment used to launch Codex:

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py
```

It installs:

- `codex-maestro` under `~/.agents/skills/`, making the skill available in all
  projects for that user;
- `implementation_worker` under `$CODEX_HOME/agents/` (or `~/.codex/agents/`),
  using `gpt-5.6-sol` at medium effort by default;
- `exploration_worker` in the same agents directory, using `gpt-5.6-terra` at
  medium effort with a read-only sandbox.

Run it once per environment. Windows and WSL have separate Codex homes and
configuration directories.

### Updating

If you installed with `--link`, `git pull` in the checkout is the whole update
and the installation cannot drift. Point the symlink at a stable checkout, not
a temporary worktree.

Otherwise the installer refuses an existing destination, so rerun it with
`--force`:

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py --force
```

`--force` deletes and rewrites the installed skill directory, so inspect and
back up local edits first. It also rewrites the worker TOML files in
`$CODEX_HOME/agents/`; those are user-owned configuration, so treat customized
copies as work to preserve rather than replace.

The installer reports a legacy `luna-worker.toml` if it finds one but does not
delete it. Retire it separately after confirming nothing still references it.

### Removing

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py --uninstall
```

This removes the skill directory, copied or symlinked, and the two worker
definitions the installer wrote. A worker file you edited no longer matches the
shipped template, so it is kept and reported instead of deleted; rerun with
`--force` to remove it anyway. `--skill-only` and `--agent-only` narrow the
removal.

Without a checkout, run the same script from the installed package — take the
base path from the `PATH` column of `codex plugin list`, then
`python <path>/skills/codex-maestro/scripts/install.py --uninstall`.

For a plugin install, use `codex plugin remove codex-maestro@agent-toolkit` —
the marketplace qualifier is required. See
[Uninstalling](../../../docs/uninstalling.md).

## Model routing

Model names are deployment choices, not agent identities. The defaults are
`gpt-5.6-sol` at medium effort for orchestration, demanding implementation, and
review, and `gpt-5.6-terra` at medium effort for economical read-heavy
exploration.

Raise effort only for a concrete risk or failure signal — security-sensitive,
architectural, migration, permissions, payments, public-contract, highly
ambiguous, or repeatedly failing work. The skill documents an alternative that
keeps one model family and varies only reasoning effort.

## Make it the default

Put an always-loaded instruction in `~/.codex/AGENTS.md` for personal defaults,
or the repository's `AGENTS.md` for project rules. Keep it short — the detailed
procedure stays in the skill.

```markdown
## Orchestration policy

- Use `$codex-maestro` for non-trivial implementation and multi-step debugging.
- Keep requirements, architecture, planning, review, and publication in the
  root task; delegate only bounded work with disjoint ownership.
- Default to Balanced: use `gpt-5.6-sol` for the root orchestrator and demanding
  workers, and `gpt-5.6-terra` for economical read-heavy exploration.
- Handle trivial, localized, low-risk work directly.
- Escalate to Quality only for security-sensitive, architectural, migration,
  permissions, payments, public-contract, or highly ambiguous work.
- Keep subagent nesting disabled by default and avoid parallel write-heavy work
  unless file ownership and verification boundaries are disjoint.
- Follow the installed `codex-maestro` skill for the complete workflow.
- Do not delegate trivial work or pure analysis/review unnecessarily.
```

The instruction expresses routing policy, but it cannot change the model of an
already-running root task. Confirm the configured root and custom agent models
before claiming which model or effort performed the work.
