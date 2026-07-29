# The toolchain

Every tool here is free software or a genuinely free tier and runs from a
command line with no account. Version numbers are the latest releases observed
on 2026-07-29; check for a newer one rather than pinning to these.

## SAST

### opengrep — the default

LGPL-2.1, a self-contained binary, cross-function taint analysis, and no login.

```bash
curl -fsSL https://raw.githubusercontent.com/opengrep/opengrep/main/install.sh | bash
opengrep scan -f rules/ . --sarif-output=out.sarif
```

Two rule packs are redistributable, which is why this is the default rather
than Semgrep: `opengrep/opengrep-rules` (Commons Clause plus LGPL-2.1) and
`AikidoSec/opengrep-rules` (MIT). Clone the pack you want into `rules/` and
point `-f` at it.

Output is SARIF 2.1.0.

### Semgrep CE — fallback only

Use it when the user already has it and prefers it. Do not introduce it.

```bash
pip install semgrep
semgrep scan --config p/default --sarif -o out.sarif --error \
  --baseline-commit "$(git merge-base origin/main HEAD)"
```

Three caveats. The engine is LGPL-2.1 but the **registry rules are licensed for
internal business purposes only and cannot be redistributed**, so they cannot
be vendored into a toolkit. Community Edition analysis is intra-file only, with
no cross-function taint. And `--config auto` logs in to the registry, which is
usually not what a scripted scan wants.

`--error` is required for a nonzero exit on findings; without it Semgrep exits
0 regardless. `--baseline-commit` restricts results to what the branch
introduced and is the flag that makes it usable in pull-request CI.

### CodeQL — excluded by licence

The free licence does not permit generating a database during CI/CD for
non-open-source code. It cannot be a default in a project-agnostic skill. Use
it only where the repository is public and the maintainer has decided to.

## Ecosystem linters

These have better precision than generic SAST because they understand the
language's own idioms. Run one whenever the ecosystem is present.

### Python

```bash
pip install 'bandit[sarif]'          # 1.9.4
bandit -r . -f sarif -o bandit.sarif
```

Suppress a single line with `# nosec B602`, naming the test identifier.

`ruff` with `select = ["S"]` in `pyproject.toml` enables the flake8-bandit rule
set and runs fast enough for pre-commit. Use it as the quick layer and Bandit
as the thorough one; they overlap deliberately.

### Go

```bash
gosec -fmt sarif -out gosec.sarif ./...     # v2.28.0
```

Suppress with `// #nosec G402 -- reason`. The reason after `--` is not optional
in review even though the tool accepts its absence.

### Ruby

```bash
brakeman -f sarif -o brakeman.sarif          # v8.0.5
```

Rails-aware, and considerably more accurate on a Rails application than any
generic engine.

### JavaScript and TypeScript

```bash
npm install --save-dev eslint-plugin-security   # v4 (4.0.1 observed)
```

It ships roughly fourteen rules. Treat it as a floor, not a scanner, and layer
`microsoft/eslint-plugin-sdl` on top for a wider set. Neither replaces
`opengrep` for this ecosystem.

### Rust

```bash
cargo install cargo-audit cargo-deny
cargo audit                       # advisories against RustSec
cargo clippy -- -D warnings       # correctness and soundness lints
cargo deny check                  # licences, bans, advisories, sources
```

## Software composition analysis

### osv-scanner — the default

```bash
osv-scanner scan source -r ./ --format sarif --output osv.sarif   # v2.4.0
```

Exit codes are 0 (packages found, no vulnerabilities), 1 (vulnerabilities
found), 127 (general error), and **128 (no packages found)** — that last one
usually means the scan format did not pick up any manifest, and treating it as
success hides a scan that did nothing.

There is no severity-threshold flag, so filter the JSON output when a threshold
is needed. For an air-gapped or rate-limited environment:

```bash
osv-scanner scan source -r ./ --offline-vulnerabilities --download-offline-databases
```

### trivy — widest single-binary coverage

