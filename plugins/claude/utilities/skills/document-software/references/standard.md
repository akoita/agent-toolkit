# Software documentation standard

This standard defines stable information roles and lets their physical layout
scale with the project. It is deliberately smaller than a documentation
framework: a file exists only when it serves a current reader or preserves a
decision worth keeping.

## Design basis

The standard combines several compatible ideas:

- Resonate demonstrates the value of a concise root documentation table,
  current architecture views, a maintained feature catalog, focused RFCs, and
  operational runbooks. Its issue-plan accumulation also shows why transient
  delivery artifacts should not dominate the documentation root.
- Practical design-doc guidance recommends spending effort in proportion to
  ambiguity, longevity, coordination, and the cost of a wrong decision. Useful
  design docs emphasize context, goals and non-goals, alternatives, trade-offs,
  interfaces, cross-cutting concerns, and unresolved questions rather than
  reproducing an implementation.
- Systems architecting treats early design as work on ill-structured problems.
  Documentation should expose drivers, boundaries, risks, and potential
  interface misfits before demanding exhaustive detail.
- TOGAF's useful lesson at project scale is to tailor content to stakeholder
  concerns and maintain a repository that separates reusable reference,
  requirements, current landscapes, and governance records. This standard
  adopts the separation, not the enterprise ceremony.
- Attribute-Driven Design centers architecture on significant functional
  requirements, quality attributes, and constraints, expressed through the
  views needed by stakeholders.

Sources:

- [Resonate documentation](https://github.com/akoita/resonate/tree/main/docs)
- [How to Write an Effective Software Design Document](https://refactoringenglish.com/excerpts/write-an-effective-design-doc/)
- [Design Docs at Google](https://www.industrialempathy.com/posts/design-docs-at-google/)
- Maier and Rechtin, *The Art of Systems Architecting*, second edition
- Harrison and Josey, *TOGAF 9 Foundation Study Guide* and *TOGAF 9 Certified
  Study Guide*, fourth editions
- [Designing Software Architectures: A Practical Approach](https://www.sei.cmu.edu/library/designing-software-architectures-a-practical-approach/)

## Invariants

Every project must make the following information discoverable, but compact
projects may combine it:

| Information | Authoritative home | Rule |
| --- | --- | --- |
| Purpose, status, quick start, verification, documentation links | Root `README.md` | Keep it short enough to scan before installation. |
| Current architecture and boundaries | README section or `docs/architecture/overview.md` | Describe what exists, not the desired future. |
| Consequential rationale | `docs/decisions/` or an established ADR location | Preserve history by superseding records. |
| Proposed consequential changes | `docs/design/` or an established RFC location | A proposal is never the sole current-state reference after delivery. |
| How to perform recurring tasks | README or `docs/guides/` | Organize around reader goals, not code layout. |
| How to operate and recover the deployed system | `docs/operations/` | Create only for operated software. |
| Exact lookup material | `docs/reference/` or generated reference site | Generate from authoritative sources where practical. |

When `docs/` contains more than a few files, `docs/README.md` is its map. It
explains document types and points to the authoritative entry points; it does
not repeat their contents.

Use one canonical document per subject. Link rather than copy. A document may
serve more than one information role in a compact project, but its status must
remain unambiguous.

## Profiles

### Compact

Use for a script, small library, prototype, or young single-component service
with few contributors and no substantial operational burden.

```text
README.md
docs/
  README.md                 # only when supporting docs need a map
  <focused-guide>.md        # only for a real current need
```

The root README includes a short architecture section. Add the first ADR or
design doc only when a real decision or proposal warrants it.

### Standard

Use for a maintained application, multi-component library, service, or project
where contributors need a durable system view.

```text
README.md
docs/
  README.md
  architecture/
    overview.md
  decisions/                # created with the first real ADR
  design/                   # created with the first real proposal
  guides/                   # task-oriented developer or user guidance
  reference/                # contracts and lookup material
```

Only `docs/README.md` and the architecture overview are baseline files. The
other directories are demand-driven.

### Operational

Use when the software is deployed, handles meaningful data or money, has
multiple services or teams, or carries material reliability, security,
privacy, or compliance risk. Start with the standard profile and add justified
views:

```text
docs/
  operations/               # deploy, observe, troubleshoot, recover
  security/                 # threat model, controls, response boundaries
  product/ or features/     # capability catalog and user-visible behavior
  data/                     # ownership, lifecycle, migration, retention
```

Do not create every conditional area merely because the profile is
operational. A dedicated security or data document is useful only when it
contains project-specific truth and has a maintenance owner.

## Document types and lifecycles

| Type | Truth represented | Typical states | Maintenance rule |
| --- | --- | --- | --- |
| README / guide / reference / architecture overview | Current | current, deprecated | Change with behavior; remove stale instructions. |
| Design document / RFC | Proposed change and review | draft, in review, accepted, implemented, abandoned, superseded | Update during design and implementation; link the delivered current state. |
| ADR | Decision at a point in time | proposed, accepted, deprecated, superseded | Do not rewrite an accepted decision's outcome; supersede it. |
| Plan | Intended delivery sequence | active, complete, cancelled | Remove when it has no durable value; otherwise archive away from current-state entry points. |
| Runbook | Current operational procedure | current, deprecated | Exercise or verify after operational changes. |

Use metadata only when it helps lifecycle management. Design docs and ADRs
normally need status and date; ownership is useful for reviewed or operational
material. Do not add ritual metadata to every living guide, and never invent an
owner or review date.

## Naming and placement

- Prefer descriptive kebab-case filenames where the repository has no existing
  convention.
- Number ADRs sequentially, such as `0001-use-postgresql.md`, unless the project
  already uses another stable convention.
- Date design documents when multiple generations or time context matter;
  otherwise use a stable descriptive name.
- Keep delivery plans under `docs/plans/` if they must live in the repository.
  Do not scatter issue-number plans across `docs/` root.
- Preserve familiar established aliases such as `rfc/` instead of renaming
  them to `design/` when they already serve the same role clearly.

## Quality bar

Good project documentation is findable, scoped, current, and testable. It:

- leads with the reader's goal and relevant system boundary;
- distinguishes facts, decisions, proposals, and uncertainty;
- names important quality attributes and constraints rather than saying only
  that the system is scalable, secure, or reliable;
- uses diagrams for relationships and flows that prose cannot explain as
  clearly;
- links concepts to code, tests, configuration, dashboards, or procedures that
  let a reader verify them;
- avoids duplicated code listings, exhaustive file tours, changelog prose, and
  explanations that add no information beyond clear source code.
