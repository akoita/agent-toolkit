---
name: maestro
description: >-
  Orchestrate non-trivial development work in Claude Code. Keep requirements,
  architecture, planning, review, verification, publication, and user-facing
  communication in the main session; route bounded implementation to reusable
  Claude subagents, use experimental agent teams only when workers must
  communicate, and use dynamic workflows for large repeatable fan-out. Skip
  trivial edits, pure analysis/review, or explicit no-delegation requests.
---

# Maestro for current Claude Code

This workflow is experimental. Claude Code and its models evolve quickly, and
the skill is not yet comprehensively tested. Inspect changes and verify results
before relying on them.

Use the main session as the maestro. Spend its context on judgment and retain
ownership of the result; use workers to isolate implementation and high-volume
exploration. Treat cost/quality claims as hypotheses to measure on the actual
repositories: record successful-task cost, latency, retries, tool calls, and
regressions instead of relying on a universal benchmark percentage.

## Choose the session and worker models

Claude Code exposes capability aliases rather than requiring version-pinned
names:

- `best` selects Fable when the organization has access, otherwise the latest
  Opus. Use it for the main session when the task is unusually difficult and
  the automatic fallback is acceptable.
- `fable` explicitly selects the longest-running, highest-capability tier. Use
  it deliberately, not by default: see the escalation triggers below.
- `opus` selects the current Opus family. Since Opus 5 this is the routine
  default for the maestro session and for correctness-sensitive workers at
  `high` effort (features, fixes, refactors, tests).
- `sonnet` selects the current Sonnet family. Use a Sonnet worker at `medium`
  or `high` effort for well-specified, low-risk, mechanical work.

### Opus vs Fable since Opus 5

Opus 5 delivers near-Fable results on most measured software tasks — within
about half a percent of Fable 5 on agentic coding benchmarks, ahead of it on
some computer-use and problem-solving evaluations — at half the token price
($5/$25 versus $10/$50 per million input/output tokens). On benchmark and cost
evidence alone, Opus wins the default slot, and this skill treats it that way.

What benchmarks do not capture is Fable's remaining edge as a generalist: it is
the stronger model for delicate, ambiguous, high-stakes judgment where the cost
of a subtly wrong framing exceeds the cost of the tokens. Escalate the main
session (or a single review pass) to `fable` when any of these hold:

- the decision is strategic or hard to reverse: architecture with lasting
  consequences, security boundaries, data migrations, public contracts;
- requirements are genuinely ambiguous and a wrong interpretation would be
  expensive to discover late;
- the item is a critical review gate where a missed subtle defect has major
  project impact;
- Opus at `high` effort has already failed or produced conflicting analyses on
  a reasoning-heavy item.

Everything else — routine orchestration, planning over clear requirements, and
all implementation work — stays on `opus` or below. Do not run Fable as the
standing session model merely because it is available; record why any Fable
escalation happened in the final report. As always, treat these price and
capability claims as hypotheses to re-measure on your own repositories as the
aliases move.

Aliases are intentionally moving targets. Their concrete model IDs and feature
availability can differ across the Anthropic API, Bedrock, Google Cloud's Agent
Platform, Foundry, gateways, plans, and organization allowlists. Provider
administrators should pin the corresponding `ANTHROPIC_DEFAULT_*_MODEL`
variables or model overrides when rollout control and reproducibility matter.
Check `/status` and the active configuration before claiming a model ran.

Do not make `max` the routine worker setting. It removes the normal constraint
on reasoning-token spending and can add substantial cost and latency. Escalate
to `max` only for a specific difficult item after `high` was insufficient, or
when the risk justifies it. Record the reason in the final report.

Reusable definitions in this distribution:

- `maestro-opus-implementation`: Opus/high for correctness-sensitive work.
- `maestro-sonnet-mechanical`: Sonnet/medium for mechanical changes; raise an
  individual invocation to high when needed.
- `maestro-economical-explorer`: Haiku, strictly read-only exploration.

Install them as project agents under `.claude/agents/`, as personal agents
under `~/.claude/agents/`, or distribute them from a plugin's `agents/`
directory. Definitions are loaded by `name`, not by filename.

## Route the work

Choose the smallest orchestration primitive that fits:

| Shape | Route |
| --- | --- |
| Trivial edit or one short dependent task | Main session directly |
| Two or three bounded, independent items whose results only need to return to the maestro | Agent-tool subagents |
| Workers must share findings, challenge competing hypotheses, or coordinate across layers | Experimental agent team, after user approval |
| Large, repeatable fan-out such as repository-wide audits or migrations | Dynamic workflow; use a one-off Ultracode request first and save it only after validation |

Agent teams are experimental, disabled by default, and materially more
expensive than subagents. They require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
and user approval. Do not use them for sequential work, overlapping edits, or
when reports flowing back to one maestro are sufficient.

Dynamic workflows are JavaScript orchestration programs that can fan out many
agents while keeping intermediate results outside the main context. Ask for a
workflow or include `ultracode` in an interactive prompt for a one-off run. Use
`/effort ultracode` only when most substantive tasks in the current session
deserve automatic workflow planning; it combines xhigh reasoning with workflow
orchestration and therefore costs more. Inspect and approve the generated plan,
verify its result, then save stable repeated workflows under
`.claude/workflows/` or `~/.claude/workflows/`.

## Phase 1: analyze and plan in the main session

