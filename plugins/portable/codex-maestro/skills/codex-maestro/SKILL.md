---
name: codex-maestro
description: >-
  Analyze, plan, implement, and verify non-trivial software changes with
  gpt-6-astra at medium effort in one root task. Keep review and publication
  in the root. Use for features, fixes, refactors, configuration, and multi-step
  debugging; skip trivial edits and pure analysis/review.
---

# Codex Maestro

Use one Astra/medium root for structured analysis, planning, implementation,
and verification. This workflow is experimental. The routing pilot did not
establish that installing this skill improves speed, cost, or quality over
using the same model directly. Verify changes against the task's requirements.

## Supported route

The only supported preset is `gpt-6-astra` at `medium` effort, working alone.
Do not spawn native workers, run CLI workers, or perform compatibility probes
as part of the standard workflow. Economy, Astra parallel, and advisor
configurations are research results, not supported presets. Do not infer
permission to delegate from task size or an old configuration file.

A skill cannot change an already-running root model. Before substantive work,
run the fail-closed preflight from this skill directory:

```text
python scripts/check_routing.py --enforce
```

It reads persisted routing metadata without model calls or worker setup.
It discovers the current task through `CODEX_THREAD_ID` or `CODEX_SESSION_ID`.
Missing, ambiguous, malformed, or changed routing evidence fails closed.
If the route is wrong, stop and explain that the user must start a fresh task
on Astra/medium. Do not plan, delegate, or silently switch routes. For repeated
failure or concrete risk, revisit the plan; a routing change requires an
explicit user override and verification of the actual route.

## 1. Analyze the problem

Read the request, repository instructions, relevant code, tests, and docs.
Capture the initial worktree state and preserve unrelated edits. Identify the
current behavior, required behavior, compatibility constraints, and acceptance
criteria. Distinguish observed facts from assumptions. Ask only for missing
information that materially changes the work and cannot be resolved locally.

## 2. Plan the steps

Write an ordered, file-level plan covering behavior, edge cases, and exact
verification commands. Keep the plan proportionate to the change. Identify
invariants that must remain true, especially existing error behavior, public
interfaces, and filesystem side effects. Resolve architectural choices before
implementation; revise the plan when new evidence contradicts it.

## 3. Implement directly

Make coherent, bounded changes in the root task. Follow existing patterns and
update affected documentation. Preserve user changes and avoid unrelated
cleanup. Add meaningful regression coverage for behavior changes rather than
tests that merely restate the implementation.

## 4. Review and verify

Inspect the actual diff against the requirements, plan, and compatibility
invariants. Run the focused tests and all repository-required checks. Verify
behavior independently of the implementation's assumptions: passing tests that
encode the same mistaken interpretation is insufficient. Check missing tests,
configuration, lifecycle effects, and accidental edits. Investigate failures,
fix their cause, and rerun the affected checks. The root owns final review.

## 5. Present and publish

Lead with the verified outcome, then report the changes, relevant validation,
and material limitations. State the actual route used when routing matters.
Commit, open pull requests, merge, release, or deploy when authorized by the
user and permitted by repository instructions. Do not claim savings or quality
improvements without comparable measurements.

## Explicit delegation overrides

If the user explicitly requests delegation for substantial independent work,
explain that it is outside the supported solo preset. Keep requirements,
architecture, planning, final review, and publication in the root. Agree on
any route override before model-specific delegation; do not silently select a
retired preset. A model name in a prompt is not execution evidence.

For an authorized override, inspect the client's available operations and
capacity. Give each worker a bounded task, exclusive path ownership, relevant
constraints, and no authority to publish or create subagents. Treat the
workspace as shared: serialize overlapping edits, stop on unexpected overlap,
and preserve others' changes. Verify actual routing before substantive work
when a specific route is required; missing evidence stops delegation. Review
the diff and run acceptance checks in the root before accepting a result.
There is no measured multi-worker speedup claim for this workflow.
