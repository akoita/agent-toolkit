---
name: maestro
description: >-
  Maestro — the orchestrator pattern for development tasks: the session model
  (the maestro, typically a premium tier like Fable/Mythos) does the analysis,
  research and deep planning, then delegates the implementation to cheaper
  worker agents — Claude workers (Opus at high effort, Sonnet at max effort)
  or external-CLI workers (GPT via Codex CLI, Gemini CLI) — tracks the
  workers, reviews their output against the plan, sends targeted fix
  instructions until the work is right, and only then presents the verified
  result. Use this for ANY non-trivial dev task — implementing a feature,
  fixing a bug, refactoring, writing tests, wiring config or infra — even if
  the user just says "implement X" or "fix Y" without mentioning delegation.
  Do NOT use for pure analysis/planning/review questions with no code to
  write, for trivial single-file edits, or when the user explicitly asks the
  session model to write the code itself.
---

# Maestro — plan on the expensive model, implement on the cheap one

## Why this pattern

Premium-model tokens are expensive and are best spent on judgment:
understanding the problem, making design decisions, and catching mistakes.
Token-heavy mechanical work — writing the code the plan already describes —
lands almost as well on a cheaper model when the plan is detailed enough.
Anthropic's own measurements (SWE-bench Pro) show a cheap executor steered by
a premium planner reaches ~92% of the premium model's score at ~63% of the
cost. The quality lever is the plan and the review, not the hands on the
keyboard.

The corollary that makes or breaks this pattern: **a worker's output is only
as good as the plan you hand it, and its self-report is not evidence.** Invest
in phase 1, verify in phase 3.

## Roles

**The maestro is whatever model runs the session** — the pattern doesn't
require a specific one. It pays off when the session model is meaningfully
stronger and more expensive than the workers (Fable/Mythos orchestrating Opus
or Sonnet; Opus orchestrating Sonnet or Haiku). If the session model is
already in the cheap tier, skip the ceremony and implement directly.

The maestro never delegates:
- requirements analysis, codebase exploration, design decisions;
- the implementation plan itself;
- reviewing diffs, deciding "done", commits/PRs, and anything user-facing.

The maestro never does itself (unless the escape hatches below apply):
- bulk implementation the plan already fully describes.

## Phase 1 — Analyze and plan (maestro)

Do the expensive thinking first, exactly as if you were going to implement it
yourself:

1. Understand the request; read the relevant code, docs, and project
   conventions (CLAUDE.md, testing standards, existing patterns to imitate).
   Use read-only Explore subagents for broad searches to keep your own context
   lean.
2. Make the design decisions and resolve ambiguities NOW — every decision left
   open becomes a coin-flip inside the worker.
3. Write a detailed, file-level implementation plan: which files to create or
   change, what goes in each, function/route/schema names, edge cases, what
   tests to write, and the exact verification commands. If the project keeps
   plan docs (e.g. `docs/issue-NNN-implementation-plan.md`), write it there so
   it survives the session.
4. Split the plan into work items. One worker per coherent item. Items that
   touch disjoint files can run in parallel; overlapping items must run
   serially (or in isolated worktrees, merged by you).

## Phase 2 — Delegate (workers)

Pick a worker per item. Default to Claude workers via the Agent tool; use an
external-CLI worker when the user prefers it, when it's the available cheap
capacity, or when a second opinion from a different model family is valuable.

| Worker | How | When |
| --- | --- | --- |
| Claude Opus | Agent tool, `model: "opus"`, high effort | Default implementer — features, fixes, refactors, tests. |
| Claude Sonnet | Agent tool, `model: "sonnet"`, max effort | Well-specified mechanical/bulk work: renames, scaffolding, doc updates, repetitive tests, straightforward CRUD. |
| GPT (Codex CLI) | `codex exec --sandbox workspace-write "<prompt>"` via background Bash | When the user prefers GPT workers, Codex quota is the cheap capacity at hand, or a different model family should sanity-check a design. |
| Gemini CLI / other CLIs | analogous non-interactive exec mode | Same reasoning, if installed and authenticated. |

Never use a worker from the maestro's own premium tier — it defeats the
purpose. The Agent tool inherits the session's reasoning effort; when
orchestrating through the Workflow tool instead, set it explicitly
(`effort: 'high'` for opus, `effort: 'max'` for sonnet). For external CLIs,
inherit the model/effort configured in the CLI's own config unless the user
says otherwise.

