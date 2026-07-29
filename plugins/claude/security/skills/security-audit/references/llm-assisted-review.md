# Where LLM-assisted review wins and where it loses

The honest summary: a model is very good at deciding whether a deterministic
tool's alert is real, and unreliable at finding vulnerabilities on its own.
Everything below follows from that asymmetry.

## The evidence

| Result | Source |
| --- | --- |
| LLM triage over deterministic scanner output removed 94 to 98 percent of false positives while preserving recall, measured on 433 real alarms. | arXiv 2601.18844 (Tencent, January 2026) |
| CWE-specific prompts combined with flow-sensitive traces reach F1 0.912 on the OWASP Java Benchmark. CWE-specialized prompting consistently beats generic prompting. | ZeroFalse, arXiv 2510.02534 |
| LLM-guided CodeQL found 69 vulnerabilities on CWE-Bench-Java against CodeQL's 27, with a 5.21 percentage-point lower false-discovery rate. | IRIS, ICLR 2025, `iris-sast/iris` |
| Standalone LLM scanning: 15 to 46 percent false-positive rates across frontier models, 50 to 65 percent recall, and no model reporting consistently across three identical runs. | arXiv 2605.23243, arXiv 2606.21397 |
| Best agent scores 58 percent on SEC-bench Pro. | arXiv 2605.26548 |

Read those rows together rather than separately. The first three measure a
model applied to output that a deterministic engine produced; the last two
measure a model asked to find the bugs itself. The gap between them is not
about model quality, it is about what the model is being asked to do.

## Why the asymmetry

Triage is a bounded verification task. The alert names a location, a rule, and
usually a trace. The model reads the surrounding code and answers a closed
question — is this reachable, is there a mitigation, does the sink matter — and
closed questions are where models are strongest. There is also a ground truth
to check against: the code either has the guard or it does not.

Discovery is an unbounded search. Nothing tells the model where to look, so
coverage becomes a function of what fit in the context window and what the
sampling happened to surface. That is exactly the shape of the instability the
2026 measurements found: not that the model is wrong, but that it is different
each run, which makes it unusable as a gate. A check that passes and fails on
identical input teaches people to rerun until it passes.

## How to use it

Use the model as a triage layer over deterministic output. Run the scanners
first, then have the model verify each alert against the code, promote the ones
with a real attack path, and drop the rest with a written reason. This is the
configuration with the strongest evidence behind it and the one the audit
workflow in this skill is built around.

Use the model as a diff-scoped reviewer for the classes rules cannot express:
authorization and IDOR, multi-step business flows, invariant violations,
trust-boundary changes. A rule engine cannot know which resource belongs to
which tenant; a model reading the diff and its surroundings can at least ask.
Keep it advisory.

Specialize the prompt by CWE. The ZeroFalse result is the most directly
actionable of the five: asking "is this a SQL injection, given this trace" beats
asking "is this a vulnerability" by a wide margin, and it costs nothing to do.
Give the model the flow, not just the line.

## What not to do

Never make an LLM verdict a blocking gate. Run-to-run instability means the
same commit passes and fails, and the first time that happens the gate loses
its authority permanently.

Never use a model as the primary scanner. At 50 to 65 percent recall it misses
between a third and a half of what it is looking for, and unlike a rule engine
it cannot tell you what it did not check. The deterministic tools define
coverage; the model improves precision within it.

Never report a model's output as a clean bill of health. "The model found
nothing" is a statement about one sampling run, not about the code.
