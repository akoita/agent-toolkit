# Method prompts and elicitation

Working material for the procedure in the skill. Each section is meant to be
applied against real components extracted from the code, never against a
hypothetical architecture.

## System model extraction

Work from the repository, in roughly this order, and record a `file:line` for
every entry.

| Look for | Where |
| --- | --- |
| Entry points | Route definitions, handler registrations, queue and topic consumers, webhook receivers, CLI argument parsers, scheduled job definitions |
| Data stores | Migrations, schema files, ORM models, cache and object storage clients |
| External integrations | HTTP clients, SDK initializations, outbound webhook senders, third-party keys read from configuration |
| Runtime shape | Container definitions, process managers, deployment manifests, serverless handlers |
| Build and dev tooling | CI workflows, build scripts, lint and test configuration, developer setup scripts |
| Authentication | Middleware, decorators, guards, token verification code |
| Authorization | Permission checks at handler level, row-level policies, tenant scoping in queries |
| Secrets | Configuration loading, environment variable reads, secret manager clients |

Two things to write down while doing this, because they are cheap now and
expensive to reconstruct later: which entry points are reachable without
authentication, and which components share a process or a credential.

## STRIDE

Apply per component and per data flow. The per-data-flow pass finds more than
the per-component pass, because most real threats live at a boundary rather
than inside a box.

| Category | Property violated | Ask |
| --- | --- | --- |
| **S**poofing | Authentication | Can the caller claim to be someone else? What binds the identity to the request, and can that binding be replayed, forged, or omitted? |
| **T**ampering | Integrity | Can data be modified in transit, at rest, or between check and use? Is anything trusted because it came back from the client? |
| **R**epudiation | Non-repudiation | Can an actor deny an action? Is there a log, does it record who, and can the actor edit or suppress it? |
| **I**nformation disclosure | Confidentiality | What leaks — through responses, error messages, logs, timing, filenames, or an over-broad query? |
| **D**enial of service | Availability | What is unbounded? Request size, result set size, recursion depth, retry loops, per-tenant resource consumption |
| **E**levation of privilege | Authorization | Can a caller act outside their scope? Cross-tenant reads, missing object-level checks, privileged internal endpoints reachable from outside |

### Applying it without generating noise

For each component, walk the six categories once and write only the ones where
you can name a concrete mechanism. "Tampering: none identified — all writes go
through `db/repo.py:88`, which parameterizes" is a legitimate and useful row.
"Tampering: data could be modified" is not a row, it is a restatement of the
category.

Elevation of privilege and information disclosure produce most real findings in
typical web and API systems. Repudiation produces the fewest, and is worth a
single pass rather than per-component attention, unless the product has an
audit or compliance obligation.

## LINDDUN GO

Use when personal data is central to the product. GO is the card-deck variant:
lighter than LINDDUN PRO, sized for a small team, and it does not require a
complete per-data-flow model first.

| Category | Ask |
| --- | --- |
| **L**inking | Can two records or sessions be tied to the same person who did not intend that? |
| **I**dentifying | Can a person be identified from data meant to be pseudonymous or aggregate? |
| **N**on-repudiation | Is someone unable to plausibly deny an action they should be able to deny? |
| **D**etecting | Can an observer infer that a record exists — through a timing difference, an error message, or a response size? |
| **D**ata disclosure | Is more personal data collected, retained, or exposed than the purpose needs? |
| **U**nawareness | Does the person not know what is collected, or lack a way to access, correct, or delete it? |
| **N**on-compliance | Is retention, purpose limitation, or lawful basis unsupported by the implementation? |

Detecting and Linking are the two most often missed in engineering-led reviews,
because both are about inference rather than access, and neither shows up in an
authorization test.

## Attack trees

Use for a single high-value asset when STRIDE has already established that the
asset matters. One tree, one root goal.

1. Write the attacker's goal as the root — "sign a release artifact",
   "read another tenant's records", "move funds".
2. Decompose into the distinct ways to achieve it. Mark each node **AND** (all
   children required) or **OR** (any child suffices).
3. Expand until each leaf is a concrete step you can point at a `file:line` or
   a specific configuration for.
4. Annotate leaves with the attacker capability they need, from the calibration
   step.
5. The cheapest complete path — the OR branch whose AND children are all
   satisfiable by the attacker you calibrated — is the finding. Everything else
   is context.

The value of a tree is the cut: a mitigation that breaks one AND node kills
every path through it. Say which node the recommendation cuts.

## Threat statement format

Write each threat as a path, not as a category:

> An **unauthenticated internet caller** [capability] reaches
> **`POST /api/import`** [entry point, `routes/import.py:23`], which parses a
> user-supplied archive path without normalization [weakness,
> `services/archive.py:57`], crossing the **request-to-filesystem** boundary,
> to **read arbitrary files readable by the service account** [asset and
> impact]. Existing mitigation: none found. Confidence: likely. Tagged
> `theoretical — no proof` until a traversal is demonstrated.

Every element in brackets is required. A threat missing the capability or the
entry point cannot be ranked, and a threat missing the `file:line` cannot be
verified by the person who has to fix it.

## Elicitation questions for step 6

Ask one to three, chosen by which assumption moves the ranking most. Do not ask
all of them; a questionnaire gets a worse answer than a targeted question.

**Deployment and exposure**

- Is this reachable from the public internet, or only from inside a private
  network or VPN?
- Is there a load balancer, gateway, or WAF in front, and does it terminate
  TLS or enforce anything the application relies on?

**Authentication and authorization**

- Who is supposed to be able to call this — anonymous users, any authenticated
  user, or a specific role?
- Are there internal or service-to-service callers that skip the normal
  authentication path?

**Data sensitivity**

- Does this hold personal data, payment data, credentials, or anything under a
  regulatory obligation?
- What is the worst realistic consequence of this data being disclosed?

**Multi-tenancy**

- Do multiple customers share this database, this process, or this cache?
- Is tenant isolation expected to be enforced by the application, by the
  database, or by both?

### When the user cannot answer

State it in the report rather than choosing for them:

> Assumption A1: the service is internet-reachable. Unconfirmed. Threats T2
> and T5 are ranked High under A1 and Low if the service is private-network
> only. T1 and T3 are unaffected.

Two assumptions stated this way are more useful than ten threats ranked on a
guess.

## Keeping the model current

- Check the `pytm` script or `threagile` YAML into the repository next to the
  code it models.
- Regenerate on architecture change, not on a schedule. The trigger is a new
  entry point, a new external integration, a new data store, or a change to an
  authentication or authorization path.
- On a diff, the useful question is narrow: does this change add an entry
  point, cross a boundary that was not crossed before, or widen what a
  component can reach? If not, the model does not need to change.
- Record the date and the commit the model was derived from. A model with no
  provenance cannot be trusted a quarter later.
