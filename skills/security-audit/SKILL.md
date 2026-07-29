---
name: security-audit
description: >-
  Run a repository-wide security audit and own the shared doctrine — severity,
  evidence, triage, suppression, reporting — that the other security skills
  restate. Use for a deep audit of a whole codebase or a large subsystem, for
  turning scanner output into evidence-backed findings, and for producing a
  security report. Do not use for a pull-request diff (use security-review),
  for running the toolchain alone (use security-scan), or for dependency, CI,
  threat-model, smart-contract, or AI-system questions that have their own
  skill.
---

# Repository security audit

An audit is expensive and unbounded by nature, so it is run in a fixed order
that spends the budget on judgment rather than on breadth. Discovery finds
candidates, a second pass assumes discovery over-reported and demands proof,
triage decides what survives, and the report says as much about what was not
covered as about what was.

The doctrine in `references/severity-and-reporting.md` and
`references/triage-and-false-positives.md` is the contract for this skill and
for its siblings. Read both before writing a single finding.

## 1. Scope and budget

Decide and write down three things before reading any code.

**In scope.** Name the paths, the branch, and the commit. Prefer a subsystem
with a clear trust boundary over "the repository" — an audit that covers a
service and its data layer thoroughly is worth more than one that skims
everything.

**Explicitly excluded.** Vendored dependencies, generated code, test fixtures,
and documentation are the usual exclusions. Every exclusion is written into the
report, because absence of findings in an unexamined directory is not evidence
of safety.

**The cost ceiling.** Fix a number before starting, in whatever unit the
external tools bill in, and stop when it is reached rather than when the work
feels done. A partially covered audit that says so is honest; one that quietly
ran out of budget mid-pass is not. Where a tool has a cost flag, set it
explicitly rather than trusting its default.

State all three in the opening of the report.

## 2. Tool preflight

Detect, never assume. Run the version command for each tool the audit intends
to use, record what answered, and print the exact install command for what did
not.

```bash
for t in opengrep osv-scanner gitleaks trivy syft grype; do
  printf '%-14s ' "$t"; command -v "$t" >/dev/null 2>&1 \
    && "$t" --version 2>&1 | head -1 || echo 'not installed'
done
```

A missing tool is a coverage gap, not a stop condition. Continue with
agent-native reasoning over the code, and record the gap in the tool coverage
table so the reader knows which classes went unscanned. The `security-scan`
skill holds the install commands and the exact invocations; this skill only
needs to know what is present.

## 3. The two-pass shape

