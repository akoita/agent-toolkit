# Exit codes and suppression

## Why this page exists

There is no convention. Some tools exit 1 on findings, some exit 2, some exit 0
unless a flag says otherwise, and one exits 183. A pipeline written as
`tool && next` or `if [ $? -ne 0 ]; then fail; fi` will report a clean scan as a
failure, a failed scan as clean, or both on different steps of the same job.

Capture each exit code explicitly and compare it against this table.

```bash
set +e
osv-scanner scan source -r ./ --format sarif --output osv.sarif
osv_status=$?
set -e
case "$osv_status" in
  0)   echo "osv: clean" ;;
  1)   echo "osv: vulnerabilities found" ;;
  128) echo "osv: NO PACKAGES FOUND - the scan did nothing"; exit 1 ;;
  *)   echo "osv: error ($osv_status)"; exit 1 ;;
esac
```

## The table

| Tool | Exit code behavior |
| --- | --- |
| `osv-scanner` | 0 packages found and clean; 1 vulnerabilities found; 1–126 reserved for result-related errors; 127 general error; **128 no packages found**; 129–255 non-result errors |
| `trivy` | 0 always, **unless `--exit-code N` is passed**; then N on findings at or above `--severity` |
| `grype` | 0 clean; **`--fail-on <severity>` exits 2**, not 1 |
| `gitleaks` | 1 when leaks are found |
| `trufflehog` | **183 when `--fail` is set and a verified secret is found** |
| `zizmor` | 0 clean; 1 on an error; **11, 12, 13, 14 by finding severity** |
| `semgrep` | 0 on findings **unless `--error` is passed**; then 1 |
| `conftest` | 1 on a policy failure |
| `kube-linter` | 1 on a lint failure |
| `checkov` | 1 on a failed check; tune with `--hard-fail-on` and `--soft-fail-on` |
| `codex-security` | 0 pass; 1 finding at or above `--fail-on-severity` on a completed scan; 2 invalid input, incomplete coverage, or runtime error; 130 interrupted; 143 terminated |
| `codecrucible` | 0 clean; 1 error; **2 findings at or above `--fail-on-severity`** — inverted relative to `codex-security` |

Two of these deserve a second look. `osv-scanner` returning 128 means no
manifest was recognized: a green pipeline that scanned nothing. And
`codex-security` returning 2 conflates a runtime error with incomplete
coverage, so read `coverage.json` and check its `completeness` field
(`complete`, `partial`, `unknown`) rather than inferring the cause from the
status.

For any tool whose report file is the real product, prefer reading the report
over trusting the status. A scan that crashed halfway can still leave a valid,
short, misleadingly clean file behind — which is why `codecrucible` runs need
`jq '.runs[0].invocations[0].executionSuccessful' results.sarif` before the
results are read at all.

## Suppression syntax

| Tool | Inline form |
| --- | --- |
| Semgrep and opengrep | `// nosemgrep` or `// nosemgrep: rule-id` |
| Checkov | `#checkov:skip=CKV_AWS_20:reason` |
| Gitleaks | `#gitleaks:allow` on the line, or a fingerprint in `.gitleaksignore` |
| Trivy | `#trivy:ignore:AVD-DS-0002` |
| Bandit | `# nosec B602` |
| gosec | `// #nosec G402 -- reason` |
| tfsec (legacy, now handled by Trivy) | `#tfsec:ignore:AWS001` |

Name the specific rule. A bare `// nosemgrep` or `# nosec` disables every rule
on the line, including ones written after the comment, and that is how a
suppression added for a formatting complaint ends up hiding an injection.

## Suppression policy

Prefer the earliest option that works:

1. **Tune the rule** — fixes the class once, for everyone, and leaves no marker
   in the source.
2. **Allowlist the path** — legitimate for generated code, vendored
   dependencies, fixtures, and test data. Never for an application source
   directory.
3. **Baseline** — freeze the current alert set so only new alerts fail. The
   right move when adopting a tool on an existing repository, and the wrong one
   as a permanent habit. Put a review date on it.
4. **Inline suppression with a mandatory justification** — the most precise and
   the most expensive. It survives refactors it should not survive and nobody
   rereads it. Reject any suppression without a reason in review.

Every suppression is an accepted risk. Review the whole set on a schedule and
delete the ones whose justification no longer describes the code.

## What may block

Keep the blocking set small and near-zero false positive: secrets, hardcoded
credentials, unsafe deserialization. A gate that is wrong more than roughly a
fifth to a third of the time gets routed around, and the true positives leave
with it.

Never gate on an unfixable transitive vulnerability. When no upstream fix
exists, blocking the build punishes whoever opens the next pull request and
changes nothing about the risk — `--ignore-unfixed` on Trivy exists for exactly
this. Track it, note the compensating control, and gate on the direct
dependencies the team controls.
