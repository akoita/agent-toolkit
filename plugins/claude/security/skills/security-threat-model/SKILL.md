---
name: security-threat-model
description: >-
  Build a repository-grounded threat model: extract the system model from the
  code, derive trust boundaries, assets and entry points, calibrate attacker
  capabilities, enumerate abuse paths, rank them by likelihood and impact, and
  separate existing mitigations from recommended ones. Use for threat
  modeling, attack surface analysis, trust boundary review, abuse path
  enumeration, STRIDE or LINDDUN design review, and model-as-code with pytm or
  threagile, including systems that contain AI agents. Do not use to find
  concrete vulnerabilities in code (use security-audit for a repository audit
  or security-review for a diff), to run scanners (use security-scan), or for
  the detailed LLM, agent, and MCP control checklists (use security-ai).
---

# Threat modeling from the repository

A threat model is only useful if it describes the system that is actually
checked in. The failure mode of this work is a plausible diagram of a system
nobody built, ranked by severities nobody can justify. The procedure below
exists to prevent that: every component, flow, and control has to come from the
code, and the ranking has to survive a conversation with the user.

Two commitments run through all of it. **Evidence or silence** — do not claim a
component, data flow, or control without a `file:line`. And **the model is
small on purpose** — a short list of well-argued abuse paths beats an
exhaustive matrix that nobody reads.

## Finding contract

This restates the contract owned by the `security-audit` skill. Read that skill
for the long form, triage policy, and suppression rules.

Severity is `Critical`, `High`, `Medium`, `Low`, or `Informational`, and it
describes impact and reachability only. Report confidence separately — `High`
when the path was read end to end, `Medium` when a hop is inferred from
framework behavior, `Low` for a pattern match or a path that leaves this
repository — and never fold confidence into
severity to make a weak item look serious or a strong one look tentative.

Every threat is one record with a stable id (so it survives across runs), a
title, severity, confidence, a CWE where one applies, a `file:line`, the
preconditions the attacker needs, the attack path in prose, the impact if it
succeeds, the evidence supporting each step, and a recommendation naming the
exact component, boundary, or entry point to change. A threat whose attack path
cannot be walked end to end carries an explicit `theoretical — no proof` tag in
its title.

Every tool finding is a lead, not a finding. A generated STRIDE row, a
`threagile` risk rule hit, or a category suggested by a model is a lead. It is
promoted only when it has a written attack path and a `file:line`; otherwise it
is tagged theoretical or dropped. In threat modeling almost everything starts
theoretical, so the tag is normal rather than a mark of failure — what is not
acceptable is an untagged threat with no code behind it.

## Procedure

### 1. Scope and extract the system model

Identify the primary components, data stores, and external integrations, and
record how each part runs: long-lived server, background worker, frontend, CLI,
scheduled job, CI pipeline.

Separate **runtime** from **build and development tooling** and keep them
separate for the rest of the model. They have different attackers, different
trust boundaries, and different blast radii, and merging them is the most
common reason a threat model produces useless rankings.

Do not claim a component, flow, or control without evidence in the code. Cite
`file:line` for each one. If something is inferred from a deployment manifest
or a README rather than from code, say which.

### 2. Derive trust boundaries, assets, and entry points

A trust boundary is any place where data or control crosses between parties
with different privilege. For each one, record:

| Property | Question |
| --- | --- |
| Protocol | What crosses, in what format? |
| Authentication | Who is the caller, and how is that established? |
| Encryption | In transit and at rest, with what? |
| Validation | What is checked, where, and against what schema? |
| Rate limiting | What stops volume abuse or brute force? |

A missing answer is a finding candidate, not an assumption to fill in.

Assets are credentials, signing and encryption keys, customer data, and
anything whose disclosure, corruption, or unavailability costs money or trust.
Entry points are every place an outside party can introduce data or trigger
execution: HTTP routes, queue consumers, webhook receivers, file uploads, CLI
arguments, environment and configuration, and CI triggers.

### 3. Calibrate attacker capabilities

Write down what an attacker realistically has, based on the exposure you found
in step 2 — unauthenticated internet access, an authenticated low-privilege
account, a tenant neighbour, a compromised dependency, a malicious pull
request, a stolen CI token.

Then explicitly state the **non-capabilities**. Uncalibrated models inflate
every severity, because any threat is critical if the attacker is allowed to
already have the database. Naming what the attacker does not have is what makes
the ranking in step 5 defensible.

### 4. Enumerate threats as abuse paths

Map attacker goals onto assets and boundaries and write each threat as a path:
the attacker starts here, crosses this boundary, abuses this weakness, reaches
this asset. Use STRIDE per component or per data flow to drive breadth (see
`references/method-prompts.md`).

Keep the list small and high quality. Ten paths that a reviewer can argue with
are worth more than eighty rows generated from a matrix.

### 5. Prioritize by likelihood and impact

Qualitative is fine and usually better than a false-precision score. Give each
threat a likelihood and an impact with a one-line justification tied to the
capabilities from step 3. Where two threats tie, rank by how cheap the
mitigation is — that is the ordering the team will actually follow.

### 6. Validate assumptions with the user, then pause

Summarize the assumptions that drive the ranking and ask **one to three**
targeted questions. Cover, in this order of usual value:

1. deployment model and internet exposure;
2. authentication and authorization expectations;
3. data sensitivity and regulatory status;
4. multi-tenancy and the tenant isolation expectation.

**Pause for an answer before producing the final report.** This step is the
difference between a threat model and a guess: the code shows what exists, but
not what the team believes it is protecting.

If the user cannot answer, say which assumptions remain open, which threats
depend on each, and how the ranking would move under the alternative. Do not
silently pick the pessimistic reading.

### 7. Recommend mitigations

Separate **existing** mitigations, each with the `file:line` that proves it,
from **recommended** ones. Conflating them is how a report ends up telling a
team to build something they already have.

Tie every recommendation to a concrete component, boundary, or entry point.
Prefer "enforce a schema on the multipart body at the upload endpoint in
`handlers/upload.py:41`" over "validate inputs". A recommendation that could
be pasted into any repository is not a recommendation.

### 8. Quality check, then report

Before writing the final report, confirm:

- every entry point found in step 2 is covered by at least one threat or an
  explicit note saying why it is not interesting;
- every trust boundary is represented;
- runtime and build/development concerns are still separated;
- the user's step 6 clarifications are reflected in the ranking, not just
  appended;
- assumptions and open questions are stated explicitly, not buried.

## Choosing a method

| Method | Use it for | Cost |
| --- | --- | --- |
| **STRIDE** | Per-component and per-data-flow design review. The default | Low; the cheapest method to assist with a model |
| **LINDDUN GO** | Privacy threats, card-deck format | Low |
| **LINDDUN PRO** | Privacy, full per-data-flow analysis | High; skip for a small team |
| **Attack trees** | One high-value asset, explored in depth | Medium |
| **PASTA** | Enterprise programs with dedicated staff | Wrong for a small team |

STRIDE first. Add LINDDUN GO when personal data is central to the product. Use
an attack tree when a single asset — a signing key, a treasury, a customer
database — dominates the risk. Do not reach for PASTA: it is a seven-stage
process with business impact analysis and threat intelligence stages that a
small team cannot feed, and an unfed process produces worse output than STRIDE.

## Model as code

Check the model into the repository and regenerate it when the architecture
changes. A threat model that is not in version control is stale within a
quarter.

**`pytm` v1.4.0** (`OWASP/pytm`; `izar/pytm` is the old mirror) is the default.

```bash
pip install pytm          # needs Python >= 3.11 and graphviz
./tm.py --json
./tm.py --dfd | dot -Tpng -o dfd.png
./tm.py --report template.md
```

Sequence diagrams additionally need Java and plantuml. The model is a Python
script, which is what makes it a good fit here: it diffs, it reviews, and an
agent can author and update it. It now models `LLM` elements, so agentic
components have somewhere to live in the model.

**`threagile`** is the best pure text-in / text-out fit — one YAML model in,
PDF, Excel, JSON, and diagrams out, roughly 50 built-in risk rules, a single
`docker run`. Offer it, and flag the staleness: the last tagged release is
**v0.9.1, July 2024**. It still runs, but nobody is adding rules for threats
discovered since.

**OWASP Threat Dragon v2.6.2** is actively developed, and its models are JSON
so an agent can author them, but as of 2.x there is still **no CLI**. Rendering
and editing need the desktop or web application, which makes it a poor fit for
an automated workflow and a good fit for a team that wants to edit diagrams by
hand.

## Be honest about what a model contributes

There is one controlled study of LLM-assisted threat modeling worth citing:
AbdulGhaffar and Matrawy, *LLMs' Suitability for Network Security: A Case Study
of STRIDE Threat Modeling* (arXiv 2505.04101, May 2025), five models across
four prompting strategies. It reports **63–72% accuracy and 52–62% F1**, with
failure modes of adopting the wrong threat perspective, missing second-order
threats, and incomplete enumeration. That is on a small threat set in a single
domain, so it bounds the claim rather than settling it. Everything else in this
space is self-reported preprints and vendor material.

So, concretely:

| Reliable | Not reliable |
| --- | --- |
| Breadth-first enumeration over a described system | Ranking risk |
| Authoring and updating `pytm` or `threagile` models | Reasoning about trust boundaries that were never described |
| Mapping findings to STRIDE, LINDDUN, or OWASP categories | Finding chained, multi-step threats |
| Keeping an existing model in sync with a diff | Deciding what the team should fix first |

A human prioritizes. Step 6 exists because of this table.

## Systems with AI agents

If the system includes an LLM or an agent, read
`references/agentic-systems.md` before step 2. Agentic components break the
usual boundary assumptions: the trust boundary is inside the prompt, and the
component's privileges are whatever its tools can reach.

## Report

Lead with the ranked abuse paths, each in the record format from the finding
contract above. Then, in order: the system model with evidence, the trust
boundary table, attacker capabilities and non-capabilities, existing
mitigations with `file:line`, recommended mitigations tied to specific
components, and the assumptions and open questions that remain. State which
method was used and whether a model file was generated or updated.

## References

- `references/method-prompts.md` — STRIDE, LINDDUN, and attack tree prompts,
  and the elicitation questions for step 6.
- `references/agentic-systems.md` — MAESTRO's seven layers and the lethal
  trifecta framing for systems containing AI agents.