1. Read the request, relevant code, repository instructions, tests, and docs.
2. Resolve requirements, architecture, security boundaries, and product
   decisions before delegation. Ask the user only when a consequential choice
   cannot be resolved from the repository.
3. Write a file-level plan with behavior, symbols, edge cases, tests, docs, and
   exact verification commands.
4. Split it into coherent work items. Parallelize only disjoint edits; serialize
   overlapping files or shared state.
5. Keep commits, pushes, pull requests, deployments, messages, and all other
   external publication in the main session.

### Exploration caveat

As of current Claude Code, the built-in Explore agent inherits the main
session's model instead of always using a cheaper tier. Built-in Explore and
Plan also skip `CLAUDE.md` and the parent session's git status. This is useful
for fast generic search but can hide repository rules or working-tree context.
Use `maestro-economical-explorer` when model cost must be explicit or when the
normal custom-agent startup context matters. It pins the documented `haiku`
alias and omits `effort` because current Claude Code does not list Haiku among
the models supporting adaptive effort. Its tools are deliberately read-only;
include any task-specific conventions in its prompt anyway.

## Phase 2: delegate bounded implementation

Prefer named agents through the current `Agent` tool (`Task` is only a legacy
alias). Start with no more than two or three independent workers. Current
Claude Code normally places subagents in the background; background agents
continue concurrently but auto-deny tool calls that would require new
permission and cannot stop for interactive clarification. Use foreground
execution when permission prompts or immediate answers are necessary.

The implementation definitions omit `Agent` from their tool allowlist and
explicitly deny it. Workers must not recursively delegate. If another layer of
decomposition is genuinely needed, return the evidence to the maestro, which
decides whether to create another bounded item. Keep recursion shallow even
when a broader environment permits nested subagents.

Give each worker a self-contained contract:

```markdown
You are implementing one work item from a reviewed plan. Work autonomously.
Your final response is a report to the maestro, not to the user.

## Task
<bounded goal and why it matters>

## Context
- Working directory and branch: <path and branch>
- Key files and roles: <paths and one line each>
- Repository rules: <only the rules needed for this item>

## Implementation plan
<numbered, file-level steps decided by the maestro>

## Constraints
- Only touch: <explicit paths or directory boundary>.
- Do not spawn agents, commit, push, create or update pull requests, deploy,
  message people, or perform external side effects.
- Preserve unrelated changes.
- If the plan is wrong or blocked, stop and report evidence; do not invent a
  different design.

## Definition of done
- <acceptance criteria>
- Run: <exact focused verification commands>

## Report
List files changed, commands and results, deviations, and open questions.
```

### Worktree isolation

Use `isolation: worktree` or ask for a worktree only when parallel writers need
separate checkouts and the integration plan is explicit. It is not a universal
safety switch:

- by default a subagent worktree branches from the repository's default branch,
  not the parent session's current `HEAD`; set `worktree.baseRef` to `head` when
  in-progress local commits are required;
- untracked and gitignored files are absent unless deliberately included;
- the maestro must inspect and integrate the worktree's changes;
- worktrees with changes persist until safely integrated or cleaned up.

Never assume an isolated worker sees the main checkout's uncommitted edits.

## Phase 3: review in the main session

Treat every worker report as a claim:

1. Inspect the actual diff and every changed file.
2. Compare it with the plan, scope boundary, repository rules, security and
   privacy constraints, and existing patterns.
3. Run focused tests, lint, type checks, builds, or other verification from the
   integration checkout.
4. Check for missing tests, docs, migrations, configuration, and overwritten
   user work.
5. Decide whether the item is complete. The worker never owns "done."

## Phase 4: resume and iterate

Send precise findings to the same agent rather than starting over. Resume the
agent by its returned agent ID, or send a follow-up through the Agent interface,
so it retains its context and model selection. State the file and location,
the defect, and the required result. After each fix, re-read the diff and rerun
verification.

Allow one targeted fix round by default. For a small residual issue, fix it in
the main session. If the plan was wrong, revise it before delegating again. If a
Sonnet mechanical item exposes real judgment or repeated failure, escalate it
to Opus/high; use max only with a documented risk or failure reason. If Opus at
high effort repeatedly fails on a reasoning-heavy item, move that item's
analysis (not the bulk implementation) to a `fable` session per the escalation
triggers above.

## Phase 5: present and publish

Only the main maestro may present the result to the user or perform commits,
pushes, pull requests, deployments, and other publication. Lead with the
verified outcome, then report:

- the actual session/worker aliases and effort used;
- which work items were delegated;
- commands and results independently verified by the maestro;
- worktree integration, deviations, escalations, and remaining work.

Never pass through a worker's unverified self-report.

## When not to orchestrate

- A trivial, localized edit with no meaningful design decision.
- Pure analysis, diagnosis, planning, or review with no implementation.
- A sequential task where delegation adds no context or latency benefit.
- The user explicitly asks for direct implementation.
- A small correction found during review.

## Claude Code references

- [Model configuration](https://code.claude.com/docs/en/model-config)
- [Custom subagents](https://code.claude.com/docs/en/sub-agents)
- [Agent teams](https://code.claude.com/docs/en/agent-teams)
- [Dynamic workflows](https://code.claude.com/docs/en/workflows)
- [Worktree isolation](https://code.claude.com/docs/en/worktrees)
