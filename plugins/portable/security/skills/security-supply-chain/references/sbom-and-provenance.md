# SBOM, signing, provenance, and repository scoring

Pass 3 answers one question: can somebody who did not build this artifact prove
what it contains and where it came from? Pass 4's checklists mostly test
whether you answered it.

## Action Bill of Materials

An SBOM inventories what enters the product. An **Action Bill of Materials
(ABOM)** inventories third-party code that can influence the build even when it
does not ship in the product:

- GitHub Actions and reusable workflows;
- local or third-party composite actions;
- job and service container images;
- compilers, generators, package managers, bundlers, signing clients, deployment
  utilities, and downloaded build tools.

Generate the ABOM from workflow files, composite-action definitions, Dockerfile
base images, and explicitly declared build utilities for every reviewed source
revision. Do not maintain a hand-written list that drifts from the executable
configuration. The generator deliberately exits nonzero after writing the
inventory when it finds a mutable tag or branch, so the ABOM cannot be treated
as passing evidence until those inputs are pinned:

```bash
python ../scripts/generate_action_bom.py /path/to/repository \
  --output /private/artifacts/action-bom.json \
  --minimum-age-days 7 \
  --build-utility 'pinact=sha256:<64-hex-digest>'
python ../scripts/validate_security_profile.py \
  /private/artifacts/action-bom.json
```

For a Git repository, the generator resolves the source revision to a commit
and reads tracked workflow and Dockerfile blobs from that commit rather than
the live worktree. Ignored files, untracked files, and uncommitted edits
therefore cannot change a revision-bound ABOM. The source revision and
generation timestamp default to the checked-out commit and its commit time,
making repeated generation stable for the same revision. A non-Git fixture
directory uses a deterministic filesystem scan and requires both
`--source-revision` and `--generated-at`; do not use that fallback as release
evidence. Pin the generator version in CI and declare build utilities with a
commit, digest, or package URL plus digest. Start from
`../assets/action-bom.template.json` when integrating a new consumer; each entry
records a stable id,
kind, consumer location, source, immutable commit/digest/package-hash evidence, version
annotation, effective permissions, provenance status, review status, and
`file:line` or setting evidence. Validate it with:

```bash
python ../scripts/validate_security_profile.py path/to/action-bom.json
```

Tie the ABOM to the source revision. Diff it on workflow/build changes and on a
release. A new source, widened permission, mutable reference, publisher change,
or provenance regression requires review under the dependency-intake policy.
An ABOM does not replace SHA/digest pinning or workflow review; it makes those
inputs enumerable and comparable.

## SBOM

Emit **CycloneDX 1.7** as the primary format. It was published in October 2025
and standardized as ECMA-424 2nd edition, and it is the format most tooling
consumes today. Add SPDX 3.0.1 only when a consumer asks for it — carrying two
formats you do not verify is worse than carrying one you do.

```bash
syft . -o cyclonedx-json=sbom.cdx.json -o spdx-json=sbom.spdx.json
syft <image>:<tag> -o cyclonedx-json=image.cdx.json
```

`syft` writes both formats from a single catalog pass, so there is no reason to
run it twice. Use `cdxgen` only when `syft` under-resolves a build — in
practice JVM and .NET projects, where the dependency graph lives in a build
tool rather than in a lockfile.

Two properties decide whether an SBOM is useful:

- it is generated from the built artifact or its lockfile, not hand-written;
- it is regenerated on every release, and stored with the release rather than
  in the repository.

An SBOM that drifts is worse than none, because it is evidence of a component
inventory that does not exist.

## Signing with cosign

```bash
brew install cosign          # or download the release binary

# Sign, keyless. Requires id-token: write in the workflow.
cosign sign --yes <registry>/<image>@sha256:<digest>

# Attach the SBOM as an attestation.
cosign attest --yes \
  --predicate sbom.cdx.json \
  --type cyclonedx \
  <registry>/<image>@sha256:<digest>
```

`--type` accepts `slsaprovenance`, `slsaprovenance02`, `slsaprovenance1`,
`link`, `spdx`, `spdxjson`, `cyclonedx`, `vuln`, `openvex`, `custom`, or a URI.
Sign digests, never tags: a tag is mutable and a signature over a tag proves
nothing about what a consumer pulls later.

### Verification is where this goes wrong

```bash
cosign verify <registry>/<image>@sha256:<digest> \
  --certificate-identity-regexp \
    'https://github.com/ORG/REPO/\.github/workflows/.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

Keyless verification is only meaningful when it constrains *who* signed. cosign
requires one of `--certificate-identity` / `--certificate-identity-regexp` and
one of `--certificate-oidc-issuer` / `--certificate-oidc-issuer-regexp` for
keyless flows, so a completely unconstrained `cosign verify` is refused. The
mistake that survives that check is an over-broad regexp — `.*`, or a pattern
that matches any repository under any owner. It verifies successfully, produces
a green check in CI, and means only that *somebody* with a Sigstore identity
signed the image.

When reviewing a verification step, read the regexp. Anchor it, name the
organization and repository, and name the workflow path. That is the finding.

## Build provenance and SLSA

**SLSA v1.2** was approved on 24 November 2025 and supersedes v1.0 and v1.1.
There is no Build L4.

| Level | What it means |
| --- | --- |
| Build L0 | No guarantees |
| Build L1 | Provenance exists, showing how the package was built. Trivial to forge; catches mistakes and documents the build |
| Build L2 | Signed provenance generated by a hosted build platform. Defends against tampering after the build |
| Build L3 | Hardened build platform with isolated runs; the signing key is unreachable from build steps. Defends against tampering during the build |

v1.2 also reintroduces a Source track alongside the Build track.

The free path to Build L2 on GitHub Actions is one step:

```yaml
permissions:
  id-token: write
  contents: read
  attestations: write

