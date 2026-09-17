# Adaptable document templates

These are content prompts, not forms to complete mechanically. Delete sections
that do not help the intended reader. Replace angle-bracket prompts with
verified project facts; never leave placeholders in committed output.

## Documentation map

```markdown
# Documentation

<One paragraph naming the audiences and what this documentation covers.>

## Start here

| Need | Document |
| --- | --- |
| Understand the system | [Architecture overview](architecture/overview.md) |
| ... | ... |

## Document types

<Explain where current architecture, proposals, decisions, guides, reference,
and operations live. Include only types the project actually has.>

## Maintenance

<State the practical rule for keeping docs synchronized and the checks to run.>
```

## Current architecture overview

```markdown
# Architecture overview

## Purpose and scope

<What the system does, for whom, and what lies outside this view.>

## System context

<A small context diagram or prose identifying users, external systems, and the
system boundary.>

## Components and ownership

<Responsibilities and boundaries; use a table when mapping components to code.>

## Key flows

<Only the flows needed to understand behavior, data, control, or failure.>

## Interfaces and data

<Important public contracts, sources of truth, persistence, and consistency
boundaries. Link to exact reference material.>

## Quality attributes and constraints

<Concrete availability, security, privacy, performance, deployability,
compatibility, or cost drivers that shape the architecture.>

## Deployment and operations

<Runtime topology and operational boundaries, or links to dedicated docs.>

## Known limitations

<Material gaps or risks that affect how the current system should be used.>

## Related documentation

<Decisions, designs, runbooks, and authoritative references.>
```

## Design document

```markdown
# <Outcome-oriented design title>

| Field | Value |
| --- | --- |
| Status | Draft / In review / Accepted / Implemented / Abandoned / Superseded |
| Owner | <Real accountable person or team, if known> |
| Created | YYYY-MM-DD |
| Related | <Issues, decisions, prior designs, or current docs> |

## Summary

<The problem and proposed direction in a paragraph understandable without oral
context.>

## Context and problem

<Current state, evidence, stakeholders, and why action is needed.>

## Goals and non-goals

<Observable outcomes and plausible adjacent outcomes intentionally excluded.>

## Drivers and constraints

<Significant functional needs, quality attributes, dependencies, and hard
constraints.>

## Proposed design

<Start with the system view, then describe only details material to the
decision. Include interfaces, data, failure behavior, and diagrams as needed.>

## Alternatives and trade-offs

<Viable alternatives, including retaining the current design, and why the
proposal fits the drivers better.>

## Cross-cutting concerns

<Relevant security, privacy, reliability, observability, accessibility,
compatibility, cost, and operability impacts. Omit irrelevant headings only
after considering them.>

## Delivery and migration

<Incremental rollout, compatibility, data migration, rollback, and cleanup.>

## Verification

<Tests, measurements, acceptance signals, and operational evidence.>

## Open questions

<Each unresolved issue, options, owner if known, and the next decision step.>

## Outcome

<After completion, record what shipped and link the updated current-state docs.>
```

For a mini design doc, keep Summary, Context, Goals/non-goals, Proposed design,
Alternatives/trade-offs, and Verification, often within one to three pages.

## Architecture decision record

```markdown
# NNNN: <Decision title>

- Status: Proposed / Accepted / Deprecated / Superseded by NNNN
- Date: YYYY-MM-DD
- Related: <Designs, issues, or code>

## Context

<Forces, constraints, and the decision that must be made.>

## Decision

<The selected option and its scope.>

## Alternatives considered

<Only credible alternatives and their decisive trade-offs.>

## Consequences

<Positive, negative, and follow-up effects, including operational implications.>

## Verification

<How implementation and continuing conformance can be checked.>
```

## Operational runbook

```markdown
# <Task or incident> runbook

## Purpose and safety boundary

<When to use this procedure, impact, authorization, and actions it does not
permit.>

## Preconditions

<Access, tools, backups, health conditions, and identifiers to resolve before
acting.>

## Procedure

<Numbered, executable steps with expected observations. Keep destructive steps
explicit and narrowly targeted.>

## Verification

<Evidence that the task succeeded and the system is healthy.>

## Rollback or recovery

<How to return to a safe state, or why rollback is impossible and how to
recover.>

## Escalation

<Stop conditions, evidence to collect, and the real escalation route if known.>
```