```bash
trivy fs --scanners vuln,secret,misconfig --severity HIGH,CRITICAL \
  --ignore-unfixed --exit-code 1 --format sarif -o trivy.sarif .   # v0.72.0
```

One binary covers dependencies, secrets, and misconfiguration. Note that Trivy
exits 0 on findings unless `--exit-code` is passed, and `--ignore-unfixed`
keeps unfixable transitive advisories out of a gate.

Its vulnerability database is distributed as an OCI artifact from `ghcr.io`,
and `TOOMANYREQUESTS` is a common CI failure. Cache `~/.cache/trivy` between
runs, or use `--db-repository` to point at a mirror, or `--skip-db-update` when
a recent database is already present.

### syft plus grype — SBOM first

```bash
syft . -o cyclonedx-json=sbom.cdx.json                       # v1.50.0
grype sbom:./sbom.cdx.json -o sarif --fail-on high            # v0.116.1
```

Use this split when the SBOM is a deliverable in its own right — for a release,
an attestation, or a customer. **`--fail-on` exits 2, not 1**, which is the
single most common mistake in a Grype gate.

### OWASP dependency-check

Not recommended for new work. NVD API-key friction and CPE-matching false
positives make it expensive to keep quiet next to the alternatives above.

## Secrets

### gitleaks

```bash
gitleaks dir . --report-format sarif --report-path gl.sarif --redact   # v8.30.1
gitleaks git . --report-format sarif --report-path gl-history.sarif \
  --baseline-path baseline.json --redact
```

MIT licensed. **`detect` and `protect` were deprecated in v8.19.0** and hidden
from the help output; use `dir` for the working tree and `git` for history.
`--redact` keeps the matched secret out of the report, which matters because
the report is an artifact that gets stored.

Suppress with a fingerprint in `.gitleaksignore` or a trailing `#gitleaks:allow`
comment on the line.

Gitleaks is regex-only with no verification step, so on any repository with
history a baseline is mandatory. Without one the first run buries every real
alert under years of rotated test keys.

### trufflehog

```bash
trufflehog git file://. --results=verified --json --fail     # v3.96.0
```

AGPL-3.0, so check the licence position before embedding it in a product;
running it in CI is fine. It exits **183** when `--fail` is set and a verified
secret is found.

`--results=verified` means TruffleHog authenticated the credential against the
live service — a verified result is a real, currently-valid secret and deserves
an immediate response. Treat `unknown` results as "not confirmed clean" rather
than as clean. There is no SARIF output; parse the JSON.

After a leak, **rotate first**. History rewriting with
`git filter-repo --replace-text` is cleanup, not remediation: the credential
was public, and every clone and cache still has it.

## Infrastructure as code

### trivy config — the default

```bash
trivy config . --severity HIGH,CRITICAL --exit-code 1 --format sarif -o iac.sarif
```

Covers Terraform HCL and plan JSON, Kubernetes manifests, Dockerfiles, Helm
charts, CloudFormation, and ARM templates in one pass.

**tfsec is dead — it merged into Trivy.** Existing `#tfsec:ignore:AWS001`
comments still work there, so a migration does not require rewriting them.

### checkov — Terraform-heavy repositories

```bash
pip install checkov                                          # 3.3.8
checkov -d . --compact --framework terraform,kubernetes \
  --output sarif --output-file-path .
```

Gate with `--hard-fail-on CRITICAL` and `--soft-fail-on LOW`. Adopt on an
existing repository through its baseline workflow, so only new failures fail:

```bash
checkov -d . --create-baseline
checkov -d . --baseline .checkov.baseline
```

Suppress inline with `#checkov:skip=CKV_AWS_20:reason`.

### kube-linter

```bash
kube-linter lint ./manifests --format sarif                   # v0.8.3
```

Production-readiness as much as security: missing resource limits, readiness
probes, privileged containers.

### conftest

```bash
conftest test . --policy ./policy --output json
```

