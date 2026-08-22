# codex-maestro

Native-first GPT-5.6 orchestration for Codex. Keeps requirements, architecture,
review, and publication in the root task and delegates bounded implementation to
custom worker agents.

This native Codex package is generated from the experimental
[Agent Plugins v1.0.0 source](../../portable/codex-maestro/). Its manifest,
marketplace metadata, and skill tree are mirrors; edit the portable source and
run the repository synchronization scripts instead of editing them here.

The full workflow is in [SKILL.md](skills/codex-maestro/SKILL.md).

## What it ships

- the `codex-maestro` skill;
- worker templates in
  [`skills/codex-maestro/references/`](skills/codex-maestro/references/);
- an installer, routing self-check, and CLI fallback runner in
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
  using `gpt-5.6-luna` at xhigh effort by default;
- `exploration_worker` in the same agents directory, using `gpt-5.6-luna` at
  xhigh effort with a read-only sandbox.

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

Model names are deployment choices, not agent identities. The root orchestrator
defaults to `gpt-5.6-sol` at medium effort. Both bounded implementation and
read-only exploration workers default to `gpt-5.6-luna` at xhigh effort.

Raise the root orchestrator above medium only for a concrete risk or failure
signal — security-sensitive, architectural, migration, permissions, payments,
public-contract, highly ambiguous, or repeatedly failing work. The worker
profiles remain pinned to Luna at xhigh.

## Fail-closed routing attestation

Run this before substantive Maestro work:

```bash
python <path>/skills/codex-maestro/scripts/check_routing.py --enforce
```

Enforcement fails unless a compatibility attestation matches the current Codex,
Maestro, config, checker/skill, and custom-agent fingerprints and the current
task's persisted rollout proves a Sol/medium root. A missing or changed
attestation requires one explicit `check_routing.py --live` probe. The probe
consumes model tokens but writes the attestation only when persisted root and
child metadata prove Sol/medium and `implementation_worker` Luna/xhigh. Auth or
runtime unavailability is skipped, never accepted.

Each newly spawned worker receives only a minimal handshake until its exact
rollout passes `check_routing.py --worker-rollout <path> --role <role>`. Reuse
that verified worker for the real assignment. A missing, malformed, Sol/medium,
wrong-effort, or wrong-role worker is interrupted and receives no substantive
work. This bounds a routing regression to the handshake instead of an entire
delegated task.

The ordinary `check_routing.py` mode remains a token-free diagnostic for the
CLI, config, and agent declarations.

## Native collaboration

Maestro prefers the collaboration lifecycle exposed by the running Codex
client: spawn bounded agents, wait for results, steer the same worker after
review, and stop obsolete or unsafe work. Use selective history inheritance,
peer evidence messages, thread listing, and thread closing only when the client
exposes them. Whenever native spawn fields are exposed, set `agent_type`,
`model`, and `reasoning_effort` explicitly; custom-agent TOMLs and global
defaults are declarations/fallbacks, not execution proof. If native spawning
cannot select model or effort and effective routing is required, use the
bundled implementation runner instead of a generic inheriting native worker.
Native topology alone does not prove the effective model or reasoning effort;
report those only from configuration, runtime, or explicit CLI evidence.

Concurrency is runtime-aware. The configured
`agents.max_concurrent_threads_per_session` cap counts spawned threads and
excludes the primary, while a product surface may report a smaller session slot
budget using different accounting. Normalize every limit to spawned-worker
slots first: subtract the primary from root-inclusive totals and use explicit
available-slot counts as reported. Respect the most restrictive normalized
limit and never create agents merely to fill it.

All native agents share the task workspace. Run parallel writers only with
explicit, disjoint path ownership; serialize overlapping edits and leave
conflict resolution to the root maestro. Subagent nesting stays disabled by
default even when the client technically permits it.

## Make it the default

Put an always-loaded instruction in `~/.codex/AGENTS.md` for personal defaults,
or the repository's `AGENTS.md` for project rules. Keep it short — the detailed
procedure stays in the skill.

```markdown
## Orchestration policy

- Use `$codex-maestro` for non-trivial implementation and multi-step debugging.
- Keep requirements, architecture, planning, review, and publication in the
  root task; delegate only bounded work with disjoint ownership.
- Default to Balanced: use `gpt-5.6-sol` at medium effort for the root
  orchestrator and `gpt-5.6-luna` at xhigh effort for bounded implementation
  and read-only exploration workers.
- Run Maestro's fail-closed routing preflight before substantive work; give a
  native worker its real task only after its persisted route is verified.
- Handle trivial, localized, low-risk work directly.
- Escalate to Quality only for security-sensitive, architectural, migration,
  permissions, payments, public-contract, or highly ambiguous work.
- Treat the agent workspace as shared: give parallel writers exclusive,
  disjoint ownership and serialize overlapping edits. Keep nesting disabled by
  default.
- Prefer native spawn, wait, and same-worker steering when exposed, passing
  explicit agent type/model/effort fields; if those fields are unavailable, use
  the CLI worker when effective routing is required.
- Follow the installed `codex-maestro` skill for the complete workflow.
- Do not delegate trivial work or pure analysis/review unnecessarily.
```

The instruction expresses routing policy, but it cannot change the model of an
already-running root task. Confirm the configured root and custom agent models
before claiming which model or effort performed the work.
