---
name: security-supply-chain
description: >-
  Harden a project's software supply chain: audit CI/CD workflows, pin actions
  to commit SHAs, control package-manager and install-script risk, enforce
  lockfiles and release cooldowns, emit an SBOM, sign artifacts and produce
  build provenance, and work through the repository checklists and regulatory
  obligations that follow (OpenSSF Scorecard, OSPS Baseline, EU CRA, NIST SSDF,
  OWASP ASVS and SAMM). Use when reviewing workflows, dependency intake,
  release pipelines, or compliance readiness. Do not use for application code
  vulnerabilities (use security-audit for a repository audit or
  security-review for a diff), for running the general scanner toolchain (use
  security-scan), or for LLM, agent, and MCP risk (use security-ai).
---

# Supply chain and build integrity

Supply chain work has a different shape from code auditing. The findings are
mostly configuration, the evidence is mostly a file and a line in a workflow or
a manifest, and the highest-value pass is almost always the cheapest one. Work
outside in: continuous integration first, then dependency intake, then what you
publish, then the checklists that a third party will hold you to.

## Finding contract

This restates the contract owned by the `security-audit` skill. Read that skill
for the long form, triage policy, and suppression rules.

Severity is `Critical`, `High`, `Medium`, `Low`, or `Informational`, and it
describes impact and reachability only. Report confidence separately — `High`
when the path was read end to end, `Medium` when a hop is inferred from
framework behavior, `Low` for a pattern match or a path that leaves this
repository — and never fold confidence into
severity to make a weak finding look serious or a strong one look tentative.

Every finding is one record with a stable id (so it survives across runs), a
title, severity, confidence, a CWE where one applies, a `file:line`,
preconditions the attacker needs, the attack path in prose, the impact if it
succeeds, the evidence that supports each step, and a recommendation naming the
exact file and change. A finding whose attack path cannot be walked end to end
carries an explicit `theoretical — no proof` tag in its title.

Every tool finding is a lead, not a finding. `zizmor`, `actionlint`,
`osv-scanner`, and Scorecard emit leads. A lead is promoted only when it has a
written attack path and a `file:line`; otherwise it is tagged theoretical or
dropped. Never claim a control exists, or does not exist, without a code
reference. Detect each tool before using it, print its install command when it
is missing, and continue with manual reading rather than aborting.

## Order of work

| Pass | Question | Reference |
| --- | --- | --- |
| 1. CI/CD | What can a pull request make the build do? | `references/ci-hardening.md` |
| 2. Intake | What runs when a dependency is installed? | `references/ci-hardening.md` |
| 3. Output | Can a consumer prove what we shipped? | `references/sbom-and-provenance.md` |
| 4. Obligations | What will an auditor or regulator ask for? | `references/standards-and-compliance.md` |

Do not start at pass 4. A repository that fails pass 1 will fail every
checklist in pass 4 for reasons the checklist describes badly.

## Pass 1: continuous integration

CI is the highest-return first pass because a compromised workflow already has
the credentials, the network, and the publishing rights that every other
control is trying to protect.

Run both of these; they overlap very little.

```bash
uvx zizmor --format sarif .github/workflows/ > zizmor.sarif
actionlint
```

`zizmor` v1.28.0 ships 40 audits. The ones that most often produce a real
attack path are `template-injection` (untrusted expression interpolated into a
`run:` block), `artipacked` (checkout leaves credentials in `.git/config`,
which a later upload step publishes as an artifact), `excessive-permissions`,
`dangerous-triggers` (`pull_request_target`), `cache-poisoning`,
`impostor-commit`, and `typosquat-uses`.

`zizmor` uses severity-graded exit codes: `0` clean, `11` informational, `12`
low, `13` medium, `14` high, `1` an error during the audit, `2` bad arguments,
`3` no inputs collected. A naive `if [ $? -ne 0 ]` gate therefore treats an
informational finding and an internal failure identically. Use
`--no-exit-codes` or `--format sarif`, both of which suppress codes 11 and
above, and decide the gate from the SARIF.

`actionlint` v1.7.12 is complementary rather than redundant: workflow schema
and expression type correctness, `needs:` graph consistency, and shellcheck
over every `run:` block.

### Pin every action to a commit SHA

In March 2025, `tj-actions/changed-files` (CVE-2025-30066) had its tags
force-moved onto a malicious commit that dumped runner process memory into
public build logs. Roughly 23,000 repositories referenced the action. The ones
that referenced it by commit SHA were unaffected, because a moved tag cannot
change what a SHA resolves to.

