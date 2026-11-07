---
name: project-baseline
description: >-
  Audit a new or existing repository against the Agent Toolkit practice
  catalog (agent instructions, toolkit plugins, documentation, feature
  catalog, engineering guides, docs checks) and propose the changes worth
  adopting, each delegated to the skill that owns it. Use when asked to apply
  good practices to a project, bootstrap a new repository, check a repository
  for drift, or record which practices a project adopts or declines. Read-only
  until the person approves a specific change.
---

# Apply the project baseline

Bring a repository up to the shared practices without overwriting what its
people wrote. This skill owns the list of practices and the audit; each
practice's content stays in the skill named in its `owner` field.

## Safety contract

1. Start read-only. The audit script never writes. Do not create a branch,
   edit a file, or touch the tracker until the person approves a change.
2. Treat existing files as the project's own. Preserve text outside managed
   markers, report conflicts, and never replace a hand-written section
   without showing the diff first.
3. Never print secrets or read credential files, even when a practice
   concerns configuration.
4. Keep project-specific facts out of this toolkit. Write them only in the
   project.

## Audit

From this skill's directory, run:

```bash
python3 scripts/audit.py /path/to/project
```

It prints one row per practice: status, the evidence it used, and the fix.
Statuses:

| Status | Meaning |
| --- | --- |
| `present` | The practice is in place. |
| `partial` | Started, with the gap named in the evidence. |
| `missing` | Applies, and nothing is in place. |
| `review` | Applies, but needs judgment the script cannot make. |
| `declined` | The project chose not to adopt it; the reason is recorded. |
| `not-applicable` | The repository does not look like it needs it. |

Then read [references/practices.md](references/practices.md) for every row
that is not `present`, `declined` or `not-applicable`. Confirm the script's
evidence against the repository, and resolve each `review` row yourself.
A wrong `not-applicable` is fixed by recording `adopt`, not by guessing.

## Propose

Present the audit as one table and a short plan grouped by practice group,
smallest useful change first. For each proposed change name the owning
skill, the files it touches, and whether the text is managed (between
`<!-- agent-toolkit:... -->` markers) or hand-written. Ask which changes to
make and which to decline.

- **New repository:** choose the documentation profile with
  `document-software` (compact, standard or operational), then propose the
  scaffold and the agent files together.
- **Existing repository:** propose the smallest changes that close gaps.
  Use `document-software`'s migration guidance before moving any page.

## Apply after approval

Make each approved group of changes on its own branch and pull request,
following the project's delivery rules.

- **Mechanical practices** (`claude-imports-agents`, `toolkit-plugins`):
  run `python3 scripts/apply.py <project> --practice <id>`, show the diff
  it prints, and re-run with `--write` after approval. It keeps existing
  text and settings.
- **Other practices:** use the owning skill's installer or procedure, for
  example `document-software`'s `install_policy.py` for the writing policy,
  and write content such as `AGENTS.md` sections from repository evidence.

Re-run the audit after writing to confirm each row is `present`. Run the project's own
quality gate before opening the pull request.

## Record decisions

Keep the person's choices in `.agent-toolkit/baseline.json` in the project,
committed with the change that applies them:

```json
{
  "schema_version": 1,
  "decisions": {
    "feature-catalog": {"decision": "adopt", "date": "2026-01-15"},
    "docs-check-ci": {
      "decision": "decline",
      "reason": "Links are checked by the docs site build.",
      "date": "2026-01-15"
    }
  }
}
```

Write decisions with `scripts/apply.py`, previewing first:

```bash
python3 scripts/apply.py /path/to/project --adopt feature-catalog
python3 scripts/apply.py /path/to/project --decline docs-check-ci --reason "Checked by the docs site build."
```

`decline` needs a reason and stops the practice being proposed again.
`adopt` makes a practice apply even when the audit thinks it does not. Ask
before changing a recorded decision.

## Keep it current

Once a project has adopted its baseline, a CI job that checks out
`akoita/agent-toolkit` at a pinned tag can run
`python3 <toolkit>/skills/project-baseline/scripts/audit.py . --check`. It
exits 1 when an applicable practice is missing or partial. Re-run the audit after updating Agent
Toolkit: a new release may add practices.

Report the statuses before and after, the changes made, and any row you
could not verify.
