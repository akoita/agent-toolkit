---
name: security-review
description: >-
  Review a diff or pull request for security-relevant changes and return
  falsifiable, inline, advisory comments. Use when the unit of work is a change
  — a branch, a pull request, staged edits — and the question is whether it
  introduces risk. Do not use as a blocking gate, for a whole-repository audit
  (use security-audit), for running the deterministic toolchain (use
  security-scan), or for dependency, threat-model, smart-contract, or
  AI-system questions that have their own skill.
---

# Diff-scoped security review

This review is fast, narrow, and advisory. It targets the classes a rule engine
cannot express — authorization, business flows, invariants — and it is never a
gate. Run-to-run instability makes a model verdict unfit to block a merge, and
the first time a gate fails on a commit that passed an hour ago it loses its
authority for good. Say what you found, cite where, and let a human decide.

## Establish the diff

```bash
git fetch origin main
git diff --name-only --diff-filter=ACMR origin/main...HEAD
git diff origin/main...HEAD
```

Triple-dot, not two-dot. `origin/main...HEAD` diffs against the merge base and
shows what this branch changed; `origin/main..HEAD` also shows everything that
landed on main since the branch started, which for a pull request is somebody
else's work. Reviewing the two-dot diff wastes the budget on unrelated code and
produces comments that confuse the author.

`--diff-filter=ACMR` drops deletions and keeps added, copied, modified, and
renamed files. When the change is not yet committed, review `git diff HEAD` or
`git diff --staged` instead and say which you used.

## What to prioritize

A diff review has a small budget, so spend it where rules are blind and impact
is high, in roughly this order:

1. **Authorization and IDOR.** A new or changed handler that takes a resource
   identifier: does anything verify that the caller owns it? This is the single
   highest-yield question in diff review, and static rules cannot answer it
   because ownership is domain knowledge.
2. **Multi-step business flows.** A change to one step of a checkout, transfer,
   approval, or provisioning sequence. Ask what happens if the steps run out of
   order, twice, or concurrently.
3. **Invariant violations.** A balance that must not go negative, a state
   machine that must not skip, a total that must equal the sum of its parts.
   Find the invariant the code assumes and ask whether the diff can break it.
4. **Trust-boundary changes.** Data crossing from untrusted to trusted, a
   validation moved or removed, a new deserialization point, a new template or
   query built from a request value.
5. **New external calls.** Outbound requests to a URL derived from input are
   server-side request forgery until proven otherwise; note that OWASP
   Top 10:2025 folds SSRF into A01. Also check timeouts, retry behavior, and
   what happens to the response.
6. **New dependencies.** Any addition to a manifest or lockfile. Who publishes
   it, how old is the release, and does it run install scripts.
7. **Authentication changes.** Session lifetime, token validation, password and
   credential handling, multi-factor logic, anything touching a comparison of
   secrets.
8. **Secrets handling.** New configuration keys, values that look like
   credentials, logging that might now include a token.
9. **CI workflow files.** A change under a workflow directory is a change to
   something that runs with repository credentials. Treat it as production
   code: check trigger types, permissions, and any use of untrusted input in a
   shell step.

## Read the surrounding context

A diff that looks safe in isolation can be unsafe in place. Open the whole
changed function and its callers, not just the hunk:

- a removed line three functions away can be the guard that made the changed
  line safe;
- a renamed variable can silently change which value reaches a sink;
- a new early return can skip a check that used to run on every path;
- a changed default in a shared configuration object can weaken every caller.

When the diff removes or moves code, ask what that code was doing. Deletions
are filtered out of the file list above but they are still in the patch, and a
deleted validation is the most commonly missed finding in diff review.

## OWASP Top 10:2025 as the checklist frame

Use it as a coverage frame at the end of the pass, not as a script at the
start. It answers "what did I not look for", which is the question a diff
review usually gets wrong.

| ID | Category |
| --- | --- |
| A01 | Broken Access Control — now absorbs SSRF |
| A02 | Security Misconfiguration |
| A03 | Software Supply Chain Failures — new in 2025 |
| A04 | Cryptographic Failures |
| A05 | Injection |
| A06 | Insecure Design |
| A07 | Authentication Failures |
| A08 | Software and Data Integrity Failures |
| A09 | Security Logging and Alerting Failures |
| A10 | Mishandling of Exceptional Conditions — new in 2025 |

For an API surface, the OWASP API Security Top 10 is still the 2023 edition;
there is no newer list, so cite it as 2023 rather than implying it tracks the
2025 web list.

## Output

Write inline comments, one per finding, anchored to a `file:line` in the diff.
Every comment carries a concrete exploit path a human can disprove in seconds:
who the attacker is, what they send, which line accepts it, and what they get.

```text
`app/api/invoices.ts:42` — the handler loads the invoice by the `id` path
parameter and returns it without comparing `invoice.orgId` to the session's
organization. An authenticated user of any tenant can read another tenant's
invoice by incrementing the identifier. The neighbouring `getOrder` handler
does this check on line 88.
Severity: High. Confidence: High. CWE-639.
```

Falsifiable means a reviewer can look at one line and say "no, the middleware
on line 12 handles that." Comments that cannot be checked that fast are the
ones that get resolved without being read. If you are not sure, say what you
could not determine and what would settle it — that is a useful comment, and a
confident wrong one is not.

Silence is a valid result. When the diff has no security-relevant change, say
so plainly and stop: "No security-relevant change. The diff touches formatting
and test fixtures; no trust boundary, authorization path, or dependency is
affected." Do not manufacture an Informational finding to look thorough. A
review that always finds something is a review nobody reads.

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

Three guardrails matter especially here, because a diff invites them. Do not
report absent TLS in a local development context. Do not casually recommend
HSTS; it is hard to reverse and has taken sites offline. Do not report a
sequential identifier as a vulnerability — prefer UUIDs for public resources as
hardening, and report the missing authorization check as the finding.
