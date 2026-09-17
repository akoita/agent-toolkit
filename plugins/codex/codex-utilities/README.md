# codex-utilities

General-purpose, project-agnostic workflow utilities for Codex. The bundle
ships:

- `document-software`, which scaffolds or normalizes maturity-scaled software
  documentation while preserving current truth and useful conventions;
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

The skill body is generated from the portable source under
[`plugins/portable/utilities/`](../../portable/utilities/); edit that source
and run the synchronization scripts rather than changing this package's skill
mirror.