steps:
  - uses: actions/attest-build-provenance@v4
    with:
      subject-path: 'dist/*'
```

Verify it as a consumer would:

```bash
gh attestation verify ./dist/app \
  -R org/repo \
  --signer-workflow org/repo/.github/workflows/release.yml
```

`gh attestation verify` requires at least `--owner` or `--repo`. Adding
`--signer-workflow` (or `--cert-identity`) is what turns "somebody in this org
signed it" into "this specific release workflow signed it", and it is
mandatory when the attestation came from a reusable workflow. Treat a
verification step without one of those flags the same way as an unanchored
cosign regexp.

Reach for `slsa-framework/slsa-github-generator` only when a consumer requires
certified Build L3. It is materially more machinery, and L2 with anchored
verification already removes the whole class of post-build tampering.

## Deploy by digest and reconcile live state

Verification is incomplete when CI verifies one digest and deployment later
resolves a mutable tag. Carry one immutable artifact identity across the whole
chain:

1. Build the artifact and record its digest.
2. Generate the SBOM from the built artifact or locked graph and associate its
   digest with that artifact.
3. Sign and attest the artifact digest using the intended release identity.
4. Verify the signature, provenance identity, subject digest, and SBOM before
   promotion.
5. Put the digest, not a tag, in the deployment input or rendered deployment
   manifest.
6. Read the registry digest and the live runtime revision/image digest after
   deployment and compare them to the release record and declared IaC.

A release verification record should contain the reviewed source revision,
builder/workflow identity, artifact and SBOM digests, signature/provenance
verification output, declared deployment digest, registry digest, live digest,
environment, deploy actor, and timestamp. Any mismatch fails promotion or
opens an incident; it is not normalized away by rewriting the record.

Reconcile on every deployment and periodically for long-lived T2–T4 services.
Also reconcile after a rollback, manual deployment, registry migration, or IaC
import. A scheduled check must read the live platform rather than compare two
copies of the same desired-state file. Tags may remain as human-friendly
labels, but they are never the deployment or verification identity.

## OpenSSF Scorecard

```bash
export GITHUB_AUTH_TOKEN=<token>
scorecard --repo=github.com/org/repo --show-details
scorecard --repo=github.com/org/repo --format=json
ENABLE_SARIF=1 scorecard --repo=github.com/org/repo --format=sarif
```

v5.5.0. Note that `--format=sarif` is gated behind `ENABLE_SARIF=1`; without
it the CLI rejects the format. `--show-details` is what makes a low score
actionable — the bare score is not a finding.

v5.5.0 documents 20 checks: `Binary-Artifacts`, `Branch-Protection`,
`CI-Tests`, `CII-Best-Practices`, `Code-Review`, `Contributors`,
`Dangerous-Workflow`, `Dependency-Update-Tool`, `Fuzzing`, `License`,
`Maintained`, `Packaging`, `Pinned-Dependencies`, `SAST`, `SBOM`,
`Security-Policy`, `Signed-Releases`, `Token-Permissions`, `Vulnerabilities`,
`Webhooks`.

Scorecard has no built-in pass/fail threshold, so gate on parsed JSON rather
than on the aggregate score, which mixes signals that mean very different
things for a given project. Prioritize in this order:

1. `Dangerous-Workflow` — this one is close to always a real finding.
2. `Token-Permissions`
3. `Pinned-Dependencies`
4. `Branch-Protection`
5. `Binary-Artifacts`

`Fuzzing`, `CII-Best-Practices`, and `Contributors` are weak signals for a
small team and should not drive remediation work.

## OSPS Baseline

`ossf/security-baseline` is the best drop-in repository checklist available for
free, and unlike most checklists it ships machine-readable YAML you can drive a
review from. Pin the version string, because identifiers and counts move
between releases.

At tag **`v2026.02.19`**, verified directly from the repository:

- 8 categories — Access Control (`OSPS-AC`), Build & Release (`OSPS-BR`),
  Documentation (`OSPS-DO`), Governance (`OSPS-GV`), Legal (`OSPS-LE`),
  Quality (`OSPS-QA`), Security Assessment (`OSPS-SA`), Vulnerability
  Management (`OSPS-VM`);
- 41 controls, with identifiers like `OSPS-VM-06`;
- 65 assessment requirements beneath them, with identifiers like
  `OSPS-VM-06.02`;
- 3 maturity levels — Level 1 for any project, Level 2 for a project with at
  least two maintainers and a small consistent user base, Level 3 for a project
  with a large consistent user base.

The controls carry mappings to other frameworks (OpenSSF Best Practices Badge,
the EU CRA, NIST SSDF, the NIST CSF, OpenCRE, PCI DSS, SAMM, SP 800-161), which
makes the Baseline a practical translation layer: satisfy a control once, cite
it against several checklists.

To use it in a review, fetch `baseline/OSPS-*.yaml` at the pinned tag, filter
to the target maturity level, and walk each assessment requirement against the
repository. Report per requirement id so the result is comparable across runs.
Numbers above were counted from the YAML at that tag; recount rather than
quoting them for a different tag.
