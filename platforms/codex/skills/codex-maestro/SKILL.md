---
name: codex-maestro
description: >-
  Orchestrate non-trivial software implementation with an adaptive GPT-5.6
  model policy: Luna for economical direct work, Terra Max as the default
  planner and integrator, and Sol Max for high-risk escalation. Delegate
  bounded implementation to Luna Max workers, review the actual diff, and
  verify results. Use for features, bug fixes, refactors, tests, configuration,
  and infrastructure; skip trivial edits, pure analysis/review, or explicit
  no-delegation requests.
---

# Codex Maestro

Use the root task as the maestro. Keep requirements, design decisions, review,
Git publication, and user-facing communication in the root task. Delegate
bounded implementation work to Luna Max workers, then verify it directly.

## Adaptive model profiles

The default is **Balanced**. Select the root model before starting the task;
the skill cannot change an already-running root session.

| Profile | Root/master | Worker | Use for |
| --- | --- | --- | --- |
| Economy | Luna, direct | None | Small, mechanical, low-risk work |
| Balanced (default) | Terra Max | Luna Max | Normal features, fixes, tests, and refactors |
| Quality | Sol Max | Luna Max | Architecture, security, migrations, ambiguity, or repeated worker failure |

Use `Sol Ultra` only when the task has several genuinely independent
workstreams and faster wall-clock completion is worth the extra parallel-token
cost. Do not make Ultra the default. Do not add a separate model review pass to
every task; automated tests and the master’s own diff review are usually enough.

Use the `luna_worker` custom agent, configured as `gpt-5.6-luna` with
`model_reasoning_effort = "max"`, for implementation. If native custom-agent
selection is unavailable, use `scripts/run_luna_worker.py`, which pins the same
model and effort through `codex exec`. Never claim a model or effort was used
without configuration or CLI evidence.

For one-time cross-project setup, run `python scripts/install.py` from this
skill directory. It installs the skill under the user's global Agent Skills
directory and the worker under the user's Codex agents directory. Do not run
the installer silently during a task. See `references/luna-worker.toml` when
checking or repairing the worker configuration.

## Route the task

1. Skip orchestration and use Luna directly for a trivial one-file edit or
   mechanical change with no meaningful design decision.
2. Use Balanced for the normal path: Terra Max plans and decomposes; Luna Max
   implements; Terra or the root session synthesizes and reviews the result.
3. Escalate to Quality when requirements are ambiguous, the change affects
   security, migrations, permissions, payments, public contracts, or lifecycle
   state; when tests fail for a reason the worker cannot isolate; or when the
   first plan is materially wrong.
4. Start with no more than two or three independent Luna work items. Add more
   only when the files and verification boundaries are genuinely disjoint.
5. Allow at most one targeted fix round by default. Stop and report when the
   budget, retry limit, or task boundary is reached.

When using the API, keep stable repository instructions and task framing at the
front of repeated prompts so prompt caching can help. Treat benchmark cost
curves as directional: measure successful task cost, retries, tool calls,
latency, and regressions in the repositories that matter.

## Phase 1: analyze and plan as the selected master

Do the judgment-heavy work before delegation:

1. Read the request, relevant code, repository instructions, tests, and docs.
2. Resolve ambiguities and make design decisions. Ask the user only when a
   decision materially changes scope or causes a consequential external action.
3. Write a file-level plan naming files, symbols, behavior, edge cases, tests,
   and exact verification commands.
4. Split the plan into coherent work items. Parallelize only disjoint edits;
   serialize overlapping changes.
5. Keep architecture, security boundaries, migrations, commits, pushes,
   pull requests, and other external side effects in the root task.

Do not delegate an underspecified goal and expect the worker to invent the
master's decisions.

## Phase 2: delegate implementation to Luna Max

Prefer the native `luna_worker` custom agent. When native role selection is not
available, write the worker prompt to a temporary file and run:

```text
python <skill-dir>/scripts/run_luna_worker.py \
  --cwd <repository-root> \
  --prompt <prompt-file> \
  --output <report-file> \
  --session-file <session-id-file>
```

The runner uses `CODEX_MAESTRO_WORKER_MODEL` and
`CODEX_MAESTRO_WORKER_EFFORT` only when an explicit environment override is
needed; their defaults are Luna and `max`.

Give each worker a self-contained contract:

```markdown
You are a Luna implementation worker executing one item from a reviewed plan.
Work autonomously. Your final response is a report to the master.

## Task
<bounded goal and why it matters>

## Context
- Working directory and branch: <path and branch>
- Relevant files: <path plus role for each>
- Repository instructions: <only the rules needed for this item>

## Implementation plan
<numbered, file-level steps decided by the master>

## Constraints
- Only touch: <explicit paths or directory boundary>.
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

Keep doing useful master work while independent workers run: prepare review
criteria, inspect related contracts, or plan the next serialized item. Do not
duplicate delegated implementation.

## Phase 3: review as the master

Treat the worker report as a claim, not evidence:

1. Inspect the actual diff and every changed file.
2. Check the diff against the plan, repository rules, scope boundary, security,
   privacy, and existing patterns.
3. Run focused tests, lint, type checks, builds, or other verification yourself.
4. Check for missing tests, docs, migrations, configuration, lifecycle effects,
   and accidentally overwritten user work.
5. Decide whether the item is complete. The worker does not decide "done."

For Quality tasks, Sol Max owns the final review. For Balanced tasks, Terra Max
or the root session owns it; do not spend Sol tokens unless an escalation
condition is met.

## Phase 4: iterate with the same worker

Send concrete review findings to the same native agent so it keeps context.
For a CLI worker, resume its recorded session:

```text
python <skill-dir>/scripts/run_luna_worker.py \
  --cwd <repository-root> \
  --prompt <fix-prompt-file> \
  --output <report-file> \
  --resume <session-id>
```

Name the file and location, explain the defect, and state the required result.
After each fix, inspect the new diff and rerun verification. Escalate to Sol
Max when the retry limit is reached or the defect is architectural or risky.

## Phase 5: present and publish

Only the root master may present the result or perform repository commits,
pushes, and pull requests. Lead with the verified outcome, then state:

- the selected profile and models used;
- what shipped and which work items Luna implemented;
- commands and results independently verified by the master;
- deviations, escalation triggers, and remaining work.

Never pass a worker's unverified self-report through to the user.
