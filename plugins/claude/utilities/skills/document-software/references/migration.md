# Existing-project documentation migration

Normalize an existing project by improving navigation and truth ownership, not
by imposing a new directory tree wholesale.

## Inventory before editing

List documentation files and relevant root-level guides, then inspect their
inbound links. Classify each file by both role and state:

| Dimension | Values |
| --- | --- |
| Role | entry point, current architecture, design/RFC, decision, guide, reference, runbook, plan, policy, generated |
| State | current, proposed, implemented, superseded, historical, stale, unknown |
| Authority | canonical, derived, duplicate, contradictory, unknown |
| Audience | user, contributor, maintainer, operator, reviewer, agent, external integrator |

Confirm claims in current-state documents against representative code, tests,
configuration, and deployment definitions. A filename such as `architecture`,
`spec`, or `plan` does not prove its role or currency.

## Make a migration map

Before material moves or merges, record the intended transformation:

```text
| Source | Current role/state | Action | Destination or authority | Reason |
| --- | --- | --- | --- | --- |
```

Use these actions deliberately:

- **Keep** when a document already has a clear role and discoverable home.
- **Refresh** when it is authoritative but stale.
- **Merge** when two documents compete as the same source of truth; preserve
  unique content and update inbound links.
- **Move** when placement obscures the document's role and link breakage is
  manageable.
- **Mark** when a proposal, decision, or plan needs an explicit lifecycle
  status rather than relocation.
- **Archive** only when historical value is real. An archive is not a dumping
  ground for content nobody evaluated.
- **Delete** only when content is redundant or misleading and the task
  authorizes removal; report material deletion.

Prefer a small first pass: establish the root and documentation entry points,
name the authoritative current architecture, and resolve the highest-impact
duplicates. Do not rewrite every document merely to make tone or headings
uniform.

## Preserve compatibility and history

- Search for repository-local inbound links before moving a file and update
  all of them in the same change.
- Consider likely external links from README files, published sites, issue
  trackers, and release notes. Keep a short moved notice at the old path when
  external breakage is likely and the repository has no redirect mechanism.
- Preserve commit history with actual moves when tooling permits.
- Keep accepted ADRs as historical records. Add a superseding record instead
  of editing the old decision to appear as if it always matched the present.
- After an RFC or design ships, record its outcome and point to current-state
  architecture, feature, interface, or operations documentation.

## Common failure patterns

- A root README links to selected documents but no docs index explains the
  complete information architecture.
- Current behavior is described only in issue plans or old RFCs.
- Multiple architecture documents describe different eras without status.
- Feature catalogs grow into dense changelogs instead of concise capability
  maps.
- Commands, environment variables, schemas, or API definitions are copied into
  multiple guides and drift apart.
- Empty folders and template files imply documentation coverage that does not
  exist.
- Issue-number plans accumulate at `docs/` root and crowd out durable entry
  points.

Resolve the information role behind each symptom rather than only renaming
files.
