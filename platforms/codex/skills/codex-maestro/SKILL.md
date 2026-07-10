---
name: codex-maestro
description: Orchestrate non-trivial software implementation with GPT-5.6 Sol as the master planner and reviewer and GPT-5.6 Luna at max reasoning as the implementation worker. Use for features, bug fixes, refactors, tests, configuration, infrastructure, and other development tasks that benefit from separating design judgment from code-writing. Do not use for pure analysis or review with no implementation, trivial edits, or when the user explicitly asks the master to implement directly.
---

# Codex Maestro

Use the root task as the maestro. Keep requirements, design decisions, review,
Git publication, and all user-facing communication in the root task. Delegate
bounded implementation work to Luna workers, then verify their work directly.

## Require the intended models

- Run the root task on `gpt-5.6-sol`. A skill cannot change the model of an
  already-running root task. If the current model is known not to be Sol, state
  that before implementation and ask the user to switch unless they explicitly
  accept a different master.
- Use the `luna_worker` custom agent, configured as `gpt-5.6-luna` with
  `model_reasoning_effort = "max"`, for implementation.
- If the native custom-agent selector is unavailable, use
  `scripts/run_luna_worker.py`. It pins the same model and effort through
  `codex exec`.
- Never claim a worker used Luna Max unless its custom-agent configuration or
  CLI invocation proves it.

For one-time cross-project setup, run `python scripts/install.py` from this
skill directory. It installs the skill under the user's global Agent Skills
directory and the worker under the user's Codex agents directory. Do not run
the installer silently during a task. See `references/luna-worker.toml` when
checking or repairing the worker configuration.

## Phase 1: analyze and plan as Sol

Do the judgment-heavy work before delegation:

1. Read the request, relevant code, repository instructions, tests, and docs.
2. Resolve ambiguities and make the design decisions. Ask the user only when a
   decision materially changes scope or causes a consequential external action.
3. Write a file-level plan that names files, symbols, behavior, edge cases,
   tests, and exact verification commands.
4. Split the plan into coherent work items. Parallelize only items that can
   safely modify disjoint files; serialize overlapping edits.
5. Keep ownership of architecture, security boundaries, migrations, commits,
   pushes, pull requests, and other external side effects in the root task.

Do not delegate an underspecified goal and expect the worker to make the
maestro's decisions.

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
Work autonomously. Your final response is a report to the Sol maestro.

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
duplicate the delegated implementation.

## Phase 3: review as Sol

Treat the worker report as a claim, not evidence:

1. Inspect the actual diff and every changed file.
2. Check the diff against the plan, repository rules, scope boundary, security
   and privacy expectations, and existing patterns.
3. Run the focused tests, lint, type checks, builds, or other verification
   commands yourself.
4. Check for missing tests, docs, migrations, configuration, lifecycle effects,
   and accidentally overwritten user work.
5. Decide whether the item is complete. The worker does not decide "done."

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
After each fix, inspect the new diff and rerun verification.

After three unsuccessful fix rounds, choose one escape hatch:

- Fix a small residual issue directly.
- Revise a faulty plan and re-delegate it.
- Implement the item directly when it exceeds Luna's capability, and disclose
  that deviation in the final response.

## Phase 5: present and publish

Only the Sol maestro may present the result or perform the repository's commit,
push, and pull-request workflow. Lead with the verified outcome, then state:

- what shipped and which work items Luna implemented;
- the commands and results independently verified by Sol;
- any deviations and why they were necessary;
- remaining work, with durable tracking when project rules require it.

Never pass a worker's unverified self-report through to the user.

## Skip orchestration when it adds no value

Implement directly for a trivial one-file edit with no real design choice, a
small correction discovered during review, or when the user explicitly says
not to delegate. Do not orchestrate pure analysis, planning, diagnosis, or code
review requests because the deliverable is the maestro's judgment.
