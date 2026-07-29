---
name: security-ai
description: >-
  Security review for LLM applications, AI agents, MCP servers and clients, the
  AI and ML supply chain, and repositories that ship agent skills or plugins.
  Covers prompt injection and indirect injection, exfiltration paths, agent
  permission and sandbox hardening, MCP authorization requirements, model,
  dataset and pickle provenance, and AI red-teaming tool selection. Skip it
  when no model or agent sits in the trust path and a conventional
  application, infrastructure, or dependency review applies, and skip it for
  legal or compliance sign-off.
---

# Security review for AI systems

Use this skill when a language model sits in a trust-bearing position: it
reads attacker-influenced text, chooses tool calls, or gates access to data.
The reviewable object is almost never the model. It is the surrounding
architecture — what the model can reach, what it can emit, and what the
harness enforces regardless of what the model decides.

Do not use this skill for a conventional web, infrastructure, cryptography, or
dependency review with no model or agent in the loop, and do not use it to
produce legal or regulatory sign-off. Regulatory dates appear here only as
engineering deadlines.

## Step 1: identify the surfaces

A target usually has more than one. Work every surface it has.

| Signal in the target | Surface | Reference |
| --- | --- | --- |
| Prompts assembled from user input, retrieved documents, or tool output; a chat, completion, or summarization endpoint; a vector store | LLM application | `references/llm-application-review.md` |
| A loop that selects tools, writes files, runs commands, browses, or spends money; permission or sandbox configuration | Agent runtime | `references/agent-runtime-hardening.md` |
| An MCP server or client, a server configuration file, a tool catalog, or a one-click server install flow | MCP | `references/mcp-server-review.md` |
| Model weights, datasets, `from_pretrained`, `torch.load`, pickles, a fine-tuning or inference pipeline, a model registry | AI/ML supply chain | `references/ai-supply-chain.md` |
| `SKILL.md`, `CLAUDE.md`, `AGENTS.md`, agent settings files, hooks, or a published skill or plugin package | Skill-shipping repository | "Repositories that ship agent skills and plugins" in `references/agent-runtime-hardening.md` |

`references/red-teaming-tools.md` is cross-cutting. Consult it once the
surfaces are known, to choose the scanners and probes that produce evidence
for the findings, and to avoid recommending archived projects.

## Step 2: work the matching checklist

Each reference is an ordered checklist with the questions to ask, the code and
configuration to read, and the commands that produce evidence. Two rules
apply to every surface:

1. A control that exists only in a prompt is not a control. Report anything
   security-relevant that is enforced by model instruction rather than by the
   harness, the network, the payment rail, or an authorization check.
2. Name the structural property that fails, not the payload that exposed it.
   A single jailbreak string is a symptom; "this component holds private data,
   reads untrusted content, and can reach the network" is the finding.

## Step 3: report per the shared contract

The `security-audit` skill owns the long form of the severity, evidence, and
reporting contract. Restated here so this skill stands alone:

- Severity is `Critical`, `High`, `Medium`, `Low`, or `Informational`, chosen
  from impact and reachability in the target's real deployment, not from a
  generic CVSS-style table.
- Every finding carries: a stable id, a one-line title, severity, confidence,
  the exact file and line or endpoint, preconditions, a written attack path,
  the impact in terms of what an attacker gains, the evidence, and a concrete
  remediation.
- Confidence is reported separately from severity and never averaged into it:
  `High` when the path was read end to end and no mitigating control was
  found, `Medium` when a hop is inferred from framework behavior rather than
  read here, `Low` for a pattern match or a path that leaves this repository.
- With no demonstrated path from attacker-controlled input to impact, tag the
  finding `theoretical — no proof`, cap it at Medium, and say what would
  settle it — a command output, a trace, a reproduction.
- Report what was reviewed and what was not, so the absence of findings in an
  unreviewed area is never read as a clean result.
- Report residual risk explicitly, including accepted risk and compensating
  controls.
- Do not invent CVE identifiers, version numbers, tool flags, or framework
  entries. Where a fact is unverified against a primary source, mark it.

## Frameworks and their current status

Cite these accurately. Status matters more than the citation, and inflated
status is itself a defect in a security report.