External-CLI workers differ from Agent workers in ways that matter:
- **Probe availability first** — e.g. `timeout 60 codex exec --sandbox
  read-only "Reply OK"`; silence or a usage-limit error means pick another
  worker instead of hanging the task.
- **They don't read your harness context** (and may read different convention
  files, e.g. AGENTS.md instead of CLAUDE.md) — fold the project conventions
  that matter into the prompt itself.
- **Run them in background Bash** so you keep working; there is no completion
  notification beyond the process exiting.
- **State the no-commit constraint explicitly** — they have their own git
  habits.

The worker prompt must be fully self-contained — the worker sees none of your
conversation. Use this contract:

```
You are implementing one work item of a reviewed plan. Work autonomously.
Your final message is a report to the orchestrator, not to a human.

## Task
<one-paragraph goal and why>

## Context
- Working directory / branch: <path, branch>
- Key files and their roles: <paths + one line each>
- Conventions to follow: <the rules that actually matter for this item,
  e.g. no hardcoded config, test file naming; for Claude workers CLAUDE.md
  also applies automatically>

## Implementation plan
<the numbered, file-level steps for this item — copied from your plan>

## Constraints
- Only touch: <file list / directory>. Do NOT commit, push, or create PRs.
- If the plan turns out to be wrong or impossible, STOP and report why
  instead of improvising a different design.

## Definition of done
- <acceptance criteria>
- <exact verification commands, e.g. `cd backend && npm run lint && npm run test`>
  — run them; do not report success without their output.

## Report
Files changed, commands run with results, deviations from plan, open questions.
```

Agent-tool workers run in the background by default — spawn independent
workers in one message so they run concurrently, and keep doing useful maestro
work (drafting docs, preparing the next item's plan, writing the review
checklist) while they run. You are notified when each finishes.

## Phase 3 — Review (maestro)

When a worker reports, verify with your own eyes — never accept the report as
proof:

1. Read the actual diff (`git diff`, or read the changed files).
2. Run the verification commands yourself (tests, lint, build). The worker
   saying "tests pass" is a claim, not a result.
3. Check conformance: does it match the plan? project conventions? Any scope
   creep, hardcoded values, silently skipped steps, missing docs/tests?
4. Judge like a senior reviewer: correctness first, then simplicity, then
   style.

## Phase 4 — Iterate

If the review finds problems, send fix instructions **to the same worker so it
keeps its context** — much cheaper than re-briefing a fresh one:

- Claude workers: SendMessage to the agent.
- Codex workers: `codex exec --sandbox workspace-write resume --last "<fix
  instructions>"` (global options go BEFORE the `resume` subcommand).

Fix instructions must be as concrete as review comments: file, location, what
is wrong, what correct looks like. Vague feedback ("improve error handling")
produces a second bad round at full price.

Escape hatches — apply after **3 fix rounds** on the same item, or immediately
if the worker reports the plan is wrong:
- Small residual issues: fix them yourself inline; that's cheaper than another
  round trip.
- The plan was wrong: go back to phase 1, revise the plan, re-delegate.
- The item is genuinely too hard for the worker: implement that item yourself
  and say so in the final report. (Trying a stronger worker tier first — e.g.
  Sonnet item escalated to Opus — is also fair.)

## Phase 5 — Present (maestro)

Only after your own verification passes. Lead with the outcome, then:
- what shipped (per work item), which worker did it, and how it was verified
  (commands + results);
- any deviations from the plan and why;
- what was NOT done / follow-ups, with tracking if the project requires it.

Never present a worker's unverified claim as a result.

## When NOT to orchestrate

- Trivial changes (roughly: one file, a few lines, no design decisions) — the
  orchestration overhead costs more than it saves; just do it.
- Pure analysis, planning, debugging-diagnosis, or review requests — the
  deliverable is your judgment; there is nothing to delegate.
- The session model is already the cheap tier — no arbitrage to capture.
- The user explicitly asked you to implement directly ("don't delegate this
  one") — per-request only; revert to orchestrating afterwards.
- Mid-flight trivial corrections during review — fix inline.
