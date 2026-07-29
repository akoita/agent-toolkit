---
name: security-scan
description: >-
  Run the free deterministic security toolchain — SAST, ecosystem linters, SCA,
  secrets, IaC, DAST, fuzzing — normalize the output to one digest, and handle
  each tool's exit codes and suppression syntax. Use when the task is choosing,
  installing, invoking, or wiring scanners into pre-commit, CI, nightly, or
  release. Do not use for reasoning about a diff (use security-review), for a
  judgment-driven repository audit (use security-audit), or for supply-chain,
  threat-model, smart-contract, or AI-system questions with their own skill.
---

# Deterministic security scanning

The tools do coverage; you do judgment. This skill holds the decision procedure
and defers the per-tool detail to its references:

- `references/toolchain.md` — every tool with its install command, exact
  invocation, output format, and licence caveats.
- `references/exit-codes-and-suppression.md` — the exit-code table and the
  suppression cheat sheet.
- `references/sequencing.md` — what runs at pre-commit, pre-push, pull request,
  nightly, release, and quarterly, and the ratchet rule for adding a check.

## 1. Detect the stack

Never guess from a README. Look for the manifests and configuration files that
prove what is here, and record what you found — the tool choice has to be
defensible later.

```bash
ls -1 package.json pnpm-lock.yaml go.mod Cargo.toml pyproject.toml \
      requirements.txt Gemfile pom.xml build.gradle composer.json 2>/dev/null
git ls-files '*.tf' '*.tfvars' | head
git ls-files 'Dockerfile*' '*.yaml' '*.yml' | grep -Ei 'k8s|kube|helm|chart' | head
git ls-files '.github/workflows/*' | head
git ls-files '*.sol' | head
```

The answers decide four things: which ecosystem linter applies, whether there
is infrastructure as code, whether there are CI workflows to check, and whether
a domain skill should take over instead.

## 2. Pick the tools

Start from these defaults and deviate only for a stated reason.

| Layer | Default | Add when |
| --- | --- | --- |
| SAST | `opengrep` | — |
| Ecosystem linter | the one for the detected language | Always, when one exists — it beats generic SAST on precision |
| Dependencies | `osv-scanner` | `trivy` for the widest single-binary coverage; `syft` + `grype` when an SBOM is a deliverable |
| Secrets | `gitleaks` on the working tree | `trufflehog --results=verified` nightly and over history |
| Infrastructure | `trivy config` | `checkov` for Terraform-heavy repositories, `kube-linter` for Kubernetes, `conftest` for organization policy |
| Deployed target | nothing | OWASP ZAP Automation Framework, `nuclei`, or `schemathesis` when a running instance exists |
| Parsers | nothing | Native fuzzing at parse, decode, and deserialize boundaries only |

Two exclusions are deliberate and are not oversights. **CodeQL is excluded by
licence**: its free tier does not permit generating a database during CI/CD for
non-open-source code, so it cannot be a default in a project-agnostic skill.
**Semgrep registry rules are not redistributable** — the engine is LGPL-2.1 but
the `p/…` rule packs are licensed for internal business purposes only, which is
why `opengrep` with the MIT and Commons-Clause packs is the default instead.

Preflight before running anything:

```bash
for t in opengrep osv-scanner gitleaks trufflehog trivy syft grype checkov; do
  printf '%-12s ' "$t"; command -v "$t" >/dev/null 2>&1 \
    && "$t" --version 2>&1 | head -1 || echo 'not installed'
done
```

Report what is missing with its install command from `references/toolchain.md`
and continue with what is present. A missing tool is a coverage gap recorded in
the report, never a stop condition.

## 3. Run

Write every artifact to a directory outside the working tree and outside any
enclosing git worktree, keep it private, and do not add it to the index.

```bash
OUT="$(mktemp -d)"; chmod 700 "$OUT"
```

Run tools in report-only mode during an audit and let the gating decision
happen once, at the end, against the triaged set. Capture each exit code as you
go rather than chaining with `&&`, because a nonzero status usually means
"found something", not "failed":

