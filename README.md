# claude-skills

Personal, project-agnostic [Agent Skills](https://code.claude.com/docs/en/skills)
for Claude Code, kept in one place for reuse across machines and projects.

## Skills

| Skill | What it does |
| --- | --- |
| [maestro](skills/maestro/SKILL.md) | Orchestrator pattern for dev tasks: a premium session model (Fable/Mythos, Opus) plans and reviews; cheaper workers (Claude Opus/Sonnet via the Agent tool, or GPT via Codex CLI, Gemini CLI) implement. The maestro verifies every result itself and iterates with the same worker until the work matches the plan. |

## Install

**Globally (all projects on a machine)** — copy or symlink into the personal
skills directory:

```bash
git clone git@github.com:akoita/claude-skills.git
ln -s "$(pwd)/claude-skills/skills/maestro" ~/.claude/skills/maestro
# or: cp -r claude-skills/skills/maestro ~/.claude/skills/
```

A symlink keeps the installed skill in sync with `git pull`; a copy freezes it.

**Per project (checked in, shared with the team)** — copy into the repo:

```bash
cp -r claude-skills/skills/maestro <repo>/.claude/skills/
```

## Conventions

- One directory per skill under `skills/`, with the skill's `SKILL.md`
  (plus optional `references/`, `scripts/`, `assets/`).
- Skills here must be project-agnostic: no repo-specific paths, secrets, or
  company context. Project-specific skills belong in that project's
  `.claude/skills/`.
