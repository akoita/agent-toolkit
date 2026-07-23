---
name: codex-maestro
description: >-
  Orchestrate non-trivial software implementation with capability-based GPT-5.6
  routing. Use gpt-5.6-sol for orchestration, demanding implementation, and
  review; use gpt-5.6-terra for economical read-heavy exploration, delegate
  bounded work, inspect the actual diff, and verify results. Use for features,
  bug fixes, refactors, tests, configuration, and infrastructure; skip trivial
  edits, pure analysis/review, or explicit no-delegation requests.
---

# Codex Maestro

This workflow is experimental. Codex and its models evolve quickly, and the
skill is not yet comprehensively tested. Inspect changes and verify results
before relying on them.

Use the root task as the maestro. Keep requirements, design decisions, final
review, Git publication, and user-facing communication in the root task.
Delegate bounded work to agents selected by capability, then verify it directly.

## Capability-based routing

Model names are configurable deployment choices, not agent identities. Use these
documented defaults unless repository policy or measured results justify an
override:

| Work | Default model and effort | Route |
| --- | --- | --- |
| Trivial, localized change | Current root session | Work directly; do not orchestrate |
| Read-heavy discovery, repository search, logs, or test triage | `gpt-5.6-terra`, `medium` | `exploration_worker` or another read-only native agent |
| Demanding implementation or review | `gpt-5.6-sol`, `medium` | Root maestro or `implementation_worker` |
| Critical or repeatedly failing work | `gpt-5.6-sol`, `high` | Root maestro; delegate only a bounded implementation |

`medium` is the normal implementation default. Raise effort to `high` only for
security-sensitive, architectural, migration, permissions, payments,
public-contract, highly ambiguous, or repeatedly failing work. Do not apply
`max` to every worker; use it only when a repository-specific evaluation shows
that its extra latency and cost improve outcomes.

Prefer native custom agents because the maestro can steer the same agent and
observe its lifecycle. Use `implementation_worker` for bounded writes and
`exploration_worker` for economical read-only discovery. If native role
selection is unavailable, use `scripts/run_implementation_worker.py` as the CLI
fallback. The implementation runner accepts `--model` and `--effort`, or
`CODEX_MAESTRO_WORKER_MODEL` and `CODEX_MAESTRO_WORKER_EFFORT`; its defaults are
`gpt-5.6-sol` and `medium`. Never claim a model or effort was used without native
configuration or CLI evidence.

Existing automation may temporarily call `scripts/run_luna_worker.py`; that
deprecated entry point forwards to the implementation runner with the new
defaults. Migrate callers to the functional filename rather than building new
dependencies on the alias.

For one-time standalone setup from a source checkout, run
`python scripts/install.py` from this skill directory. It installs the skill
and both custom-agent templates. A plugin installation can use the bundled CLI
fallback without additional setup; if a plugin user explicitly wants the
native custom-agent templates, run the same installer with `--agent-only` so it
does not create a duplicate standalone skill. Do not run the installer silently
during a task. See `references/implementation-worker.toml` and
`references/exploration-worker.toml` when checking or repairing configuration.

## Native subagent operating limits

- Favor parallelism for read-heavy exploration, test triage, and independent
  verification. Parallel writes carry merge and review cost.
- Run no more than two or three write-capable workers at once, and only when
  file ownership and verification boundaries are disjoint.
- Be aware of the configured `agents.max_threads` (the documented default is
  six); reserve capacity for the maestro and do not create agents merely to
  fill the limit.
- Keep the documented `agents.max_depth` default of one. Workers must not
  recurse or create their own subagents unless the maestro explicitly designs
  and reviews that topology.
- Native subagents inherit the parent task's approval policy and sandbox
  constraints. A role may narrow access (the exploration worker is read-only),
  but delegation must never be used to bypass parent restrictions.
- Workers must not commit, push, open or update pull requests, deploy, message
  people, change external services, or perform other external side effects.
- Send review findings back to the same agent when possible so it retains
  context. Start a replacement only when the original role or context is wrong.

## Phase 1: analyze and plan as the maestro

