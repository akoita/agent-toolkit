# Agent runtime hardening

## Permission rules are enforced by the harness, not the model

The single most consequential fact about agent permissions: they are evaluated
by the harness before a tool runs. It follows that a `CLAUDE.md`, an
`AGENTS.md`, a system prompt, or a skill file **can never grant or restrict
capability**. Instructional text shapes behaviour; it does not bound it.
Any control described in those files should be reported as unenforced unless
a matching harness rule exists.

### Claude Code

Rules are evaluated `deny` → `ask` → `allow`, first match winning. A bare tool
name in `deny` removes the tool from the model's context entirely, which is
stronger than refusing calls to it.

A documented gotcha worth grepping for: `Bash(command:rm *)` is ignored and
produces a startup warning. The correct form is `Bash(rm *)`. A rule that
never matches reads exactly like a rule that works.

### OpenAI Codex

Two independent settings:

| Setting | Values |
| --- | --- |
| `sandbox_mode` | `read-only`, `workspace-write` (default), `danger-full-access` |
| `approval_policy` | `untrusted`, `on-request`, `never` |

Network is off by default in `workspace-write`. Check whether it was turned
back on, and why.

### OpenAI Agents SDK

Per-tool `needs_approval` and `is_enabled`. The distinction matters: a
disabled tool is *hidden* from the model rather than merely refused, which
removes it from the attack surface an injection can aim at.

## The sandbox ladder

From an operator's tradeoff table, weakest and cheapest first:

| Layer | Isolation | Overhead |
| --- | --- | --- |
| OS sandbox (seccomp, Seatbelt, bubblewrap) | Good | Very low |
| Containers | Setup-dependent | Low |
| gVisor | Excellent | Medium-high — roughly 2x on simple syscalls, far worse on heavy file I/O |
| microVMs (Firecracker) | Excellent | High, but sub-125 ms boot |

`@anthropic-ai/sandbox-runtime` (`anthropic-experimental/sandbox-runtime`,
Apache-2.0) is the ready-made OS-sandbox layer: bubblewrap plus seccomp on
Linux, Seatbelt on macOS, WFP on Windows, with a domain-allowlisting proxy.
**There is no Anthropic project called `claude-sandbox`. Do not cite one.**

Choose by blast radius, not by preference: an agent that only reads a
repository is fine in an OS sandbox; an agent that executes model-authored
code from untrusted input belongs in gVisor or a microVM.

## Egress is the control that breaks the trifecta

Removing external communication is usually the only leg of the lethal trifecta
that can be removed without removing the product. Two documented failure modes
make naive implementations useless:

- A **hostname-only allowlist** loses to domain fronting when the proxy does
  not terminate TLS. The SNI or the Host header is attacker-controlled text.
- An **allowlisted domain that accepts uploads** — a paste service, a gist, a
  telemetry endpoint that logs query strings, an object store with public
  writes — is itself the exfiltration channel.

So the control that works is: a TLS-terminating egress proxy with its CA
installed inside the sandbox, a per-task allowlist rather than a global one,
and explicit verification that **every allowlisted host is non-writable**.
Write the verification down per host; it is the step teams skip.

Beware exposing a Unix socket into the sandbox. Mounting the Docker socket is
a host escape, not a convenience.

## Credential isolation via the proxy pattern

Run a credential-injecting proxy outside the agent boundary so the agent
process never holds a long-lived secret. The agent makes an unauthenticated
request; the proxy attaches the credential; the agent can use the capability
but cannot exfiltrate the key. Envoy's `credential_injector` filter,
mitmproxy, Squid, or an API gateway all implement this.

Never mount into an agent workspace: `~/.ssh`, `~/.aws`, `~/.config/gcloud`,
`~/.kube`, `.npmrc`, or `*.pem`. **Read access counts** — an agent that can
read a key can exfiltrate it, and injection makes "the agent would not do
that" irrelevant.

One important harness detail: in Claude Code, credential masking, TLS
termination, and filesystem disabling are honoured only from user or managed
settings and **never from repository settings**, precisely so that a
repository cannot weaken them. When reviewing, check which settings scope a
control was written in; a hardening setting committed to the repository may
be silently inert.

## Spend controls

Three distinct things that get conflated:

| Control | What it bounds |
| --- | --- |
| Token budget | Model inference cost |
| Request rate limit | Call volume and burst |
| Purchase authority | Real money leaving the organization |

Purchase authority needs its own limits: a per-transaction cap, a daily cap, a
merchant or payee allowlist, and a human gate on irreversible spend. Enforce
these at the payment rail, never in a prompt and never in agent-side code the
agent can reach.

