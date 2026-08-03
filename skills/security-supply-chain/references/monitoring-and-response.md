# Supply-chain monitoring and response

Preventive controls reduce compromise probability. Monitoring and response
bound the time and blast radius when a package, workflow, identity, builder, or
developer tool is compromised anyway.

## Monitoring contract

Every monitor records five things: the event source, retained fields, detection
logic, routed owner, and first response action. A dashboard without routing is
not a control, and an alert without the evidence needed to reconstruct the
event is not actionable.

| Surface | Watch for | Evidence to retain | First response |
| --- | --- | --- | --- |
| Workflow and release policy | New or modified workflow, reusable workflow, trigger, permission, environment, runner label, action ref, secret mapping, or protection rule | Actor, review/merge record, before/after content, source revision, workflow identity | Stop privileged runs when the change is unexpected; preserve the diff and review path |
| Workflow execution | Unusual manual/scheduled trigger, fork/base-context mismatch, repeated failed release, unapproved environment use, or job outside normal cadence | Event type, actor, ref/SHA, run/job ids, environment, runner, permission set, artifact digests | Disable or hold the workflow/environment and identify what credentials and artifacts it reached |
| Credential and workload identity | Token issued for unexpected repository, ref, workflow, audience, subject, environment, geography, or time; use after job completion | Provider audit event, token claims without the token, principal, target API, source network, decision | Revoke or disable the trust binding, rotate fallback secrets, enumerate actions performed |
| Registry and package | New publisher, maintainer transfer, namespace/source change, yanked/revoked release, unexpected publish, tag/digest movement | Registry event, publisher identity, version, digest, provenance, package contents, downstream consumers | Quarantine the version, stop automation, preserve artifacts, identify exposed consumers |
| Artifact and deployment | Signature/provenance failure, registry digest differs from release record, live runtime digest differs from declared IaC, unexpected rollback | Declared, registry, release, and live digests; verifier output; deploy actor and revision | Halt promotion, isolate the revision, restore the last verified digest, retain the mismatch |
| Privileged-job egress | Destination outside the allowlist, unusual upload volume, DNS/TLS identity mismatch, or write to an unapproved endpoint | Job/run id, process or step, destination, method, byte count, decision, content hash where safe | Stop the job, revoke reachable credentials, preserve network and runner evidence |
| Developer tooling | New IDE extension, agent skill/plugin, hook, package-manager config, credential helper, or local publishing event | Tool identity/version/source, install time, requested capabilities, destinations, affected credentials | Disconnect publishing authority, quarantine the tool, rotate exposed credentials, inspect released artifacts |

Redact secret values while retaining identity, scope, target, timestamps, and
decision data. Store detailed evidence in restricted artifacts; public pull
requests and issues receive counts and locations, not tokens, private source,
or exploit steps.

## Retention

Retention must cover the longest realistic interval between compromise,
detection, release, and downstream adoption. Record the chosen interval and why
it is sufficient. At minimum, retain enough to connect:

- source revision and reviewed change;
- workflow run, runner, and federated identity;
- package/image/artifact digests and attestations;
- registry publish and deployment events;
- alert decision, responder action, and recovery verification.

Test that evidence can be retrieved before relying on its configured retention.
Provider defaults and plan changes can shorten retention silently. Immutable or
write-restricted logs matter most for identities that can also alter the normal
audit destination.

## Common response shape

1. **Contain:** stop the affected publish/deploy path, quarantine mutable tags
   or releases, disable the exact trust binding, and prevent further adoption.
2. **Preserve:** record source, workflow, identity, registry, artifact, runtime,
   and network evidence before cleanup destroys it.
3. **Scope:** walk the attack chain and identify every credential, consumer,
   artifact, environment, and downstream release it could reach.
4. **Eradicate:** remove the malicious input or compromised authority, rotate
   reachable secrets, rebuild on a clean isolated runner, and close the entry
   point.
5. **Recover:** publish or deploy a newly built immutable digest, verify
   signature/provenance/SBOM, reconcile live state, and notify affected
   consumers through the project's disclosure process.
6. **Learn:** record detection and patch-gap timestamps, failed controls,
   owners, due dates, and whether a class-wide control is cheaper than another
   one-off fix.

## Scenario modules

Each repository keeps only the modules its tier and inventory activate. A
playbook names exact local owners and revocation/recovery commands; the prompts
below are the reusable minimum.

### Package takeover

- Which versions, digests, publishers, tokens, and downstream consumers are
  affected?
- Can publishing be disabled without losing evidence?
- Which release is the last verified safe input, and can consumers pin it?
- How are registry tokens rotated and compromised releases marked or removed?

### Dependency confusion

- Which resolver selected the unexpected public or alternate-registry package?
- Which internal names and scopes need reservation?
- Which lockfiles, caches, build outputs, and developer machines consumed it?
- What registry/source constraint prevents recurrence?

### Pipeline credential harvesting

- Which workflow, trigger, runner, checkout, cache, or artifact exposed the
  credential?
- What could the credential publish, deploy, read, or administer?
- Can the long-lived secret be replaced by a subject-constrained workload
  identity before the pipeline is restored?

### Malicious skills or plugins

- Which instruction/configuration files, hooks, tools, destinations, and
  dependencies entered the runtime?
- Which repository, CI, cloud, registry, or organization credentials were
  readable by the process?
- Which workspaces or generated changes require independent review before use?

### Developer workstation or IDE compromise

- Which credential helpers, package-manager credentials, signing keys, browser
  sessions, IDE extensions, agents, or hooks were reachable?
- Which commits, releases, packages, images, or infrastructure changes did the
  workstation authorize?
- Can recovery occur from a known-clean device without importing compromised
  configuration or caches?

### Payment, custody, or signing authority

- What irreversible action remains available, and how is it paused or revoked?
- Which independent approver and recovery authority are outside the compromised
  path?
- Which on-chain, payment-rail, or key-management evidence proves containment?

## Tabletop cadence and record

| Tier | Default cadence | Minimum scenarios |
| --- | --- | --- |
| T0 | On material automation change; no recurring exercise required | Unexpected workflow change when automation exists |
| T1 | Annually when the release is broadly consumed | Package takeover or dependency confusion; compromised publisher |
| T2 | Semiannually | Pipeline credential harvesting; artifact/deployment mismatch |
| T3 | Quarterly | T2 scenarios plus malicious skill/plugin and unexpected agent egress |
| T4 | Quarterly and before a major authority migration | T3 scenarios plus payment/custody/signing-authority recovery |

Record date, scope, participants or roles, starting evidence, decisions,
containment time, recovery proof, missing access/evidence, owners, due dates, and
the next exercise. A tabletop is incomplete until its gaps have owners and
review dates.