Adapted from the CodeCrucible blueprint (https://github.com/block/codecrucible).
The value is in the second pass being adversarial towards the first.

### Pass one: open-ended discovery

Read as much of the in-scope repository as fits, without a checklist, looking
for anything that smells wrong. The goal is recall, and over-reporting here is
expected and acceptable — it is the input to pass two, not the report.

Chunk as late and as semantically as possible:

- keep files whole; a function split across two chunks is a function neither
  chunk can reason about;
- cluster files that import each other, so a chunk contains a data flow rather
  than a directory listing;
- duplicate small, high-priority files — authentication helpers, middleware,
  configuration loaders, permission tables — into every chunk that touches
  them, because their absence is what makes a reviewer guess;
- merge undersized chunks rather than shipping many thin ones.

Prompt complexity does not correlate with output quality. Every section added
to a discovery prompt costs tokens on every chunk, so a section earns its place
by changing the output or it comes out.

### Pass two: CWE-specific audit

Re-examine each candidate assuming the first pass over-reported, because it
did. Ask a closed, CWE-specific question rather than an open one — "is this
CWE-89, given this trace" rather than "is this a vulnerability" — and require
two things before a candidate survives:

- **proof of reachability**: a written path from an attacker-controlled input
  to the sink, with each hop at a `file:line`;
- **absence of a mitigation**: an explicit statement that the guard a reviewer
  would expect — a middleware, a framework-level check, a database policy, a
  type that makes the unsafe state unrepresentable — is not there, backed by
  where you looked for it.

A candidate that fails either test is dropped, or kept with the
`theoretical — no proof` tag and capped at Medium. Record the drop reason; the
dropped set is evidence that triage happened.

The reasoning behind this split, and the measurements that support it, are in
`references/llm-assisted-review.md`.

## 4. Deduplicate

Collapse survivors by `(location, CWE)`, keeping the highest severity instance
and merging the evidence from every tool and pass that reported it. Record
which sources agreed: independent agreement is a real confidence signal.

A repeated idiom that fails at fifty call sites is one finding with fifty
locations, not fifty findings.

## 5. Triage

Apply `references/triage-and-false-positives.md` in full: promotion rules,
KEV → EPSS → CVSS prioritization for anything with a CVE, the suppression
preference order, and the anti-noise guardrails. Do not skip the guardrails —
absent TLS in a local development context, a casual HSTS recommendation, and a
sequential identifier reported without the missing authorization check are the
three findings most likely to get an entire report dismissed.

## 6. Ownership as a risk signal

Who maintains a file predicts how quickly a defect in it is noticed, so use
history to rank attention. This is an input to prioritization and never a
finding on its own.

```bash
git log --since=18.months --format='%an' -- path/to/sensitive \
  | sort | uniq -c | sort -rn
git log -1 --format='%ar %an' -- path/to/sensitive
```

Two signals matter. A **bus factor of one** over a security-sensitive path —
authentication, cryptography, permission checks, deployment configuration —
means a single reviewer's blind spot is the whole review. **Orphaned sensitive
code**, untouched for a long time by anyone still active, has had no adversarial
reading in as long.

Use these to decide where the deep pass goes when the budget will not cover
everything, and report them in the assumptions section as context. Never write
"this file has one owner" as a finding.

## 7. Report

Write the report exactly as `references/severity-and-reporting.md` specifies:
executive summary, scope and what was not covered, findings by severity, the
tool coverage table with versions and exit codes, assumptions, open questions.

Write artifacts outside the working tree, keep the directory private, and do
not attach them to a pull request. They contain source excerpts and exploit
steps.

## 8. Routing

This skill is the deep pass and the doctrine. Hand off when the question has a
better-shaped home:

| Hand off to | When |
| --- | --- |
| `security-scan` | The task is running the deterministic toolchain, normalizing SARIF, handling exit codes, or setting up the pre-commit through release cadence. |
| `security-review` | The unit of work is a diff or a pull request rather than a repository. |
| `security-supply-chain` | The question is about dependencies, CI/CD workflows, SBOM, signing, or provenance. |
| `security-threat-model` | There is no code question yet — the work is trust boundaries, assets, attacker capabilities, and abuse paths. |
| `security-smart-contracts` | The target is Solidity or another on-chain contract, where the vulnerability classes and the severity rubric differ. |
| `security-ai` | The target is an LLM application, an agent, an MCP server, or a model supply chain. |

A repository audit routinely calls two or three of these. Run them, fold their
results into the same deduplication and triage, and attribute each finding to
the pass that produced it.

## Optional external LLM scanners

Two published tools do LLM-driven scanning. Drive them when the user has them;
never depend on either, and never let their absence stop an audit. Both ship
their own agent skills, so wrap them rather than duplicating their guidance.

### OpenAI Codex Security CLI

Apache-2.0, TypeScript, distributed as the npm package
`@openai/codex-security` (https://github.com/openai/codex-security). Requires
Node.js 22 or later and Python 3.10 or later.

```bash
npm install @openai/codex-security
npx codex-security login                    # or --device-auth when headless
printenv OPENAI_API_KEY | npx codex-security login --with-api-key
```

```bash
SCAN_ROOT="$(mktemp -d)"
npx codex-security scan . \
  --diff origin/main \
  --output-dir "$SCAN_ROOT/results" \
  --json \
  --fail-on-severity high > "$SCAN_ROOT/findings.json"
```

Scan targeting is `--path P` (repeatable), `--diff BASE` with an optional
`--head SHA`, or `--working-tree` with an optional `--base` — the three are
mutually exclusive. `--mode deep` raises effort on repository and path targets.
`--knowledge-base PATH` (repeatable) feeds threat models and architecture
documents in. `--max-cost USD` stops the scan when the estimated cost exceeds
the amount, `--dry-run` validates the inputs without starting a scan,
`--model` and `--auth {auto,chatgpt,api-key}` select the model and credential.

Subcommands: `scan`, `scans list|show|rerun|match|compare`,
`findings false-positive OCCURRENCE_ID --reason "..."`,
`export SCAN_DIR --export-format {sarif,csv,json} --output FILE`, `validate`
and `patch` (each takes a findings file plus a description of the issue),
`install-hook`, `bulk-scan`, `info`, `login`, `logout`. An MCP server mode is
available via `--mcp`; scans stay CLI-only there because the transport cannot
cancel a running command.

Five operational details matter more than the flag list:

- **Exit codes**: 0 for a completed report-only scan or a passing policy, 1 for
  a completed scan with a finding at or above `--fail-on-severity`, 2 for
  invalid input, incomplete coverage, *or* a runtime error, 130 for
  interruption, 143 for termination. Because 2 conflates coverage with failure,
  read `coverage.json` in the scan directory and check its `completeness`
  field (`complete`, `partial`, or `unknown`) rather than trusting the status.
- **The output directory must be outside** the scanned directory and any
  enclosing git worktree. On macOS and Linux an existing one must be private to
  the current user (`chmod 700`), and it must be empty unless
  `--archive-existing` is passed, which moves the previous results aside.
- **`findings.json` is the source of truth.** SARIF is a lossy secondary export
  written to `<scan-dir>/exports/results.sarif`; add `--source-root` to the
  export for source-line fingerprints.
- **Pass `--auth` explicitly or use `--json`.** An interactive scan prompts for
  a credential when both a ChatGPT sign-in and an API key are present.
- Findings carry stable occurrence identities across runs, which is what makes
  `scans compare` and `findings false-positive` worth using: a false positive
  marked once with a reason stays marked.

### CodeCrucible

Apache-2.0, Go, from Block (https://github.com/block/codecrucible). Prototype
maturity: there are no releases and no binary distribution, so it is built from
source.

```bash
git clone https://github.com/block/codecrucible && cd codecrucible
make build            # or: make docker-build
./codecrucible scan /path/to/repo --output results.sarif --max-cost 10
```

Useful flags: `--dry-run` to preview scope and cost, `--max-cost` (a float in
dollars, **defaulting to 25** — always set it explicitly), `--paths` and
`--exclude` to scope, `--fail-on-severity` as a float from 0 to 10,
`--prompts-dir` to select one of the 13 prompt sets shipped under `prompts/`,
`--skip-audit` to drop the second pass, `--concurrency` for parallel chunks,
and `--phase-output-dir` to place per-phase artifacts. Providers are
`anthropic`, `openai`, `google`, `ollama`, `openai-compat`, and `databricks`,
auto-detected from environment variables; with the Anthropic provider it falls
back to Claude Code CLI authentication when no API key is set.

Three traps:

- **`--dry-run` estimates input tokens only.** Real scans also bill completion
  tokens from the analysis, repair, and audit phases, so the actual cost runs
  higher than the estimate. Do not size the budget from a dry run alone.
- **Exit codes are inverted relative to Codex Security**: 0 clean, 1 error, 2
  findings at or above `--fail-on-severity`.
- **A failed run still emits schema-valid SARIF.** Always check
  `runs[0].invocations[0].executionSuccessful` before reading the results, or a
  broken scan reads as a clean repository.

```bash
jq '.runs[0].invocations[0].executionSuccessful' results.sarif
```

The prompt sets are the most reusable part of the project even when the binary
is not run: they are the concrete form of the two-pass shape this skill
describes, including language-specific and exploit-proof variants that require
a concrete exploit per finding.
