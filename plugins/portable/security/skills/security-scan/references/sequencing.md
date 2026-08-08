# Sequencing

The same tool is useful or intolerable depending on when it runs. A secret
scanner that takes four seconds before a commit is a good trade; the same
scanner taking four minutes there gets uninstalled by the end of the week.
Place each check by its latency budget and by what it can honestly block.

## The cadence

| Stage | Budget | Blocking | What runs |
| --- | --- | --- | --- |
| Pre-commit | under 5 s | Yes, secrets only | `gitleaks dir .`, `detect-private-key`, formatters, `actionlint` on changed workflow files |
| Pre-push | under 30 s | Yes | The ecosystem linter for the changed language, `checkov -f` on changed IaC files |
| Pull-request CI | under 5 min | New HIGH and CRITICAL only | Diff-scoped SAST with `--baseline-commit`, `osv-scanner`, `trivy config`, supply-chain checks, LLM diff review |
| Nightly | unbounded | Never | Full-tree SAST, verified secret scan over history, image scanning, the DAST plan, fuzz targets |
| Release | as long as it takes | Yes | SBOM generation, signing, provenance verification |
| Quarterly | a scheduled block of time | n/a | Baseline and suppression review, standards gap pass |

## Pre-commit

The only thing worth blocking a commit for is a secret, because a secret that
reaches the remote is unrecoverable — rotation is the only remedy and it costs
far more than the four seconds. Everything else can wait for a stage that has a
budget.

Run `gitleaks dir .` on the working tree rather than over history, add
`detect-private-key` from the standard pre-commit hooks, and run `actionlint`
when a workflow file changed. Keep formatters here too: they cost nothing and
they remove an entire category of review noise.

## Pre-push

Thirty seconds is enough for the ecosystem linter on the changed language —
`ruff` with the `S` rules, `gosec`, `brakeman`, `cargo clippy` — and for
`checkov -f` against the individual infrastructure files that changed. This is
the last stage where a failure costs the author nothing but a rerun, so it is
the right place for checks that are precise but slower than a commit hook
allows.

## Pull-request CI

Five minutes is the ceiling before people start merging around the pipeline.
Everything here is diff-scoped:

- SAST with `--baseline-commit "$(git merge-base origin/main HEAD)"`, so only
  what the branch introduced is reported;
- `osv-scanner` on the manifests, watching for exit 128;
- `trivy config` on changed infrastructure;
- supply-chain checks on workflow and dependency changes;
- the LLM diff review, advisory and inline.

Block on new HIGH and CRITICAL findings only. Everything else annotates the
change. Pre-existing findings never block a pull request that did not introduce
them — that is what a baseline is for, and a pipeline that fails on inherited
debt trains people to ignore it.

## Nightly

Nothing here blocks anything, which is what makes the unbounded budget usable.
Run the full-tree SAST without a baseline, `trufflehog --results=verified` over
the whole history, container image scanning, the ZAP automation plan against a
deployed environment, and the fuzz targets with a cached corpus.

Nightly output goes to a dashboard or a digest, not to a pull request. Its job
is to find what diff-scoped scanning structurally cannot: issues that predate
the baseline, and issues that only exist in a deployed configuration.

## Release

The one stage where slow and blocking are both correct. Generate the SBOM, sign
the artifacts, and verify the provenance before publishing. A release that
cannot produce its own attestation should not ship, and there is no argument
about latency at a cadence measured in weeks.

## Quarterly

Set aside a block of time to review the accumulated baselines and inline
suppressions, delete the ones whose justification no longer describes the code,
and do a gap pass against whichever standard the project is measured by. Both
grow silently and neither is ever urgent, which is exactly why they need a
calendar entry rather than a ticket.

## The ratchet rule

Never land a new check as required. Land it with `continue-on-error: true` for
two to four weeks, watch what it reports on real pull requests, tune it, and
promote it to required only once its false-positive rate on this repository is
known and small.

```yaml
- name: New security check (advisory until 2026-09-01)
  continue-on-error: true
  run: ./scripts/new-check.sh
```

A check promoted straight to required teaches the team that the pipeline is
unreliable, and that lesson outlives the check. The soak period is also the
only honest way to measure the false-positive rate, since it is a property of
the repository and not of the tool.
