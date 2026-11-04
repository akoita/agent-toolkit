# codex-utilities

General-purpose, project-agnostic workflow utilities for Codex. The bundle
ships:

- `document-software`, which scaffolds or normalizes maturity-scaled software
  documentation while preserving current truth and useful conventions, holds
  the shared writing guide, and installs its policy in each project's
  `AGENTS.md`;
- `plan-milestone`, which produces dependency-aware, capacity-coherent
  milestone proposals and keeps tracker writes behind explicit approval.

Future additions must remain broadly reusable rather than becoming specialized
orchestration, security, or setup capabilities.

## Install

```bash
codex plugin marketplace add .
codex plugin add codex-utilities@agent-toolkit
```

For an individual skill installation without the plugin:

```bash
npx skills add akoita/agent-toolkit --skill document-software -g -a codex
npx skills add akoita/agent-toolkit --skill plan-milestone -g -a codex
```

## Share the writing policy across projects

`document-software` carries one canonical "Writing documentation" section for
`AGENTS.md`. Install or refresh it in a project from the skill directory:

```bash
python3 scripts/install_policy.py /path/to/project --check
python3 scripts/install_policy.py /path/to/project --write
```

The first command reports whether the project is out of date; the second
updates the text between its markers in `AGENTS.md` and enables
`utilities@agent-toolkit` in `.claude/settings.json`. Agents using the skill
run the same check before other documentation work. To find a project's
densest pages, run `python3 scripts/docs_density.py /path/to/project`.

The skill body is generated from the portable source under
[`plugins/portable/utilities/`](../../portable/utilities/); edit that source
and run the synchronization scripts rather than changing this package's skill
mirror.
