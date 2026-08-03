# CI/CD hardening and dependency intake

Everything here is free and CLI-drivable. Versions are the ones verified at the
time of writing; re-check before quoting a number to a user.

## zizmor

Static analysis for GitHub Actions workflows and composite actions.

```bash
uv tool install zizmor                       # or: uvx zizmor ...
zizmor .github/workflows/                    # human-readable
zizmor --format sarif .github/workflows/ > zizmor.sarif
zizmor --no-exit-codes .github/workflows/    # plain output, no severity codes
```

Output formats: `plain` (default), `json`, `sarif`. Version v1.28.0 documents
40 audits.

### Audits that most often become real findings

| Audit | What it catches |
| --- | --- |
| `template-injection` | `${{ … }}` interpolated into a `run:` block, where attacker-controlled text becomes shell code |
| `artipacked` | `actions/checkout` leaves the token in `.git/config`; a later artifact upload publishes it |
| `excessive-permissions` | Workflow or job with more `GITHUB_TOKEN` scope than it uses |
| `dangerous-triggers` | `pull_request_target` and friends, which run with secrets in the base repository's context |
| `cache-poisoning` | A cache writable from an untrusted context and read by a trusted one |
| `impostor-commit` | A `uses:` SHA that is reachable in the network of forks but not in the named repository |
| `typosquat-uses` | An action reference one edit away from a popular one |
| `unpinned-uses` | Tag or branch refs rather than commit SHAs |
| `secrets-inherit` | `secrets: inherit` passing everything to a called workflow |
| `github-env` | Writes to `$GITHUB_ENV` / `$GITHUB_PATH` from untrusted data |