- **OWASP Top 10 for LLM Applications** — the current edition is **2025**.
  There is no 2026 edition. LLM01 Prompt Injection, LLM02 Sensitive
  Information Disclosure, LLM03 Supply Chain, LLM04 Data and Model Poisoning,
  LLM05 Improper Output Handling, LLM06 Excessive Agency, LLM07 System Prompt
  Leakage, LLM08 Vector and Embedding Weaknesses, LLM09 Misinformation, LLM10
  Unbounded Consumption. Verified against `https://genai.owasp.org/llm-top-10/`.
- **OWASP Top 10 for Agentic Applications 2026** — a separate list, released
  2025-12-09. ASI01 Agent Goal Hijack, ASI02 Tool Misuse and Exploitation,
  ASI03 Identity and Privilege Abuse, ASI04 Agentic Supply Chain
  Vulnerabilities, ASI05 Unexpected Code Execution, ASI06 Memory and Context
  Poisoning, ASI07 Insecure Inter-Agent Communication, ASI08 Cascading
  Failures, ASI09 Human-Agent Trust Exploitation, ASI10 Rogue Agents. **These
  entry titles were assembled from secondary summaries, not from the OWASP
  PDF — confirm them against the source document before quoting them in a
  deliverable.** The release date and the existence of the 2026 edition are
  verified from the OWASP GenAI resource page.
- **OWASP MCP Top 10** — a distinct OWASP project, currently **v0.1, Phase 3
  beta release and pilot testing**, identifiers `MCP01:2025`–`MCP10:2025`:
  Token Mismanagement and Secret Exposure, Privilege Escalation via Scope
  Creep, Tool Poisoning, Software Supply Chain Attacks and Dependency
  Tampering, Command Injection and Execution, Intent Flow Subversion,
  Insufficient Authentication and Authorization, Lack of Audit and Telemetry,
  Shadow MCP Servers, Context Injection and Over-Sharing. Verified against
  `https://owasp.org/www-project-mcp-top-10/`.
- **MITRE ATLAS** — the adversarial-ML technique knowledge base, on a monthly
  release cadence, with 2026 additions that are agent-centric. **The specific
  version (v5.4.0, February 2026) and technique counts come from secondary
  sources and are unverified** — check `https://atlas.mitre.org/` before
  citing a number.
- **NIST AI RMF 1.0** with the **NIST AI 600-1** generative-AI profile for
  governance framing, and **NIST SP 800-218A** (final, 26 July 2024) as the
  AI-specific overlay on the Secure Software Development Framework. Use
  800-218A when the question is "what should the development process do".
- **NSA Cybersecurity Information Sheet on MCP** — cite the PDF URL
  `https://media.defense.gov/2026/Jun/02/2003943289/-1/-1/0/CSI_MCP_SECURITY.PDF`
  rather than a publication date, because reported dates conflict.
- **EU AI Act** — from **2026-08-02**, Article 50 transparency obligations
  apply (disclose that a user is interacting with an AI system, mark
  synthetic content in a machine-readable way) and Commission supervision of
  general-purpose AI providers begins. The Digital Omnibus delayed some
  high-risk obligations but **not** Article 50; the specific delay dates
  reported by secondary sources are unverified here. Treat this as an
  engineering deadline for disclosure and content-marking work, not as legal
  advice.

## Accuracy discipline

This surface generates more confident-sounding folklore than most. Before a
version number, a CVE identifier, a framework entry, or a tool flag reaches
the report, either verify it against the primary source — the vendor
advisory, the CVE record, the specification page, the project README — or
mark it unverified in the text. A report that hedges an unverified claim is
useful. A report that states a wrong version floor gets a real fix skipped.

## References

- `references/llm-application-review.md` — the lethal trifecta, direct and
  indirect injection, exfiltration in the rendering layer, defensive design
  patterns, RAG and vector-store access control.
- `references/agent-runtime-hardening.md` — permission rules, sandbox ladder,
  egress control, credential isolation, spend limits, audit logging,
  reliability evaluation, blast radius, and skill-shipping repositories.
- `references/mcp-server-review.md` — MCP specification `2026-07-28`
  authorization requirements, ecosystem risks the specification does not
  cover, and scanners.
- `references/ai-supply-chain.md` — pickles and `torch.load`, safetensors
  limits, `trust_remote_code`, scanners, provenance, dataset poisoning, and
  model hubs as non-anchors.
- `references/red-teaming-tools.md` — install commands, exact invocations,
  what each tool actually tests, and CI gating.
