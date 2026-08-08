# Triage, prioritization, and suppression

Scanners produce alerts. Reports contain findings. The distance between the two
is this document.

## Every tool finding is a lead

A lead becomes a finding only when both of these are written down:

- a `file:line` that a reader can open, and
- an attack path from an attacker-controlled input to the impact, naming each
  hop.

If either is missing, the item is either dropped or kept with the
`theoretical — no proof` tag and capped at Medium severity. There is no third
option, and "the scanner said so" is not an attack path.

Promotion is cheap to check and that is the point: a finding written this way
can be disproven by a reviewer in under a minute. Findings that cannot be
disproven quickly are the ones that erode trust in the whole report.

Work in this order for each lead:

1. Read the flagged line and the function around it.
2. Trace backwards to the nearest attacker-controlled input. If the value can
   only originate from a constant, a build-time configuration, or another
   trusted service, the lead is usually dead.
3. Trace forwards to the impact. A tainted value that reaches a sink with no
   security consequence is not a finding.
4. Look for the mitigation the scanner cannot see: a framework-level guard, a
   middleware, a database-level policy, a type that makes the unsafe state
   unrepresentable. Absence of a mitigation is a claim; verify it.
5. Write the record, or drop the lead with a one-line reason.

## Deduplication

Deduplicate by the tuple `(file, line, class)` across every tool, where class
is the CWE rather than the tool's own rule name. Two tools reporting the same
line under different rule names are one finding.

Keep the highest severity instance and merge the evidence, so the surviving
record cites whichever tool gave the clearest trace. Record which tools agreed:
independent agreement is a genuine confidence signal, and disagreement between
a taint-tracking engine and a pattern matcher usually means the pattern matcher
is wrong.

When the same defect appears at many locations because of a repeated idiom,
report it once with the primary location and list the rest as additional
locations. A hundred instances of one mistake is one finding with a hundred
call sites, not a hundred findings.

## Prioritizing known vulnerabilities

For dependency and CVE findings, the CVSS base score alone is a poor ranking
signal — it says nothing about whether anyone is exploiting the issue. Rank on
evidence of exploitation first:

| Rank | Rule |
| --- | --- |
| P0 | The CVE is in the CISA Known Exploited Vulnerabilities catalog. Patch on the catalog's schedule regardless of the CVSS score. |
| P1 | Not in KEV, but EPSS ≥ 0.1 and CVSS ≥ 7. Exploitation is plausible in the near term and the impact is serious. |
| P2 | Not in KEV, EPSS below the P1 threshold, but CVSS ≥ 9. Severe if it is ever weaponized. |
| Backlog | Everything else. Fix it on the normal dependency-update cadence. |

Two data sources, both free and unauthenticated:

```bash
curl -fsSL https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
curl -fsSL "https://api.first.org/data/v1/epss?cve=CVE-2021-44228"
```

Cache the KEV feed for the length of a run rather than fetching it per CVE, and
batch EPSS lookups. Both are point-in-time signals: a P2 today can be a P0 next
week, which is why this ladder is re-run rather than recorded once.

Reachability still outranks all of it. A P0 CVE in a code path the application
never executes is a lower operational priority than a P1 in a request handler,
and saying so explicitly is more useful than a sorted list.

## Suppression

Suppress in this order, and prefer the earliest option that works:

1. **Tune the rule.** The rule is over-broad for this codebase. Fixing it once
   removes the class of noise for everyone and leaves no marker in the source.
2. **Allowlist the path.** Generated code, vendored dependencies, fixtures, and
   test data are legitimate whole-directory exclusions. Do not allowlist an
   application source directory to quiet one alert.
3. **Baseline.** Freeze the current alert set so only new alerts fail, and put
   a review date on the baseline. This is the right move when adopting a tool
   on an existing repository; it is the wrong move as a permanent habit.
4. **Inline suppression, with a mandatory justification string.** The most
   precise and the most expensive: it survives refactors it should not survive
   and nobody rereads it. Require a reason in the comment and reject any
   suppression without one in review.

Every suppression is a decision to accept risk. Review the whole set on a
schedule and delete the ones whose justification no longer parses.

## What may block

A blocking gate above roughly a 20 to 30 percent false-positive rate stops
being a gate: people learn to bypass it, and the true positives go with it.
Keep the blocking set small, near-zero false positive, and unambiguous:

- secrets and hardcoded credentials committed to the repository;
- unsafe deserialization of attacker-controlled data;
- anything the team has explicitly agreed to add after measuring its false
  positive rate on this repository.

Everything else is advisory: it annotates the change, it does not stop it.

Never gate on an unfixable transitive vulnerability. When no upstream fix
exists, blocking the build punishes the person who happened to open the next
pull request and changes nothing about the risk. Track it, document the
compensating control, and gate on the direct dependencies you actually control.

## Anti-noise guardrails

These are the recurring false positives that make security reports easy to
ignore. Do not report them:

- **Absent TLS in a local development context.** A development server bound to
  a loopback interface, a docker-compose file for local use, a test fixture —
  none of these are transport-security findings. Check the context before
  reporting a missing certificate.
- **HSTS as a casual recommendation.** `Strict-Transport-Security` with a long
  max-age is difficult to reverse and has taken sites offline when a subdomain
  or a certificate was not ready. Recommend it only where the deployment is
  understood, and always with the rollout consideration attached.
- **Sequential identifiers, reported without the access-control finding.** A
  sequential integer key is an enumeration convenience, not a vulnerability;
  the vulnerability is the missing authorization check. Prefer UUIDs for
  publicly addressable resources, say so as hardening, and report the missing
  check as the actual finding.

More generally, before reporting anything that resembles a configuration
default, ask what the deployment context is. A finding that would be wrong in
half of all repositories is a finding that should have been a question.