Read the upstream audit documentation (`docs/audits.md` in the repository, or
<https://docs.zizmor.sh/audits/>) for the full set rather than relying on this
table being complete; audits are added in most minor releases.

### Exit codes

| Code | Meaning |
| --- | --- |
| 0 | Clean, or SARIF mode |
| 1 | Error during the audit |
| 2 | Argument parsing failure |
| 3 | No inputs were collected |
| 11 | Findings, highest severity informational |
| 12 | Findings, highest severity low |
| 13 | Findings, highest severity medium |
| 14 | Findings, highest severity high |

This is the trap. `zizmor` returning non-zero does not mean it failed, and it
does not mean the finding is serious. `--no-exit-codes` and `--format sarif`
both suppress codes 11 and above, so a CI step can distinguish a tool crash
from an informational finding. Gate on the parsed SARIF, not on `$?`.

## actionlint

```bash
go install github.com/rhysd/actionlint/cmd/actionlint@latest
actionlint                                   # all workflows under .github/workflows
actionlint -format '{{json .}}'
```

v1.7.12. Complementary to `zizmor`, not a substitute: workflow schema
validation, expression type checking, `needs:` graph consistency, runner label
checks, and shellcheck over every `run:` block. Many real CI defects are
correctness bugs that only become security bugs under load, and this is the
tool that finds them.

## SHA-pinning actions

### Why

`tj-actions/changed-files`, CVE-2025-30066, March 2025. An attacker gained
write access and force-moved the action's version tags — including tags that
looked like stable releases — onto a commit that dumped the runner's process
memory into the build log. On public repositories those logs are world
readable, so any secret that had passed through the runner was exposed.
Roughly 23,000 repositories referenced the action. Repositories that pinned by
commit SHA were unaffected, because a tag move cannot change the content a SHA
addresses.

The lesson generalizes past this one incident: a tag is a mutable pointer
controlled by the upstream maintainer's account. A SHA is not.

### How

```bash
go install github.com/suzuki-shunsuke/pinact/v4/cmd/pinact@latest

pinact run --check          # report only; exit 2 when something is unpinned
pinact run                  # rewrite uses: refs to SHAs with version comments
pinact run --update         # move pins forward to the latest release
pinact run --min-age 7      # when updating, ignore releases newer than 7 days
pinact run --verify-min-age # also check the currently pinned versions
pinact run --format sarif
```

`--min-age` takes a number of days and can also be set through `PINACT_MIN_AGE`
or `.pinact.yml` (`min_age.value`, plus per-rule `min_age`). Exit code 2 means
an action could not be auto-fixed: a branch reference, a SHA pin with no
version comment, or a `--min-age` violation.

`ratchet` (`ratchet pin`, `ratchet check`) is an equivalent tool if it is
already in the toolchain. Either way, Dependabot understands SHA pins with a
trailing `# v4.1.1`-style comment and updates both together, so pinning does
not freeze you on old versions.

### The rest of the workflow checklist

- Set `permissions:` explicitly at the workflow level, default it to
  `contents: read`, and widen it per job only where a job needs more.
  `id-token: write` is needed for keyless signing and OIDC, and should never be
  granted at the workflow level "just in case".
- `persist-credentials: false` on `actions/checkout` unless a later step pushes
  with the same token.
- Never check out the pull request head ref inside a `pull_request_target`
  workflow. That combination runs untrusted code with access to the base
  repository's secrets, and it is the single most common way a repository loses
  its release credentials.
- Treat self-hosted runners as shared state. A non-ephemeral runner carries
  whatever the previous job left behind.
- Pin container images by digest, not by tag, for the same reason as actions.

## Short-lived CI identity with OIDC and workload identity federation

Prefer a workload identity issued for one job over a stored PAT, registry token,
or cloud key. OIDC-based workload identity federation (WIF) is not safe merely
because it is short-lived: the trust policy must bind the token to the intended
issuer, audience, repository, workflow, ref or protected environment, and
operation. A subject pattern broad enough to match a fork, another workflow, or
every branch preserves the same attack path as a shared secret.

Verify all of these:

1. `id-token: write` exists only on the job that exchanges the token, not as a
   workflow-wide default.
2. The identity provider checks issuer and audience and constrains repository,
   workflow, ref/tag, and environment claims as tightly as the release process
   permits.
3. The resulting cloud or registry principal has only the publish/deploy action
   and target scope the job needs. Federation removes a stored key; it does not
   make an over-privileged role safe.
4. A run from the wrong branch, workflow, repository, or environment fails the
   exchange. Record this negative test; reading the happy path is insufficient.
5. Token issuance and use are present in retained provider audit logs with the
   workload subject and target resource.
6. Superseded PATs, cloud keys, and registry tokens are removed and rotated.
   Leaving a fallback secret in repository settings leaves the old path open.

When federation is unavailable, use a per-environment credential with the
shortest practical lifetime and scope, expose it only to the privileged job,
rotate it automatically, and record federation as a prerequisite rather than
claiming equivalence.

## Runner, source, and workspace isolation

Provider-hosted jobs are normally single-use and are the default for small
projects. A privileged self-hosted job needs equivalent evidence: a fresh
instance per job, no previous workspace or process state, no organization-wide
credential, and destruction after evidence export. Cleanup scripts on a
persistent runner are not equivalent because the compromised job controls the
cleanup environment.

Separate untrusted evaluation from privileged publish/deploy:

- An untrusted pull request may build and test without secrets, but it must not
  hand a writable workspace, cache, executable artifact, environment file, or
  generated workflow directly to a privileged job.
- The privileged job starts from a fresh checkout of the reviewed immutable
  commit. When it consumes an artifact from an earlier job, bind that artifact
  to a digest and the reviewed source revision, and verify both before use.
- Keep release credentials and `id-token: write` out of dependency installation
  and arbitrary project-script steps. Split fetch/build, verify, and publish
  when the platform permits it.
- Scope caches by trust level and immutable inputs. Never let an untrusted
  context write a cache that a privileged release consumes as executable code.
- Do not mount the host container socket, developer home directory, SSH/cloud
  configuration, or package-manager credentials into an untrusted or build
  workspace.

## Egress from privileged jobs

A privileged build usually needs fewer destinations than a test job: source
hosting, the selected package registry or mirror, the attestation service, and
the publish/deploy endpoint. Deny other egress when the runner platform supports
it, or move publishing into a small job whose network surface can be bounded.

An allowlisted hostname is not enough evidence. Verify the TLS identity and
whether the destination accepts attacker-controlled writes or uploads. A
telemetry endpoint, gist service, public object store, or compromised package
registry can be an exfiltration path even when its domain is expected. Record
the allowed destination, method, purpose, write capability, owner, and review
date. Alert on denied destinations and unusual upload volume, and fail closed
when the policy or proxy is unavailable.

## Package-manager and install-script risk

### The threat as of 2026

Install lifecycle scripts run arbitrary code on every developer machine and
every CI runner, before any test or lint has a chance to look at the code.

| Event | Date | Shape |
| --- | --- | --- |
| Shai-Hulud | September 2025 | Self-propagating npm worm; stole registry and cloud credentials from `postinstall`, republished itself using stolen tokens |
| Shai-Hulud 2.0 | November 2025 | Roughly 796 packages; moved to `preinstall` so the payload ran even when the install later failed |
| "Mini Shai-Hulud" | May 2026 | 170+ npm packages and 2 on PyPI; same family, smaller blast radius |

### Controls

```bash
npm ci --ignore-scripts
```

and, permanently, `ignore-scripts=true` in `.npmrc`. Packages that genuinely
need a build step then need an explicit allowlist or a rebuild step; that
friction is the point, because it makes the set of packages that execute code
visible and small.

```bash
npm audit signatures
```

Verifies registry signatures and, where present, provenance attestations for
the installed tree. npm Trusted Publishing (OIDC, generally available since
July 2025) makes publishers emit `--provenance` automatically, so coverage
improves over time; do not treat a missing attestation as a finding on its own.

### Release cooldown

Malicious releases are typically detected and yanked within hours. Delaying
adoption by a few days filters most of them at no review cost.

| Tool | Setting | Unit |
| --- | --- | --- |
| npm CLI ≥ 11.10.0 (February 2026) | `min-release-age`, with `min-release-age-exclude` | days |
| Renovate | `minimumReleaseAge` | duration string, e.g. `"3 days"` |
| pinact | `--min-age` | days |

npm's `before` setting takes an absolute date and wins over `min-release-age`
within a single configuration source. When the cooldown blocks a version that
`npm audit fix` wanted to install, npm keeps the vulnerable version, warns, and
exits non-zero — so a cooldown and an audit gate can deadlock. Resolve it by
adding the specific package to `min-release-age-exclude`, not by removing the
cooldown.

### Lockfile discipline

| Ecosystem | CI command | Never in CI |
| --- | --- | --- |
| npm | `npm ci` | `npm install` |
| pnpm | `pnpm install --frozen-lockfile` | `pnpm install` |
| yarn (berry) | `yarn install --immutable` | `yarn install` |
| uv | `uv sync --locked` | `uv sync` |
| pip | `pip install --require-hashes -r requirements.txt` | `pip install -r …` |
| cargo | `cargo build --locked` | `cargo build` |

For pip, generate the hashed file with
`uv pip compile requirements.in --generate-hashes -o requirements.txt`, then
audit with `pip-audit --strict` (which fails rather than skipping when a
dependency cannot be resolved to a known distribution).

PEP 740 attestations are Final and PyPI serves them, but as of this writing
neither pip nor uv will refuse an unsigned or unattested package. Collect them
as audit evidence; do not describe them to a user as a gate.

## What to check without any tools

If nothing is installed, reading recovers most of pass 1:

- `grep -rn 'github.event' .github/workflows/` and look for hits inside `run:`
  blocks or `script:` inputs.
- `grep -rn 'uses:' .github/workflows/` and flag every ref that is not 40 hex
  characters.
- `grep -Ln 'permissions:' .github/workflows/*.yml` for workflows relying on
  the repository default.
- `grep -rn 'pull_request_target' .github/workflows/` and check each one for a
  checkout of `github.event.pull_request.head.sha` or `.ref`.
- Read every `package.json` for `preinstall`, `install`, and `postinstall`, and
  every `setup.py` / `pyproject.toml` build hook.
