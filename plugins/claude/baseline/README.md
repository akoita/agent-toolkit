# baseline

Audit a new or existing repository against the Agent Toolkit practice
catalog for Claude Code, and adopt the practices that apply. The bundle ships
`project-baseline`, which:

- checks agent instructions, toolkit plugins, documentation, the feature
  catalog, engineering guides and docs checks, reading the repository only;
- proposes the changes worth making, each delegated to the skill that owns
  the practice, such as `document-software`;
- records which practices the project adopts or declines in
  `.agent-toolkit/baseline.json`, so declined ones are not proposed again.

## Install

```bash
claude plugin marketplace add .nclaude plugin install baseline@agent-toolkit
```

For an individual skill installation without the plugin:

```bash
npx skills add akoita/agent-toolkit --skill project-baseline -g -a claude-code
```

Install `utilities` too: most practices are applied through its
`document-software` skill.

## Audit a project

From the skill directory:

```bash
python3 scripts/audit.py /path/to/project
python3 scripts/audit.py /path/to/project --check
```

The first prints one row per practice with its status, evidence and fix. The
second exits 1 when an applicable practice is missing or partial; run it in
CI to catch drift. `references/practices.md` explains each practice.

The skill body is generated from the portable source under
[`plugins/portable/baseline/`](../../portable/baseline/); edit that source
and run the synchronization scripts rather than changing this package's skill
mirror.
