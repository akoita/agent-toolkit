# Making Maestro the default

Use a short, always-loaded agent instruction to choose when Maestro should run,
and keep the detailed orchestration procedure in the skill. This makes the
default predictable without loading the full workflow into every task.

## Codex

Put personal defaults in `~/.codex/AGENTS.md` and project-specific rules in the
repository's `AGENTS.md`:

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

The instruction expresses the desired routing policy, but it cannot change the
model of an already-running root task. Confirm the configured root and custom
agent models before claiming which model or effort performed the work.

## Claude Code

Put personal defaults in `~/.claude/CLAUDE.md` and shared project instructions
in `CLAUDE.md` or `.claude/CLAUDE.md`:

```markdown
## Orchestration policy

- Use `/maestro` for non-trivial implementation work such as features, bug
  fixes, refactors, tests, configuration, or infrastructure.
- Keep analysis, design decisions, planning, review, and publication in the
  root session; delegate bounded implementation work as directed by the
  installed `maestro` skill.
- Use a few subagents for independent bounded work, agent teams only when
  workers must communicate, and dynamic workflows for large repeatable fan-out.
- Prefer documented model aliases and capability-based effort: `opus` at high
  effort for correctness-sensitive work and `sonnet` at medium or high effort
  for mechanical work.
- Do not orchestrate trivial edits, pure analysis or review, or tasks where the
  user explicitly requests direct implementation.
- Follow the installed `maestro` skill for worker selection, verification, and
  retry behavior.
```

## Where instructions belong

Keep repository architecture, commands, security constraints, and coding
standards in `AGENTS.md` or `CLAUDE.md`. Keep multi-phase procedures, worker
contracts, fallback runners, and result formats in `SKILL.md`, where they are
loaded only when relevant. If both platforms are used, keep the two base files
as thin platform adapters rather than duplicating the full skill in each one.
