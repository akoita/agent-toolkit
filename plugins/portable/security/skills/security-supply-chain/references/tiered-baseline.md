# Tiered cross-project supply-chain baseline

This baseline turns a long control catalog into a proportionate starting point.
It is additive: assign the highest tier that describes the repository, inherit
every lower tier, then evaluate the conditional controls triggered by the
actual build and release surface.

The source input is Google Threat Intelligence Group's 30 July 2026 article,
[Batten Down Your Packages — Mitigation Guidance for Supply Chain
Compromise](https://cloud.google.com/blog/topics/threat-intelligence/mitigation-guidance-for-supply-chain-compromise?hl=en).
The article motivates inventory across applications, services, dependencies,
vendors, developer tooling, CI/CD, packages, and artifacts; strong CI identity
and isolation; provenance; monitoring; and rehearsed response. The T0–T4
taxonomy, control ids, minimum matrix, priorities, and cadence below are
agent-toolkit's project-agnostic adaptation for small repositories. They are
engineering judgment, not claims made verbatim by Google.

## Assign one additive tier

| Tier | Repository shape | Additive consequence |
| --- | --- | --- |
| T0 — docs-only | Documentation, examples, or static content with no published executable package, image, deployment, or privileged automation | Establish ownership and inventory; harden any workflow that still runs |
| T1 — library/tooling | A package, CLI, build tool, action, plugin, or other executable consumed by someone else | Add dependency intake, release inventory, SBOM/ABOM, and release integrity |
| T2 — deployed service | A service, scheduled job, image, or infrastructure definition deployed to an environment | Add federated deployment identity, isolated privileged jobs, immutable deployment, reconciliation, and operational response |
| T3 — agent/MCP | An agent, MCP server/client, skill, plugin, or model-driven runtime that reads untrusted content or invokes tools | Add executable-instruction inventory, restricted build/release boundaries, agent/plugin incident scenarios, and tighter review cadence |
| T4 — payment/custody/smart contract | A payment, custody, signing-key, funded-session, account-abstraction, or smart-contract surface where compromise can irreversibly move value or authority | Add independent release approval, strongest identity and artifact verification, class-specific response, and quarterly exercises |

Use the highest applicable tier even when the higher-risk component is a small
subdirectory. Scope may be narrowed to that component only when the trust
boundary is explicit and lower-tier automation cannot publish or deploy it.
Record that boundary as evidence.

## Stable control catalog

| ID | Control | Evidence that can prove it |
| --- | --- | --- |
| SC-INV-01 | Tiered inventory of repositories, services, packages, images, deployment targets, vendors, and development tools | Profile plus paths to manifests, workflows, registries, IaC, and owner records |
| SC-VCS-01 | Reviewed, attributable changes to workflows, release policy, and protected branches or equivalent merge controls | Repository settings export and reviewed change history |
| SC-CI-01 | Least-privilege permissions, safe triggers, and checkout credentials disabled unless required | Workflow `file:line` evidence and workflow-linter output |
| SC-CI-02 | Short-lived federated identity for publish/deploy, bound to repository, workflow, ref, and environment | Identity-provider policy, workflow permissions, token claims, and negative test |
| SC-CI-03 | Single-use privileged runner or equivalent isolation, fresh source/workspace, and restricted egress | Runner configuration, job boundaries, network policy, and test evidence |
| SC-BUILD-01 | External Actions, reusable workflows, container base images, and privileged build utilities resolve to reviewed immutable commits or digests | Validated ABOM, source annotations, and update-review evidence |
| SC-DEP-01 | Immutable lockfile installs, disabled install scripts by default, and explicit build-script exceptions | Package-manager config, lockfiles, CI commands, and exception register |
| SC-DEP-02 | SCA plus disposition policy for vulnerable, malicious, abandoned, new, provenance-missing, and maintainer-transferred inputs | Scanner coverage and adoption records using the dependency-intake policy |
| SC-ABOM-01 | Generated Action Bill of Materials for actions, reusable workflows, composite actions, build images, and build utilities | Validated ABOM tied to a source revision |
| SC-SBOM-01 | Release-generated SBOM from the built artifact or locked dependency graph | SBOM digest, generator invocation, release association, and coverage check |
| SC-PROV-01 | Signed build provenance and identity-constrained consumer verification | Attestation plus verification output bound to the intended workflow identity |
| SC-DEPLOY-01 | Deployment by immutable digest with declared, registry, and live-state reconciliation | IaC reference, registry digest, runtime digest, signature/provenance checks |
| SC-MON-01 | Monitoring for workflow changes, unusual triggers, credential use, and privileged-job egress | Retained audit events, alert rules, routing, and an exercised response record |
| SC-IR-01 | Scenario playbooks and tabletop cadence matched to the repository tier | Playbooks, exercise date, participants, gaps, owners, and due dates |
| SC-AI-01 | Agent/skill/plugin inputs treated as executable content with declared destinations and dependencies | Inventory, review evidence, scanner evidence, and capability boundaries |
| SC-T4-01 | Independent approval and recovery controls for irreversible value or signing authority | Approval rule, key/authority boundary, pause/revocation procedure, exercise evidence |

## Minimum-control matrix

`R` means required for the tier. `C` means required when the named surface
exists. `—` means the control is not a baseline minimum, though a project may
adopt it. A `C` disposition must say whether the trigger exists and cite the
evidence.

| Control | T0 | T1 | T2 | T3 | T4 |
| --- | --- | --- | --- | --- | --- |
| SC-INV-01 | R | R | R | R | R |
| SC-VCS-01 | C: automation exists | R | R | R | R |
| SC-CI-01 | C: workflows exist | R | R | R | R |
| SC-CI-02 | — | C: publish uses credentials | R | R | R |
| SC-CI-03 | — | C: privileged release job | R | R | R |
| SC-BUILD-01 | C: automation or external build input exists | R | R | R | R |
| SC-DEP-01 | — | R | R | R | R |
| SC-DEP-02 | — | R | R | R | R |
| SC-ABOM-01 | C: workflows exist | R | R | R | R |
| SC-SBOM-01 | — | R | R | R | R |
| SC-PROV-01 | — | C: signed or executable release | R | R | R |
| SC-DEPLOY-01 | — | — | R | R | R |
| SC-MON-01 | C: automation exists | C: publish exists | R | R | R |
| SC-IR-01 | — | C: widely consumed release | R | R | R |
| SC-AI-01 | — | C: agent artifact is shipped | C: agent runtime exists | R | R |
| SC-T4-01 | — | — | — | — | R |

## Adoption record

Start with `../assets/repository-baseline.template.json`. One record exists per
catalog control so the validator can distinguish tier requirements, conditional
triggers, and controls that are genuinely out of tier. A completed record
contains:

- a stable `control_id`;
- `required`, `conditional-triggered`, `conditional-not-triggered`, or
  `out-of-tier` applicability with trigger evidence;
- `adopt`, `adapt`, `reject`, `already-covered`, or `not-applicable`;
- a decision rationale and any compensating controls;
- non-empty evidence, including negative evidence for a conditional control
  whose trigger is absent;
- expected risk reduction and operating cost;
- prerequisites, owner, and review cadence;
- the failure mode that could leave the attack path open.

`not-applicable` is valid only for an untriggered conditional or an out-of-tier
control; it is not a synonym for `reject`. `already-covered` credits an existing
control and still requires evidence. `adapt` names the local variation.
`reject` states why the control is disproportionate and names at least one
inherited or compensating control that bounds the risk.
Do not turn a standards gap into a vulnerability finding without a reachable
attack path.

## Roadmap priorities

| Priority | Outcome | Default controls |
| --- | --- | --- |
| P0 — cheap chain breakers | Remove mutable and over-privileged inputs before adding machinery | SC-INV-01, SC-VCS-01, SC-CI-01, SC-BUILD-01, SC-DEP-01, the deterministic parts of SC-DEP-02 |
| P1 — release integrity and response | Make releases attributable, verifiable, deployable by digest, observable, and recoverable | SC-CI-02, SC-ABOM-01, SC-SBOM-01, SC-PROV-01, SC-DEPLOY-01, SC-MON-01, SC-IR-01 |
| P2 — advanced isolation and assurance | Reduce privileged execution blast radius and exercise high-impact recovery | SC-CI-03, SC-AI-01, SC-T4-01, stronger builders or isolation where evidence justifies them |

Within a priority, fix the earliest reachable step in an attack chain first.
For example, removing a long-lived deployment key has priority over adding a
dashboard that detects its later misuse.

## Review cadence

| Evidence | T0 | T1 | T2 | T3 | T4 |
| --- | --- | --- | --- | --- | --- |
| Tier, inventory, and applicability | Annually and on scope change | Semiannually and on new release surface | Quarterly and on new deployment | Quarterly and on new tool/capability | Quarterly and on authority/value-flow change |
| Dependency and ABOM review | When automation changes | Each release plus monthly update review | Each release plus monthly review | Each release plus monthly review | Each release plus monthly review |
| Identity, runner, and egress review | When automation changes | Semiannually if privileged | Quarterly | Quarterly | Quarterly and after each incident |
| Playbook/tabletop | Not required | Annually when broadly consumed | Semiannually | Quarterly | Quarterly and before a major authority migration |

Repository events override the calendar: re-evaluate immediately after a
maintainer transfer, workflow privilege change, new registry or deployment
target, credential incident, package takeover, or trust-boundary expansion.

## Explicit scale-based rejects

These are rejects as universal minimums, not statements that the controls have
no value:

- Do not require dedicated self-hosted runners for small projects. Prefer
  provider-hosted single-use jobs; a poorly maintained persistent runner is a
  regression.
- Do not require SLSA Build L3 everywhere. Identity-constrained Build L2 is the
  default; adopt L3 when a consumer, threat model, or T4 authority justifies the
  added builder complexity.
- Do not block on package age, popularity, missing optional provenance, or
  maintainer count alone. They are review signals, not proof of compromise.
- Do not require live deployment reconciliation for T0 or T1 repositories that
  have no deployment target.
- Do not require quarterly exercises for an inactive T0 repository. Exercise
  cadence begins where publishing, deployment, agent capability, or irreversible
  authority creates a response path worth rehearsing.
- Do not duplicate project-specific owners, secrets policy, exceptions, or
  rollout state in a shared baseline. Keep those in the consuming repository.
