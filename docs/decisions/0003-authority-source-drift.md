# ADR 0003: Check authority sources for drift on a schedule

- Status: Accepted (stages 1 to 3); stage 4 proposed
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
   `source-drift` workflow keeps one tracking issue current. The checker itself
   never edits a skill.
3. **Agent review (accepted).** When the checker exits 1, the `source-drift`
   workflow runs an agent for the flagged entries only. It reads each current
   source and proposes the skill and manifest updates as a draft pull request.
   It uses ordinary fetching for every source; the Developer Knowledge MCP for
   `publisher: google` entries remains an option once it leaves preview. It
   classifies each change as a direct source claim, an adaptation, or
   separately established guidance, as the August 2026 research note does. The
   checker's `--json` output is its input contract, and
   `.github/prompts/source-drift-review.md` holds its instructions. The agent
   never shares a job with a write token:
   - `check` uploads the report and the issue-writing `report` job is
     unchanged.
   - `propose` runs the agent with a read-only token and a fixed tool list
     that cannot execute repository code, because the API key is in the
     agent's environment. After the agent finishes, the job restores
     `.github/` code and `tests/`, regenerates mirrors and adapters without
     the key, and uploads a patch. It never pushes.
   - `verify` applies the patch, enforces the path allowlist, and runs the
     offline checks (`sync_skills.py --check`, `sync_plugin_adapters.py
     --check`, `check_sources.py --validate-only`, and the test suite). It is
     separate from `publish` because tests execute scripts that ship inside the
     patched paths.
   - `publish` holds `contents: write` and `pull-requests: write`. It re-checks
     the allowlist, applies the patch, and pushes `bot/source-drift-<date>`. It
     opens a draft pull request against `main` whose body is the agent summary
     plus a fixed warning footer. It runs no agent and no patched code.

   The allowlist accepts only `plugins/**`, `skills/**`,
   `.claude-plugin/marketplace.json`, `.agents/plugins/marketplace.json`,
   `.github/authority-sources.json`, and `docs/research/**`. Anything else, a
   symlink, or a submodule fails the run, so the agent cannot change workflows,
   scripts, or tests. A failed verification fails the workflow and opens no
   pull request.

   Two repository settings govern it. The `ANTHROPIC_API_KEY` repository secret
   is required; without it the `propose` job skips cleanly and the weekly
   issue is the only output. Opening the pull request also needs "Allow GitHub
   Actions to create and approve pull requests" under Settings, Actions. The
   job also skips while any open pull request has a head branch starting with
   `bot/source-drift-`, so at most one proposal is open at a time. Pull requests
   opened with `GITHUB_TOKEN` do not trigger other workflows, so `tests` and
   `version-gate` do not run by themselves; a maintainer closes and reopens the
   pull request, or pushes to the branch, to run them before merging.
4. **Discovery (proposed).** A monthly run searches the topics the skills cover
   and writes a note under `docs/research/` through a draft pull request,
   without editing skills. It will run as a scheduled Claude Code cloud
   routine on the maintainer's side, outside repository CI, so it needs no
   repository secret or workflow. This stage stays proposed until that routine
   exists.

## Consequences

- Adding a URL or pin to a tracked file requires a manifest entry, so new
  sources cannot enter unregistered.
- Fetched content is untrusted. The checker accepts only version strings and
  sanitized redirect targets into the report, and the issue-writing token runs
  in a job that fetches nothing. The stage 3 agent is confined to a read-only
  job and a path-allowlisted patch that becomes a draft pull request on a bot
  branch, following `security-ai`'s runtime-hardening guidance. Its prompt
  treats fetched content as data, but prompt injection is not eliminated: the
  allowlist, the offline verification, and human review of every draft are the
  controls that remain.
- `verified_on` dates were seeded from the dates the skills already record:
  2026-07-29 for the toolchain observations and 2026-08-03 for the Google
  research analysis.
- GitHub disables scheduled workflows after 60 days without repository
  activity; the workflow can then be re-enabled or run by `workflow_dispatch`.
