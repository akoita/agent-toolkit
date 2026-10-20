# ADR 0003: Check authority sources for drift on a schedule

- Status: Accepted (stages 1 and 2); stages 3 and 4 proposed
- Date: 2026-10-20
- Scope: Maintainer tooling; no shipped skill changes

## Context

Skills are written from authority sources: pinned tool releases, standards,
vendor documentation, and first-party security publications. Those sources
move. A release ships, a flag is deprecated, a page is relocated, or guidance is
superseded, and the skill keeps teaching the old answer with no signal that
anything changed.

Most of what goes stale is checkable without a model. The security-scan
toolchain alone pins seventeen releases. The cited pages can be probed for
removal or relocation. Whether a claim still matches its source does need a
reader, but only for the few sources a deterministic pass flags or an interval
marks as due.

Google's Developer Knowledge API exposes current Google developer
documentation to agents through an MCP server
(`https://developerknowledge.googleapis.com/mcp`, tools `search_documents`,
`get_document`, and `batch_get_documents`; public preview at the time of
writing). It covers Google's documentation corpus only. Most sources the skills
cite are elsewhere: GitHub releases, OWASP, CISA, MITRE, and tool vendors.

## Decision

Source checking is maintainer-side CI, never a client hook: hooks would run
on every user's machine, need network access and credentials there, and give
different answers per installation.

1. **Manifest.** `.github/authority-sources.json` registers each source with
   the canonical file that depends on it, a `publisher`, and a `verified_on`
   date. Every URL and every `# vX.Y.Z` pin in a tracked file must be
   registered; `tests/test_authority_sources.py` enforces this offline on every
   pull request. Coverage starts with the security-scan skill and the
   Google-sourced security references, and grows file by file.
2. **Deterministic checker.** `.github/scripts/check_sources.py` compares pins
   with the latest GitHub, PyPI, npm, and RubyGems releases, probes cited pages,
   and marks claims due for review after `review_after_days`. The weekly
   `source-drift` workflow keeps one tracking issue current. It never edits a
   skill.
3. **Agent review (proposed).** For flagged entries only, an agent reads the
   current source and proposes a draft pull request. It uses the Developer
   Knowledge MCP for `publisher: google` entries and ordinary fetching for the
   rest, and classifies each change as a direct source claim, an adaptation, or
   separately established guidance, as the August 2026 research note does. The
   checker's `--json` output is its input contract.
4. **Discovery (proposed).** A monthly, separate job searches the topics the
   skills cover and writes a note under `docs/research/`, without editing
   skills.

## Consequences

- Adding a URL or pin to a tracked file requires a manifest entry, so new
  sources cannot enter unregistered.
- Fetched content is untrusted. The checker accepts only version strings and
  sanitized redirect targets into the report, and the issue-writing token runs
  in a job that fetches nothing. A stage 3 agent must be confined to draft pull
  requests on a bot branch, following `security-ai`'s runtime-hardening
  guidance.
- `verified_on` dates were seeded from the dates the skills already record:
  2026-07-29 for the toolchain observations and 2026-08-03 for the Google
  research analysis.
- GitHub disables scheduled workflows after 60 days without repository
  activity; the workflow can then be re-enabled or run by `workflow_dispatch`.
