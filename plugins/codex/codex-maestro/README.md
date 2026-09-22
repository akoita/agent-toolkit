# codex-maestro

Analyze, plan, delegate, review, and verify software changes with a
**GPT-6 Sol/medium root and GPT-6 Luna/max workers**. This is the only supported route.
Requirements, architecture, final review, publication, and user communication
stay in the root task.

Maestro is an experimental workflow, not a demonstrated performance upgrade.
The [routing pilot](../../../docs/research/2026-09-maestro-routing-evaluation.md)
did not establish that installing the skill improves speed, cost, or quality
over using the same models directly. Its historical results describe only the
routes actually tested.

The full procedure is in [SKILL.md](skills/codex-maestro/SKILL.md). This native
package is generated from the [portable source](../../portable/codex-maestro/);
edit that source and synchronize the package rather than editing its mirrors.

## What it ships

- the `codex-maestro` skill;
- Luna/max implementation and exploration templates under
  [`skills/codex-maestro/references/`](skills/codex-maestro/references/);
- a standalone installer, fail-closed routing checker, and CLI implementation
  fallback under [`skills/codex-maestro/scripts/`](skills/codex-maestro/scripts/).

## Install and use

```bash
codex plugin marketplace add akoita/agent-toolkit
codex plugin add codex-maestro@agent-toolkit
```

A native plugin install provides the skill but does not write user-owned agent
configuration. Take the installed package path from `codex plugin list`, then
install the required custom agents:

```bash
python <path>/skills/codex-maestro/scripts/install.py --agent-only
```

Start a fresh Codex task using `gpt-6-sol` at `medium` effort and invoke
`$codex-maestro`. It delegates bounded implementation and read-only exploration
to `gpt-6-luna` agents at `max` effort while retaining planning, review,
verification, and external side effects in the root.

Before substantive work, the skill runs:

```bash
python <path>/skills/codex-maestro/scripts/check_routing.py --enforce
```

The checker validates the installed agent definitions and persisted Sol/medium
root route. Each new worker receives a minimal handshake before its real task;
verify its exact persisted rollout with:

```bash
python <path>/skills/codex-maestro/scripts/check_routing.py \
  --worker-rollout <exact-child-rollout.jsonl> \
  --role implementation_worker
```

Use `exploration_worker` for a scout. Missing, ambiguous, malformed, or
mismatched routing evidence fails closed. The skill cannot change a running
task's model.

## Standalone installer

From a checkout, install the skill and both custom agents together:

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py
```

The skill is copied to `~/.agents/skills/codex-maestro/`; the two worker TOMLs
are copied to `$CODEX_HOME/agents/` or `~/.codex/agents/`. Use `--link` to make
the skill follow a stable development checkout. `--skill-only` and
`--agent-only` provide explicit partial operations.

The installer refuses existing destinations without `--force`. Inspect and
back up local changes before replacement, especially agent TOMLs, because they
are user-owned configuration. Windows and WSL have separate homes and
installations.

## Updating from 0.7.4

Version 0.7.5 updates the supported route to GPT-6 Sol/medium and GPT-6
Luna/max. After updating a native plugin, explicitly refresh its agent files:

```bash
python <path>/skills/codex-maestro/scripts/install.py --agent-only --force
```

Review the exact diff first and preserve customized definitions. Plugin and
skills-CLI updates do not rewrite `$CODEX_HOME/agents/` automatically. Update
any managed Agent Toolkit policy with the setup workflow, then start a fresh
task so Codex reloads the plugin, workers, and base instructions.

The installer reports a legacy `luna-worker.toml` but does not delete it.
Inspect callers before retiring that file.

## Remove

For a marketplace installation, remove the required agent definitions before
removing the plugin:

```bash
python <path>/skills/codex-maestro/scripts/install.py --uninstall --agent-only
codex plugin remove codex-maestro@agent-toolkit
```

For a standalone installation, omit `--agent-only` to remove the skill and
unmodified agents together. Modified agent files are preserved unless
`--force` is explicitly supplied. Restart Codex after removal. See
[Uninstalling](../../../docs/uninstalling.md).

## Optional always-loaded policy

Use the [setup workflow](../../../tools/setup-agent-toolkit/SKILL.md) to preview
and apply a managed block to a personal or project `AGENTS.md`. A minimal policy
is:

```markdown
- Use `$codex-maestro` for non-trivial implementation and multi-step debugging.
- Use a `gpt-6-sol` root at medium effort with `gpt-6-luna` workers at max.
- Keep requirements, architecture, planning, final review, and publication in
  the root; delegate only bounded work with verified routing.
- Preserve unrelated user changes and prevent worker publication or nesting.
```
