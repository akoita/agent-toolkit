# Security context and review knowledge base

Security review is more accurate when a component explains its trust boundary
before discovery starts. Context narrows the review; it never substitutes for
evidence from the implementation.

## Source and adaptation

**Direct source claim.** The Chrome Security Team says its vulnerability
discovery harness uses prior CVEs, Chrome's Git history, focused `SECURITY.md`
files, repeated analysis, and a separate-context critic. Its public FAQ says a
directory-level `SECURITY.md` can describe security boundaries so automated
tools filter reports that assume impossible attacks.

- Chrome Security Team, 30 July 2026:
  https://blog.google/security/chrome-stronger-with-every-update/
- Chromium, *AI-generated security bugs FAQ*, April 2026:
  https://chromium.googlesource.com/chromium/src/+/main/docs/security/ai-generated-security-bugs-faq.md

**Scaled adaptation in this skill.** Small projects do not need Chrome's full
history-indexing or multi-model infrastructure. They need a short, maintained,
source-backed context pack for the paths under review. The requirements below
are this skill's adaptation, not claims that Chrome prescribes this exact file
layout.

## Root disclosure policy versus nested engineering context

These files may share the name `SECURITY.md`, but they serve different readers.

| Location | Purpose | Must contain |
| --- | --- | --- |
| Repository root | Public vulnerability disclosure policy | Supported versions, private reporting channel, response expectations, safe-harbor or disclosure expectations where applicable |
| At or above a trust boundary | Engineering and reviewer context | Assets, attacker-controlled inputs, privileges, trust assumptions, invariants, expected controls, unsafe operations, ownership and tests |

Do not put exploit details, active incident data, credentials, or private
reporter information in either file. A nested file must not redirect external
reporters or silently redefine the root disclosure policy. A root policy alone
does not explain a component's security invariants.

Use `../assets/trust-boundary-SECURITY.template.md` for nested engineering
context. Place it at the narrowest directory whose descendants share the same
boundary. A more specific nested file overrides broader engineering context
only where it says so explicitly.

## Context loading order

Before discovery, collect only what affects the in-scope attack paths:

1. The audit scope, branch, commit, exclusions, deployment shape, and data
   classification.
2. The root disclosure policy and every applicable nested engineering
   `SECURITY.md` from repository root to the in-scope path.
3. The current threat model or architecture document, with its revision or
   commit.
4. Prior confirmed findings, CVEs, incidents, and accepted risks for the same
   component. Keep private reports outside the worktree and summarize only the
   minimum non-sensitive lesson.
5. Relevant history for privileged paths: introductions of security controls,
   reversions, migrations, and ownership changes. Do not ingest the entire Git
   history by default.
6. The tests and runbooks that claim to enforce or recover the documented
   invariants.

Record each item in a context manifest with:

- source path or stable URL;
- commit, version, or retrieval date;
- component and boundary covered;
- owner;
- sensitivity and whether it may be sent to an external model;
- the claim it is being used to support;
- last validation date.

If a document conflicts with code, the implementation is evidence of current
behavior and the document is stale. Report the documentation mismatch as
context unless it creates a reachable security failure of its own.

## Minimum useful knowledge base

A knowledge base earns its place when it changes a test, a hypothesis, or a
triage decision. Keep these entries:

- **Boundary cards:** component, assets, untrusted inputs, privileges,
  authorized callers, and external dependencies.
- **Security invariants:** falsifiable statements such as “tenant identity is
  taken only from the verified session, never the request body.”
- **Historical lessons:** root cause, affected boundary, structural mitigation,
  regression test, and whether the lesson remains applicable.
- **Known exceptions:** owner, expiry, compensating controls, and a link to the
  approval record.
- **Ownership:** human owner or maintainer role for reproduction and remediation.

Exclude generic secure-coding prose, raw scanner dumps, unverified model
claims, and history unrelated to the scoped boundary. They consume context
without improving a decision.

## Use during review

Turn every invariant into an attempted falsification. For each claimed
mitigation, identify the implementing `file:line`, configuration, or test.
Treat missing or stale context as an uncertainty that guides review depth, not
as proof of a vulnerability.

A model-generated candidate still has to meet the finding contract: reachable
attacker input, sink or security decision, missing mitigation, concrete impact,
and file-and-line evidence. Agreement with a knowledge-base statement is not
proof.

## Maintenance proportional to project size

- A static or documentation-only repository may need only the root disclosure
  policy and a short note stating that it has no runtime trust boundary.
- A library should document unsafe APIs, parsing boundaries, generated code,
  release authority, and compatibility constraints.
- A deployed service should add identities, data stores, network boundaries,
  administrative paths, and deployment ownership.
- Agent, payment, custody, and smart-contract components should use focused
  files near each privileged boundary and review them when the boundary changes.

Review focused context when a privileged interface changes, after an incident,
or at least annually for an active high-impact component. Delete obsolete
entries instead of letting contradictory context accumulate.