1. Read the request, repository instructions, relevant code, tests, and docs.
2. Resolve ambiguities and make design decisions. Ask the user only when a
   decision materially changes scope or causes a consequential external action.
3. Write a file-level plan naming files, symbols, behavior, edge cases, tests,
   and exact verification commands.
4. Split the plan into coherent work items. Parallelize only disjoint edits;
   serialize overlapping changes.
5. Keep architecture, security boundaries, migrations, commits, pushes, pull
   requests, and all external side effects in the root task.

Do not delegate an underspecified goal and expect a worker to invent the
maestro's decisions. Keep stable repository instructions and task framing at
the front of repeated prompts so prompt caching can help.

## Phase 2: delegate bounded work

Use read-only agents early when broad discovery can happen independently. After
the maestro reviews that evidence and decides the plan, prefer the native
`implementation_worker` custom agent for bounded code, test, configuration, and
documentation changes.

When native role selection is unavailable, write the worker prompt to a
temporary file and run:

```text
python <skill-dir>/scripts/run_implementation_worker.py \
  --cwd <repository-root> \
  --prompt <prompt-file> \
  --output <report-file> \
  --session-file <session-id-file>
```

Give each worker a self-contained contract:

```markdown
You are an implementation worker executing one item from a reviewed plan.
Work autonomously. Your final response is a report to the maestro.

## Task
<bounded goal and why it matters>

## Context
- Working directory and branch: <path and branch>
- Relevant files: <path plus role for each>
- Repository instructions: <only the rules needed for this item>

## Implementation plan
<numbered, file-level steps decided by the maestro>

## Constraints
- Only touch: <explicit paths or directory boundary>.
- Do not create subagents.
- Do not commit, push, open or update pull requests, message people, deploy, or
  perform other external side effects.
- Preserve unrelated user changes.
- If the plan is wrong or blocked, stop and report evidence; do not invent a
  different design.

## Definition of done
- <acceptance criteria>
- Run: <exact focused verification commands>

## Report
List files changed, commands and results, plan deviations, and open questions.
```

Keep doing useful maestro work while independent workers run: prepare review
criteria, inspect related contracts, or plan the next serialized item. Do not
duplicate delegated implementation.

## Phase 3: review as the maestro

Treat every worker report as a claim, not evidence:

1. Inspect the actual diff and every changed file.
2. Check the diff against the plan, repository rules, path boundary, security,
   privacy, and existing patterns.
3. Run focused tests, lint, type checks, builds, or other verification yourself.
4. Check for missing tests, docs, migrations, configuration, lifecycle effects,
   external side effects, and accidentally overwritten user work.
5. Decide whether the item is complete. The worker does not decide "done."

The root maestro owns final review. For critical work, use `gpt-5.6-sol` with
`high` effort when the running environment supports selecting it; do not add a
separate expensive review pass without a concrete risk or failure signal.

## Phase 4: steer the same worker

Send concrete review findings to the same native agent so it keeps context. For
a CLI worker, resume its recorded session:

```text
python <skill-dir>/scripts/run_implementation_worker.py \
  --cwd <repository-root> \
  --prompt <fix-prompt-file> \
  --output <report-file> \
  --resume <session-id>
```

Name the file and location, explain the defect, and state the required result.
Allow at most one targeted fix round by default. After the fix, inspect the new
diff and rerun verification. Escalate effort or stop and report when the defect
is architectural, risky, still unexplained, or beyond the task boundary.

## Phase 5: present and publish

Only the root maestro may present the result or perform repository commits,
pushes, and pull requests. Lead with the verified outcome, then state:

- the capability route and configured models/effort actually used;
- what shipped and which work items agents handled;
- commands and results independently verified by the maestro;
- deviations, escalation triggers, and remaining work.

Never pass a worker's unverified self-report through to the user. Treat model
cost and quality claims as hypotheses: measure successful-task cost, retries,
tool calls, latency, and regressions in the repositories that matter.

## Codex references

- [Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Current model guidance](https://developers.openai.com/api/docs/guides/latest-model)
