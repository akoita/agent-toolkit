# maestro

Capability-based orchestration for Claude Code. Keeps requirements,
architecture, review, and publication in the root session and delegates bounded
implementation to named subagents.

The full workflow is in [SKILL.md](skills/maestro/SKILL.md).

## What it ships

- the `maestro` skill;
- three custom agents in [`agents/`](agents/): an Opus implementation worker, a
  Sonnet mechanical worker, and an economical read-only explorer.

## Install

```bash
claude plugin marketplace add .
claude plugin install maestro@agent-toolkit
```

See [Installation](../../../docs/installation.md) for per-project and
agent-led installs, and [Updating](../../../docs/updating.md) for refreshing.

## Manual install

Copy or symlink the skill and copy its three named agents into the personal
Claude directories:

```bash
git clone git@github.com:akoita/agent-toolkit.git
mkdir -p ~/.claude/skills ~/.claude/agents
ln -s "$(pwd)/agent-toolkit/plugins/claude/maestro/skills/maestro" ~/.claude/skills/maestro
cp agent-toolkit/plugins/claude/maestro/agents/*.md ~/.claude/agents/
```

Use a normal copy instead of the symlink when the checkout should not remain
the live source; a copy will not follow later changes. Inspect existing
destinations before either operation and do not overwrite a customized agent
definition. Claude Code 2.1.212 or later is recommended for the subagent,
resume, and worktree behavior this skill relies on.

## Model routing

Routing is capability-based rather than fixed to model names. Use `best` or
`fable` for an unusually difficult main session, `opus` at high effort for
correctness-sensitive implementation, `sonnet` at medium or high effort for
mechanical work, and the provided Haiku explorer for economical read-only
discovery.

Aliases resolve differently by provider and organization policy, so pin
provider model mappings only when reproducibility requires it.

Dynamic workflows and Ultracode are for large repeatable fan-out; experimental
agent teams are reserved for workers that must communicate directly.

## Make it the default

Put an always-loaded instruction in `~/.claude/CLAUDE.md` for personal
defaults, or `CLAUDE.md` / `.claude/CLAUDE.md` for shared project rules. Keep
it short — the detailed procedure stays in the skill, loaded only when relevant.

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
