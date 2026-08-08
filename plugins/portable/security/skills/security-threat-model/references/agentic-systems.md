# Threat modeling systems that contain AI agents

Agentic components break the assumptions the rest of the procedure rests on.
In a conventional system, the trust boundary is where a request crosses from
one party to another, and you can point at the code that enforces it. In a
system with an LLM, untrusted content and trusted instructions arrive in the
same channel, and there is no reliable enforcement point between them. Model
the component by what its tools can reach, not by what its prompt says it will
do.

This file covers the modeling angle only. For the detailed agent, LLM, and MCP
control checklists — prompt injection defenses, MCP specification review,
egress and credential proxying, model supply chain — use the sibling
`security-ai` skill rather than duplicating them here.

## The framing question

Ask it of every component that involves a model:

> Does this component have **access to private data**, **exposure to untrusted
> content**, and **the ability to communicate externally** at the same time?

That combination — the lethal trifecta — is an exfiltration primitive. It does
not need a bug: the intended behaviour of the component is enough, because
untrusted content can instruct the model, the model can read the data, and the
model can send it somewhere. Any **two** of the three are survivable.

| Leg | What it means concretely |
| --- | --- |
| Private data access | Tools or context that reach secrets, customer records, internal systems, or the repository |
| Untrusted content | Anything the attacker can influence: web pages, documents, issue text, emails, tool output, retrieved chunks, another agent's message |
| External communication | Network egress, outbound HTTP tools, posting to a chat or issue tracker, writing to a location an attacker can read, rendering an image URL |

When a system is safe, say **which leg was removed and how**, with a
`file:line`. "The summarizer has no network tools; its only tools are
`read_file` and `respond`, registered at `agent/tools.py:31`" is a mitigation.
"Prompt injection is mitigated by instructions in the system prompt" is not —
system prompt instructions do not remove a leg.

Watch for legs that reappear indirectly. A tool that renders markdown can
exfiltrate through an image URL. A tool that writes a file into a repository
that a CI job later publishes has external communication. A subagent without
network access that reports back to a parent that has it has network access.

## MAESTRO

**MAESTRO** (Cloud Security Alliance, February 2025,
`CloudSecurityAlliance/MAESTRO`) is a seven-layer decomposition for agentic
systems. It exists because STRIDE and PASTA under-cover goal manipulation,
agent impersonation, and cross-agent collusion — categories that have no clean
home in a framework built around a request crossing a boundary.

| Layer | Scope | Threats to look for |
| --- | --- | --- |
| 1. Foundation models | The model itself | Training data poisoning, backdoors, jailbreaks, model theft |
| 2. Data operations | Ingestion, embeddings, retrieval stores | Poisoned corpora and retrieved chunks, embedding inversion, tenant bleed in a shared index |
| 3. Agent frameworks | Orchestration, tool registration, memory | Tool description poisoning, tool rug-pulls, memory persistence of injected instructions, unsafe tool argument construction |
| 4. Deployment infrastructure | Runtime, sandbox, network, credentials | Sandbox escape, egress to attacker-controlled hosts, over-broad credentials in the agent's environment |
| 5. Evaluation and observability | Evals, traces, logs | Prompts and outputs logged with secrets, evaluation gamed by the system under test, traces that omit tool calls |
| 6. Security and compliance | Guardrails, policy | Guardrail bypass, policy expressed only in prose, no human approval on irreversible actions |
| 7. Agent ecosystem | Multi-agent interaction, external agents | Agent impersonation, cross-agent collusion, goal manipulation propagating between agents, an untrusted agent in a trusted mesh |

Use it as scaffolding for coverage — walk the seven layers to check you have
not left one unexamined — rather than as a scoring system. The published method
is still thin in places, particularly on how to rank the threats it enumerates,
so treat it as a useful checklist and not as a mature standard. It does not
replace STRIDE for the conventional parts of the system; run both, STRIDE for
the services and MAESTRO for the agentic layer.

## Extra system model questions for agentic components

Add these to step 1 of the procedure, each with a `file:line`:

- **Tool inventory.** Every tool registered on every agent, what it can reach,
  and whether it can write or only read. This is the component's actual
  privilege set; the prompt is not.
- **Content provenance.** For each thing that enters the context — user turns,
  retrieved documents, tool results, file contents, other agents' messages —
  is it attacker-influenceable? Assume yes unless you can show otherwise.
- **Egress.** What can leave, through which tool, to where. Include indirect
  paths: rendered links and images, files written to published locations,
  messages posted to shared channels.
- **Credentials.** Which credentials are in the agent's environment or passed
  to its tools, and what they authorize. An agent inherits the blast radius of
  its weakest credential.
- **Autonomy and reversibility.** Which actions execute without human approval,
  and which of those are irreversible — sending money, deleting data,
  publishing, merging, messaging a third party.
- **Memory.** Whether anything persists across sessions or between users, and
  whether injected content can be written into it. Persistent memory turns a
  one-shot injection into a durable compromise.
- **Multi-tenancy.** Whether one tenant's content can reach another tenant's
  context through a shared index, a shared cache, or a shared memory store.

## Trust boundaries that are easy to miss

- **Inside the context window.** System prompt, user input, retrieved content,
  and tool output are different trust levels arriving in one channel. Name the
  boundary explicitly even though no code enforces it, because that absence is
  the point.
- **The tool call argument.** The model constructs it, so anything that
  influenced the model influenced the argument. A tool that takes a path, a
  URL, a query, or a shell fragment is receiving attacker-influenceable input.
- **The tool description.** Descriptions are instructions the model reads. A
  third-party or remote tool whose description can change is a channel into the
  agent, and a description that changes after review is a rug-pull.
- **Agent to agent.** A message from another agent is untrusted content unless
  every input to that agent was trusted, which is rarely provable. Trust is not
  transitive across a mesh.
- **The eval and observability path.** Traces and logs carry prompts, tool
  arguments, and outputs, which means they carry whatever secrets passed
  through. A log sink is a data store in the model.

## Ranking agentic threats

Two adjustments to step 5:

**Likelihood is higher than it feels.** Indirect prompt injection needs no
vulnerability and no privileged position — only content the agent will read.
If the agent reads web pages, issues, emails, or shared documents, treat the
delivery step as satisfied rather than as a hurdle.

**Impact follows the tools, not the prompt.** Rank by what the tool set can
reach if the model is fully attacker-controlled. Guardrails, system prompt
instructions, and output filters reduce likelihood somewhat and reduce impact
not at all; do not let them move a severity down. The mitigations that move
impact are the structural ones: removing a tool, narrowing a credential,
requiring human approval on an irreversible action, or removing one leg of the
trifecta.

Modeling a `pytm` `LLM` element is a reasonable way to keep this in the
checked-in model, but the element type alone does not carry the tool inventory
or the egress paths — record those alongside it.
