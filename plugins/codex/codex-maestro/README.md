# codex-maestro

Implement and verify software changes with **Astra/medium alone by default**.
Request **economy mode** to use a **Sol/medium root with Luna/max workers**.
Requirements, architecture, review, and publication stay in the root task.

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
`$CODEX_HOME/agents/`. Default mode needs no worker setup. Economy preflight
requires the worker templates and native compatibility proof, even when later using the CLI
fallback. To add the agents, run the bundled installer — it ships inside the
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
  using `gpt-5.6-luna` at max effort by default;
- `exploration_worker` in the same agents directory, using `gpt-5.6-luna` at
  max effort with a read-only sandbox.

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

| Profile | Root | Workers |
| --- | --- | --- |
| Default | `gpt-6-astra`, `medium` | None |
| Economy (explicit opt-in) | `gpt-5.6-sol`, `medium` | `gpt-5.6-luna`, `max` |

Invoke `$codex-maestro` for the default, or say “Use Codex Maestro in economy
mode” to opt in. Default mode performs planning, implementation, and verification
in Astra without native or CLI workers. Economy delegates only bounded work.
It is a cost-oriented option; savings depend on the task. Astra with Luna is not
a supported profile.

Start a fresh Codex task with the matching root model and medium effort when
changing profiles; mixed historical routing fails closed.
The skill cannot switch the model of a running task and will stop on a mismatch.
Higher effort or a different model requires an explicit routing override.

## Fail-closed routing attestation

Before default work, verify the current Astra/medium root:

```bash
python <path>/skills/codex-maestro/scripts/check_routing.py --enforce
```

This reads persisted routing evidence without model calls, worker templates,
or an economy attestation. Missing, ambiguous, malformed, or mismatched root
evidence fails closed. The check verifies model and effort; the skill's
instructions enforce the no-delegation workflow.

Economy mode retains compatibility and worker verification:

```bash
python <path>/skills/codex-maestro/scripts/check_routing.py --profile economy --enforce
```

The attestation must match Codex, Maestro, config, checker/skill, and custom-agent
fingerprints, and the current root must prove Sol/medium. When the attestation
is missing or stale, run `check_routing.py --profile economy --live`, then rerun
enforcement. The live probe consumes tokens and attests only persisted proof of
a Sol/medium root and Luna/max implementation worker. Auth or runtime
unavailability is skipped, never accepted. `--live` requires economy explicitly.

Each new economy worker receives a minimal handshake until its exact rollout
passes `check_routing.py --profile economy --worker-rollout <path> --role <role>`.
Use `fork_turns: "none"` for the handshake, then reuse the verified worker for
the real assignment. Missing or mismatched evidence stops the worker before
substantive work. This bounds a routing regression to the handshake.

`check_routing.py --profile economy` diagnoses CLI, config, and agent declarations
without model calls. With no profile or flags, the script describes the default
route; use `--enforce` to verify it.

## Native collaboration

In economy mode, Maestro prefers the collaboration lifecycle exposed by the
running Codex client: spawn bounded agents, wait for results, steer the same worker after
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
- Default to `gpt-6-astra` at medium effort, working alone in the root.
  Do not spawn native or CLI workers in default mode.
- Use economy mode only when explicitly requested: `gpt-5.6-sol` at medium
  effort in the root with `gpt-5.6-luna` at max effort for bounded implementation
  and read-only exploration workers. Never silently combine Astra with Luna.
- Run Maestro's fail-closed routing preflight before substantive work; give a
  native worker its real task only after its persisted route is verified.
- Handle trivial, localized, low-risk work directly.
- Keep both profiles at medium root effort. For concrete risk or repeated
  failure, revisit the plan; changing the route requires an explicit override.
- Treat the agent workspace as shared: give parallel writers exclusive,
  disjoint ownership and serialize overlapping edits. Keep nesting disabled by
  default.
- In economy mode, prefer native spawn, wait, and same-worker steering; respect the
  effective runtime thread capacity and use the CLI worker only as a fallback.
- Follow the installed `codex-maestro` skill for the complete workflow.
- Do not delegate trivial work or pure analysis/review unnecessarily.
```

The instruction expresses routing policy, but it cannot change the model of an
already-running root task. Confirm the configured root and custom agent models
before claiming which model or effort performed the work.