```bash
opengrep scan -f rules/ . --sarif-output="$OUT/opengrep.sarif"; echo "opengrep=$?"
osv-scanner scan source -r ./ --format sarif --output "$OUT/osv.sarif"; echo "osv=$?"
gitleaks dir . --report-format sarif --report-path "$OUT/gitleaks.sarif" --redact; echo "gitleaks=$?"
```

`references/exit-codes-and-suppression.md` has the full table. Read it before
writing any gating logic; a naive `if [ $? -ne 0 ]` misreports at least four of
these tools.

## 4. Normalize

Multi-tool output is unreadable until it is collapsed into one view.

```bash
pip install sarif-tools
sarif summary "$OUT"          # counts by severity and rule across every file
sarif csv "$OUT" --output "$OUT/all.csv"
sarif html "$OUT" --output "$OUT/all.html"
sarif diff "$OUT/base" "$OUT/head"   # what this change introduced
```

`sarif summary` is the digest to read first and `sarif diff` is what turns a
full-tree scan into a pull-request signal. Tools with no SARIF output —
`trufflehog`, `schemathesis` — are summarized separately and their counts added
to the coverage table by hand.

SARIF 2.1.0 is the only version these tools emit, and it has limits worth
knowing before a large run: 10 MB gzipped per file, 20 runs per file, 25,000
results per run of which only the top 5,000 by severity are retained, and 1,000
locations per result. A repository that exceeds them silently loses results, so
split by tool rather than concatenating everything into one file.

GitHub code scanning upload is free for public repositories only; private
repositories need a paid Code Security licence. A project-agnostic pipeline
therefore falls back to workflow artifacts, a job summary, or
`reviewdog -f=sarif -reporter=github-pr-review -filter-mode=added`.

## 5. Triage

Scanner output is a list of leads. Promote a lead to a finding only with a
`file:line` and a written attack path, deduplicate by `(file, line, CWE)`
across tools keeping the highest severity instance, and rank anything with a
CVE by exploitation evidence rather than by CVSS alone:

```bash
curl -fsSL https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
curl -fsSL "https://api.first.org/data/v1/epss?cve=CVE-2021-44228"
```

In the CISA KEV catalog is P0. Otherwise EPSS ≥ 0.1 with CVSS ≥ 7 is P1, CVSS
≥ 9 alone is P2, and everything else is backlog.

Suppress in preference order: tune the rule, then allowlist the path, then
baseline, and only then an inline suppression with a mandatory justification
string. Keep the blocking set small and near-zero false positive — secrets,
hardcoded credentials, unsafe deserialization — because a gate above roughly a
20 to 30 percent false-positive rate gets routed around and takes the true
positives with it. Never gate on an unfixable transitive vulnerability.

## Doctrine

This skill is self-contained; `security-audit` holds the long form.

```text
Severity is impact and reachability only: Critical when an unauthenticated
attacker compromises the system or its data outright; High for privilege
escalation, cross-tenant access, or sensitive-data exposure behind a
precondition the attacker normally holds; Medium for real impact behind a
meaningful precondition, or a missing control one failure away from
exploitable; Low for limited impact or a privilege the actor already has;
Informational for hardening with no demonstrated impact.

Confidence is reported separately and never averaged in: High when the path
was read end to end with no mitigation found, Medium when one hop is inferred
from framework behavior, Low for a pattern match or a path that leaves this
repository.

Every finding carries a stable id, title, severity, confidence, CWE,
file:line locations, preconditions, a written attack path, impact, a quoted
code excerpt as evidence, and a specific recommendation. With no demonstrated
path from attacker-controlled input to impact, tag it `theoretical — no proof`
and cap it at Medium.

Report as: executive summary; scope and what was NOT covered; findings by
severity; tool coverage table with versions and exit codes; assumptions; open
questions.

Scan artifacts contain source and exploit steps. Write them outside the
working tree, keep the directory private, and never attach them to a pull
request by default.
```