```bash
pinact run --check              # report unpinned actions, exit 2 on violation
pinact run                      # rewrite refs to SHAs, keeping version comments
pinact run --min-age 7          # when updating, skip releases newer than 7 days
```

`ratchet` is an equivalent alternative. Dependabot updates SHA pins and
preserves the trailing version comment, so pinning does not cost you updates.

Alongside pinning: declare least-privilege `permissions:` at both workflow and
job level, set `persist-credentials: false` on checkout unless a later step
genuinely needs the token, and never combine `pull_request_target` with a
checkout of the pull request head ref.

## Pass 2: dependency intake

Install scripts are now the dominant npm threat. The Shai-Hulud worm
(September 2025) stole credentials from `postinstall`; Shai-Hulud 2.0
(November 2025, roughly 796 packages) moved to `preinstall` so that it ran even
when the install later failed; a smaller follow-on in May 2026 affected 170+
npm packages and 2 on PyPI.

Three controls carry most of the weight:

```bash
npm ci --ignore-scripts                    # or ignore-scripts=true in .npmrc
npm audit signatures                       # registry signatures and provenance
```

Add a release cooldown. Most malicious releases are yanked within hours, so a
delay of a few days filters them without human review. npm CLI 11.10.0
(February 2026) added `min-release-age`, expressed in days, with
`min-release-age-exclude` for packages you must take immediately; Renovate has
`minimumReleaseAge`. Note that when the cooldown blocks a fix `npm audit fix`
wanted to install, npm keeps the vulnerable version, warns, and exits non-zero.

Lockfiles are a gate, not a suggestion. Use `npm ci`,
`pnpm install --frozen-lockfile`, or `uv sync --locked` in CI; a bare `install`
silently resolves new versions. For Python, generate hashes with
`uv pip compile --generate-hashes` and install with
`pip install --require-hashes`, then run `pip-audit --strict`.

PEP 740 attestations are Final and PyPI supports them, but neither pip nor uv
rejects an unsigned package today. Treat attestations as audit evidence, not as
an enforcement point.

## Pass 3: what you publish

Emit CycloneDX 1.7 as the primary SBOM format and add SPDX only on request.
`syft` produces both in one pass:

```bash
syft . -o cyclonedx-json=sbom.cdx.json -o spdx-json=sbom.spdx.json
```

Sign and attest with `cosign` v3.1.2 in keyless mode, and produce build
provenance with `actions/attest-build-provenance`. Verification without an
identity constraint is the mistake that matters — see
`references/sbom-and-provenance.md` for the exact invocations, the SLSA v1.2
build track, and how to gate on OpenSSF Scorecard output.

## Pass 4: checklists and obligations

`references/standards-and-compliance.md` covers the OSPS Baseline as the
drop-in repository checklist, and states the EU Cyber Resilience Act, NIST
SSDF, OWASP ASVS and SAMM, CIS benchmarks, PCI DSS, and SOC 2 as engineering
obligations. It is engineering guidance, not legal advice.

## When a tool is missing

Print the install command and continue by reading the files.

| Tool | Install |
| --- | --- |
| `zizmor` | `uv tool install zizmor` (or `uvx zizmor`) |
| `actionlint` | `go install github.com/rhysd/actionlint/cmd/actionlint@latest` |
| `pinact` | `go install github.com/suzuki-shunsuke/pinact/v4/cmd/pinact@latest` |
| `syft` | `brew install syft` or the upstream install script |
| `cosign` | `brew install cosign` or the release binary |
| `scorecard` | `brew install scorecard` or the release binary |
| `pip-audit` | `uv tool install pip-audit` |

Reading `.github/workflows/` for `${{ github.event.* }}` inside `run:` blocks,
for missing `permissions:`, and for tag-shaped `uses:` refs recovers most of
pass 1 with no tools at all.

## Report

Group findings by pass, not by tool. For each, give the record described in the
finding contract above. Separate what is already mitigated in the repository,
with the `file:line` that proves it, from what you are recommending. State
which tools were unavailable and what that leaves unverified.

## References

- `references/ci-hardening.md` — workflow audits, pinning, install scripts,
  lockfiles, and cooldowns in detail.
- `references/sbom-and-provenance.md` — SBOM formats, `cosign`, SLSA v1.2,
  Scorecard, and OSPS Baseline.
- `references/standards-and-compliance.md` — CRA, SSDF, ASVS, SAMM, CIS,
  PCI DSS, SOC 2.