**No standard exists for agent purchase authority.** Say so in the report
rather than citing a framework that does not cover it, and treat the absence
as a reason for a conservative, rail-enforced design.

## Audit logging

An agent log is adequate only if an incident can be reconstructed from it.
Require, per tool call:

- tool name;
- arguments, redacted but structurally intact;
- agent identity;
- session id and trace id;
- **the permission rule that matched**;
- the allow/deny decision and, if approved, the approver;
- the target host or filesystem path;
- a result size or content hash.

The matched rule is the field most often missing and the one that answers
"why was this allowed".

On telemetry, be precise: **OpenTelemetry GenAI semantic conventions are still
pre-stable.** Core semconv v1.42.0 (June 2026) deprecated the `gen_ai.*`
conventions and moved them to a separate repository, which has no tagged
release. Expect attribute renames, pin your collector mappings, and set
`OTEL_SEMCONV_STABILITY_OPT_IN` deliberately rather than inheriting whatever
the SDK defaults to.

## Evaluating reliability, not capability

`pass@k` — success in at least one of k trials — flatters agents and is the
wrong metric for a control. **`pass^k`, success on every one of k trials, is
the reliability metric.** A guardrail that holds 4 times in 5 is not a
guardrail.

Practices that make the numbers mean something:

- k ≥ 3 on anything load-bearing;
- fixed seeds;
- pinned model version and pinned tool versions, recorded in the result;
- stored trajectories, not only final outcomes, so a failure can be diagnosed
  rather than re-run.

## Blast-radius questions

Ask these of any agent that can spend money or write code. Each has a
concrete, checkable answer.

1. What is the worst single irreversible action available to it?
2. Which credentials are reachable from the *process* — environment,
   filesystem, metadata service, keyring — rather than from the tool list?
3. What is reachable on the network *after* an injection succeeds, not in
   normal operation?
4. Is every allowlisted domain non-writable?
5. Can the agent modify its own policy: settings files, `$PATH`, shell rc
   files, hooks, CI workflow files, pre-commit configuration?
6. Is the spend cap enforced by the payment rail or by a prompt?
7. Can the full tool-call sequence be reconstructed after an incident?

For calibration: an internal red team reported getting a coding agent to
exfiltrate cloud credentials in 24 of 25 attempts under prompt injection.
**Model-layer defences alone failed.** That result is the reason the controls
above are structural — sandbox, egress, credential isolation, rail-enforced
spend — rather than instructional.

## Repositories that ship agent skills and plugins

A repository that publishes skills, plugins, or agent configuration is itself
an agent-runtime surface, because its files execute in someone else's context.

Snyk's **ToxicSkills** audit (completed February 2026, 3,984 skills) found
**36.8% carried at least one security flaw, 13.4% were critical, and 76 had
confirmed malicious payloads**. Prompt injection appeared in 91% of the
malicious skills. Publishing required only a `SKILL.md` and a week-old
account. Treat third-party skills as untrusted code with a friendly file
extension.

**`SKILL.md`, `CLAUDE.md`, `AGENTS.md`, and `.claude/settings.json` are
executable-content surfaces, not configuration.** They enter the context
window verbatim, and hidden or invisible-Unicode instructions have been
demonstrated in the wild.

**CVE-2025-59536** (CVSS 8.7, published 2025-10-03) is the concrete case: a
repository-controlled settings file could specify hook commands that executed
at project-open time, **before the trust dialog**. Per the CVE record, Claude
Code versions before 1.0.111 were affected.

Review checklist:

- Read every line of skill and settings files, including a check for
  invisible Unicode (zero-width, bidirectional controls, tag characters) and
  base64 or hex blobs.
- No hooks in repository-scoped settings that execute at project open or
  session start.
- No committed auto-approve or bypass-permission defaults.
- No `allow` rules that widen network or shell scope, and no wildcard `Bash`
  or fetch rules.
- Skills declare their network destinations and dependencies. No
  `curl | bash`, no unpinned downloads, no `@latest` in an install step.
- Secret scanning in CI, plus credential-file exclusions so an agent run
  cannot read what it should not.
- Worktree and CI credentials scoped so an agent run cannot reach
  organization-wide tokens; prefer per-job, least-privilege tokens with short
  lifetimes.
- CI scanning of the skills themselves — `aig-skill-scan` for a fully local
  run, or `snyk-agent-scan` where sending tool metadata to a vendor is
  acceptable. Both are covered in `references/mcp-server-review.md`.

Advise pinning the agent toolchain to patched versions. Version floors quoted
in press coverage should be marked unverified unless they match a vendor
advisory or a CVE record; the 1.0.111 floor above comes from the CVE record
itself.
