# Dependency intake and disposition policy

This policy decides whether a package, action, build image, compiler plugin,
skill, or other third-party development input may enter or remain in a build.
It complements immutable installs and scanning: a lockfile proves which input
was selected, not that selecting it was safe.

## Evidence classes

Separate deterministic evidence from soft signals before deciding what may
block.

**Deterministic evidence** is directly reproducible and attributable:

- a digest, signature, or attestation fails verification against the required
  identity;
- the resolved artifact differs from the approved lockfile or ABOM entry;
- a registry, vendor, or coordinated advisory identifies the exact release as
  malicious or revoked;
- a reachable vulnerability affects the selected version and a validated fixed
  version exists;
- an install/build script executes outside the explicit allowlist;
- a source or publisher identity violates an explicit organization policy.

**Soft signals** change review depth but are not proof of compromise:

- a release is newer than the normal cooldown;
- provenance is unavailable in an ecosystem where it is optional;
- the project is low-activity, archived, or has a small maintainer set;
- ownership, publisher, namespace, or signing identity changed recently;
- popularity, download count, reputation, or maintainer tenure is low;
- a scanner cannot resolve the package or assign a severity.

Never combine several soft signals into a fictional deterministic verdict.
Record the uncertainty, require review where proportionate, and prefer a
well-supported alternative when one exists.

## Disposition matrix

| Condition | Default disposition | May block? | Evidence and exit condition |
| --- | --- | --- | --- |
| Confirmed malicious, revoked, digest-mismatched, or identity-verification failure | Quarantine; block install, build, publish, and deployment; preserve evidence; rotate exposed credentials | Yes, deterministic | Vendor/registry record or reproduced verification failure; replacement or explicitly reviewed rollback |
| Reachable vulnerability with a validated fix | Update under lockfile and regression tests; use normal review unless exploitation is active | Yes for an agreed severity/reachability gate | Scanner record, reachability trace, fixed version, tests, regenerated SBOM/ABOM |
| Reachable vulnerability without an upstream fix | Track and time-bound; apply compensating control, isolate, replace, or remove | No automatic block on unrelated changes | Reachability, lack of fix, owner, review date, compensating control and replacement plan |
| Vulnerability not reachable in the deployed use | Retain with documented evidence and scheduled re-evaluation | No | Call/configuration trace, deployment evidence, and review date |
| Newly published release inside cooldown | Hold unless an urgent fix or compatibility need is documented | Policy may defer adoption, but is not a malicious-package verdict | Release timestamp, cooldown rule, exception owner, tests, and follow-up date |
| Missing provenance or signature where the ecosystem does not enforce it | Review source, publisher, hashes, and alternatives; prefer verified inputs | No by itself | Ecosystem capability, publisher evidence, hash/lockfile, exception or migration plan |
| Abandoned or archived dependency | Prefer maintained replacement; otherwise pin, minimize exposed surface, and schedule review | No by itself | Upstream status, last release/activity, reachable surface, replacement cost, owner |
| Maintainer, namespace, publisher, or signing-identity transfer | Pause automatic update; verify the transfer and compare release contents/behavior | Yes as a temporary review hold, not as a finding | Registry/source history, identity evidence, diff, scripts, provenance, explicit approval |
| Dependency confusion or unexpected registry/source | Block and investigate; reserve internal names and constrain registry/source selection | Yes, deterministic when resolution violates policy | Resolver output, package source, namespace policy, lockfile, registry configuration |
| Package requires install/build script | Deny by default; allow only the named package and script in an explicit rebuild/allowlist step | Yes when outside the allowlist | Manifest script, justification, sandbox/egress boundary, expected output, owner |

## Intake procedure

1. Resolve the exact source, version, digest, publisher, and dependency type.
2. Check the immutable lockfile or ABOM and identify any install/build-time code.
3. Run the ecosystem SCA and integrity checks. Treat “no packages found” or an
   unavailable database as incomplete coverage, not a clean result.
4. Check deterministic evidence first. Quarantine before further execution when
   integrity or maliciousness is confirmed.
5. Apply the normal release cooldown and inspect soft signals. A soft signal
   raises review depth; it does not create a vulnerability finding.
6. Record the decision, evidence, prerequisites, owner, expiry or review date,
   and failure mode in the repository security profile.
7. Regenerate the lockfile, SBOM, and ABOM after an accepted change. Run the
   tests that exercise the dependency's reachable behavior.

## Automated update policy

Automation may propose an update and run deterministic checks. It may merge
only when the repository has explicitly allowed that update class, every
required check completed, the cooldown passed, the source/publisher did not
change unexpectedly, and no install/build-script capability widened.

Require human review for:

- a new direct dependency or action;
- a major version change;
- a maintainer, publisher, namespace, registry, or signing-identity change;
- a new lifecycle/build script or network destination;
- an emergency cooldown bypass;
- a dependency on a release, deployment, agent, payment, custody, or signing
  path.

Do not let update automation weaken a lockfile, change registries, remove hash
checking, broaden workflow permissions, or silently accept a new exception.

## Exceptions

An exception names the exact input and version range, why the normal policy
cannot be met, the compensating control, owner, approval, evidence, and expiry
or next review. “No alternative” is not sufficient without the search evidence
and reachable impact. Expired exceptions fail review; they do not silently
renew.
