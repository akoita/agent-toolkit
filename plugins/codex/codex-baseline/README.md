# codex-baseline

Audit a new or existing repository against the Agent Toolkit practice
catalog for Codex, and adopt the practices that apply. The bundle ships
`project-baseline`, which:

- checks agent instructions, toolkit plugins, documentation, the feature
  catalog, engineering guides and docs checks, reading the repository only;
- proposes the changes worth making, each delegated to the skill that owns
  the practice, such as `document-software`;
- records which practices the project adopts or declines in
  `.agent-toolkit/baseline.json`, so declined ones are not proposed again.

## Install

```bash
codex plugin marketplace add .ncodex plugin add codex-baseline@agent-toolkit
```

For an individual skill installation without the plugin:

```bash
npx skills add akoita/agent-toolkit --skill project-baseline -g -a codex
```

Install `codex-utilities` too: most practices are applied through its
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

## Apply mechanical practices

```bash
python3 scripts/apply.py /path/to/project --practice toolkit-plugins
python3 scripts/apply.py /path/to/project --practice toolkit-plugins --write
```

The first prints the diff; the second writes it. `apply.py` handles
`claude-imports-agents` and `toolkit-plugins`, and records decisions with
`--adopt <id>` or `--decline <id> --reason "<why>"` in
`.agent-toolkit/baseline.json`. Other practices go through their owning
skill.

The skill body is generated from the portable source under
[`plugins/portable/baseline/`](../../portable/baseline/); edit that source
and run the synchronization scripts rather than changing this package's skill
mirror.
