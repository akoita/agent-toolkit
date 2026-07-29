# Severity, evidence, and the report contract

This is the canonical contract for every security skill in this plugin. A
finding that does not fit this shape is not ready to report. The last section
is a condensed restatement that other skills copy inline so they stay
self-contained.

## Severity

Severity describes impact and reachability, nothing else. It is not a measure
of how confident you are, not a measure of how easy the fix is, and not a
measure of how much the finding annoys you.

| Severity | Decision rule |
| --- | --- |
| Critical | An unauthenticated attacker who can reach the system compromises it or its data outright — remote code execution, authentication bypass, mass extraction of sensitive records — and every precondition is under the attacker's control. |
| High | Serious impact — privilege escalation, cross-tenant or cross-user access, exposure of sensitive data, silent integrity loss — behind a precondition the attacker normally holds, such as an ordinary authenticated account, or a non-default configuration that is nevertheless common. |
| Medium | Real impact behind a meaningful precondition: a privileged position, user interaction, a race the attacker cannot reliably win, or a configuration that is not the default. Also the correct level for a missing control where exactly one other failure would make it exploitable. |
| Low | Limited impact, or exploitable only by a principal who already holds the privilege the issue would grant. Information disclosure with no downstream use lands here. |
| Informational | Hardening, hygiene, and standards gaps with no demonstrated impact. Never blocks anything, and is reported in a separate section so it does not dilute the rest. |

Two rules keep the ladder honest. Rate the finding you can prove, not the one
you suspect: if reachability is unproven, the finding is at most Medium and
carries the theoretical tag. And rate each finding on its own — do not inflate
one because several of the same class exist. Repetition is a pattern to call
out in the summary, not a severity multiplier.

## Confidence

Confidence is reported separately and never averaged into severity. "Critical
severity, Low confidence" and "Critical severity, High confidence" call for
different actions, and collapsing them into one number destroys that.

| Confidence | Decision rule |
| --- | --- |
| High | The path was read end to end. Source and sink are both in this repository, every hop was inspected, and no mitigating control was found where one could be. |
| Medium | The path is plausible and mostly traced, but at least one link is inferred from framework or library behavior rather than read in this repository. |
| Low | A pattern match, or the reachability depends on code, configuration, or deployment topology that is not in this repository. |

Never present a Low-confidence item as a fact. Write what would raise it: the
file that was not available, the runtime configuration that was not observed,
the test that would settle it.

## The finding record

Every finding carries all of these. Missing fields are stated as unknown, not
omitted.

- **id** — stable across runs so the same issue can be recognized after the
  code moves. Derive it from the CWE and the normalized primary location, for
  example `CWE-89-app-db-query-executeRaw`, not from a line number alone.
- **title** — one line, specific. "Missing tenant check on the invoice export
  endpoint", not "Broken access control".
- **severity** — one of the five levels above.
- **confidence** — one of the three levels above, reported beside severity.
- **cwe** — the CWE identifier and name. Use one; if two genuinely apply, name
  the one that describes the root cause rather than the symptom.
- **locations** — one or more `file:line` references. The first is the primary
  location where the fix belongs; the rest are the supporting hops.
- **preconditions** — what the attacker must already have. Network position,
  an account, a role, a specific configuration, a race window, user
  interaction. "None" is a strong claim; make it deliberately.
- **attack path** — prose from an attacker-controlled input to the impact,
  naming each hop with its location. This is the field that separates a finding
  from a lead, and it is the field reviewers read first.
- **impact** — what the attacker gains in the terms this system cares about:
  which records, whose data, what privilege, what downtime.
- **evidence** — the code excerpt that demonstrates the claim, quoted with its
  file and line range. Quote enough to be checkable and no more.
- **recommendation** — the specific change, at the specific location, with the
  invariant it restores. Not "validate input" but which check, where, and what
  it must reject.
- **tags** — free-form, but one is mandatory: mark the finding
  `theoretical — no proof` when there is no demonstrated path from an
  attacker-controlled input to the impact.

The theoretical tag is not a disclaimer to sprinkle everywhere. Use it exactly
when the code pattern is present but reachability, exploitability, or the
absence of a mitigating control could not be established. A report where every
finding is tagged theoretical is a report that has not been triaged.

## The report skeleton

1. **Executive summary** — what was examined, the headline risk in two or three
   sentences, and the counts by severity. Written so someone who reads nothing
   else is not misled.
2. **Scope and what was not covered** — the paths, branches, and commit
   examined; the components deliberately excluded; the components that could
   not be reached, with the reason. Absence of findings in an uncovered area is
   not evidence of safety and this section is where that is stated.
3. **Findings by severity** — Critical first, Informational in its own trailing
   section. One record per finding, in the shape above.
4. **Tool coverage** — a table of every tool with its version, what it ran
   against, its exit code, and its finding count. Tools that were absent appear
   here with their install command, so the reader can see the gap.
5. **Assumptions** — the deployment, trust, and configuration assumptions the
   analysis rests on. Each one is a place the conclusions change if it is wrong.
6. **Open questions** — what a human needs to answer, phrased so it can be
   answered without rereading the whole report.

A report with no findings still needs sections 2, 4, 5, and 6. "Nothing found"
is only meaningful next to what was searched and with what.

## Artifact handling

Scan artifacts contain source excerpts, credential material, and step-by-step
exploit instructions. Treat them as sensitive output, not as build output.

- Write them outside the working tree and outside any enclosing git worktree,
  under a private directory (`chmod 700` on macOS and Linux).
- Never add them to the index and never attach them to a pull request or an
  issue by default. Publishing them is a decision a human makes explicitly,
  after reading them.
- In CI, keep them in restricted-access job artifacts and post only counts and
  locations to the pull request.
- When a finding must be discussed in a public place, discuss the location and
  the class, not the working exploit.

## Restate this inline

Copy this block into any skill that does not ship this file, so it carries the
contract without referencing a path outside its own directory.

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