Rego policies for organization-specific rules that no shipped ruleset covers —
naming conventions, required tags, approved regions.

### Plan-based versus static

Scanning a Terraform plan finds what static HCL analysis cannot, because the
plan has resolved variables, modules, and defaults:

```bash
terraform plan -out=tf.plan
terraform show -json tf.plan > tfplan.json
checkov -f tfplan.json
```

It costs credentials and a provider round trip, so the practical split is
static locally and plan-based in CI where credentials already exist.

### tflint

```bash
tflint --recursive --format sarif
```

It catches correctness bugs — invalid instance types, deprecated syntax,
unreachable configuration — that no security scanner looks for. Worth running
alongside, not instead.

## Dynamic testing

Only when a deployed target exists. DAST beats SAST for post-login
authorization, deployed-only configuration, issues that require chaining
several requests, and findings that are confirmed exploitable and therefore
need no reachability triage.

### OWASP ZAP Automation Framework

Apache-2.0 and still actively released. One YAML plan describes the whole run:

```bash
docker run --rm -v $(pwd):/zap/wrk/:rw -t ghcr.io/zaproxy/zaproxy:stable \
  zap.sh -cmd -autorun /zap/wrk/plan.yaml
```

Jobs worth knowing: `spider` and `spiderAjax` for discovery, `openapi` to
import a specification, `activeScan` for the attack pass, `alertFilter` to
downgrade or drop known-noisy alerts, `exitStatus` to control the process exit,
and `report` with `template: sarif-json` for SARIF output. In GitHub Actions,
`zaproxy/action-af@v0.3.0` runs the same plan.

### nuclei

```bash
nuclei -u https://target -severity critical,high -sarif-export r.sarif   # v3.11.0
```

A signature matcher. Excellent for known CVEs, exposed panels, and default
credentials; useless for business logic, because it has no notion of what the
application is supposed to do.

### schemathesis

```bash
uvx schemathesis run https://app/openapi.json --checks all -n 100       # v4.24.3
```

The best free API fuzzer and cheap enough to run on a pull request. Its
`ignored_auth` check is the standout: it detects endpoints that return data
without enforcing the authorization the specification declares. No SARIF
output; read the report.

## Fuzzing

Fuzz parse, decode, and deserialize boundaries only. Everywhere else,
property-based testing finds more bugs per hour for less setup.

Go's native fuzzing is the only zero-friction entry point, because failing
inputs persist automatically into `testdata/` and become ordinary regression
tests:

```bash
go test -fuzz=FuzzParse -fuzztime=60s ./pkg/...
```

`cargo fuzz` needs a nightly toolchain. AFL++ v5.02c remains the reference for
native targets. OSS-Fuzz is not available for private products, and
ClusterFuzzLite is in maintenance mode, so a private repository runs its own.

**Cache the corpus between runs or this is just slow random testing.** A fuzzer
starting from an empty corpus every night re-derives the same shallow inputs
and never reaches the interesting states.

## Normalization

```bash
pip install sarif-tools           # 3.0.5
sarif summary out/                # counts by severity and rule, all files
sarif diff base/ head/            # what changed between two scans
sarif csv out/ --output all.csv
sarif html out/ --output all.html
```

One digest across every tool is the difference between a readable result and
six files nobody opens.

## SARIF limits

Version 2.1.0 only. The ceilings that bite on a large repository:

| Limit | Value |
| --- | --- |
| File size | 10 MB gzipped |
| Runs per file | 20 |
| Results per run | 25,000, of which only the top 5,000 by severity are retained |
| Locations per result | 1,000 |

Exceeding them drops results rather than failing loudly, so split output by
tool instead of concatenating.

GitHub code scanning SARIF upload is **free for public repositories only**;
private repositories require a paid Code Security licence. A project-agnostic
pipeline must therefore fall back to workflow artifacts, a job summary, or:

```bash
reviewdog -f=sarif -reporter=github-pr-review -filter-mode=added < out.sarif
```
