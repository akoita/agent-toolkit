# Choosing LLM-powered security tools

These tools complement deterministic scanning; they do not replace it, and none
of them gates a merge. See `llm-assisted-review.md` for why: a model is strong
at triaging deterministic output and unstable at finding vulnerabilities alone.
The inventory below was verified 2026-11-17 and products change fast. Check the
vendor page before relying on access, pricing, or data handling.

Every tool here sends code to a model provider unless it runs on a local model.
Only CodeCrucible (Ollama or an OpenAI-compatible server) and IRIS (open-weight
models on a local GPU) are verified to run locally. No frontier-vendor tool
below runs on local models.

## Choose by constraint

| Constraint | Start with | Caveat |
| --- | --- | --- |
| Code must not leave the machine | CodeCrucible with `--provider ollama` or `openai-compat`; IRIS with a local model | CodeCrucible is young and has no releases. IRIS is a Java-focused research artifact. Local models are weaker; expect more misses. |
| Free, public open-source repository | Copilot Autofix on CodeQL alerts | Autofix only fixes CodeQL alerts; it finds nothing new. Other free-tier availability is unverified. OSS maintainers can apply to Codex for OSS (application-based; per OpenAI announcements, not verified from the primary page). |
| PR or diff review | `/security-review`; `claude-code-security-review` Action on trusted PRs; Gemini CLI `/security:analyze`; Codex Security on a diff | Advisory only. The Action is not hardened against prompt injection: never run it on fork PRs. |
| Deep scan with verified patches | `claude-security` plugin; Codex Security CLI | The plugin is beta and proprietary. Both cost model usage; set a cap. |
| Hosted or enterprise platform | Claude Security app; CodeMender; Semgrep Multimodal; Snyk Agent Fix | Claude Security is Enterprise public beta; CodeMender is Pre-GA on Google Cloud; Semgrep and Snyk are commercial, free-tier availability unverified. |
| Vetted defender access | Anthropic Cyber Verification Program; OpenAI Trusted Access for Cyber; Google Fairwind Program | Access programs that widen what models will help with, not tools. Application and vetting required. |

## Frontier-vendor tools

| Tool | Vendor | Does | Access | Licence | Maturity | Data handling |
| --- | --- | --- | --- | --- | --- | --- |
| `/security-review` | Anthropic | One security pass over pending changes on the current branch (diff, not full repository) | Built-in Claude Code slash command | Part of Claude Code | GA per Claude Code docs | Diff goes to Anthropic, or to Bedrock or Vertex if configured |
| `claude-code-security-review` Action | Anthropic | Diff-aware PR review, inline comments, false-positive filtering | GitHub Action; needs `claude-api-key`; set `claude-model` explicitly | MIT | Not stated | Not verified; assume the model provider |
| `claude-security` plugin (v0.12.0) | Anthropic | Scan a codebase or changes (branch, PR, commit); suggest patches. Inventory, threat model, hunt, then independent verifiers try to disprove each finding. Outputs Markdown, JSONL, SARIF 2.1.0; patches drafted in a scratch copy, never auto-applied | `/plugin install claude-security@claude-plugins-official`, then `/claude-security`; Python 3.9+; git checkout for change scans and patches | Proprietary | Beta for all Claude Code users | Code goes to the model provider; the plugin treats the repository as trusted and adds no isolation |
| `security-guidance` plugin | Anthropic | Regex check per edit (no model call); model review of the diff at end of turn; agentic review on each commit or push Claude makes; Claude fixes findings | `/plugin install security-guidance@claude-plugins-official`; all plans | Not stated | GA per docs | Not verified; assume the model provider |
| Claude Security app | Anthropic | Connect a GitHub repository, scan, validate, propose patches | claude.ai/security; Claude Enterprise only (Team and Max "coming soon") | Hosted | Public beta | Hosted by Anthropic |
| Codex Security CLI and SDK (formerly Aardvark) | OpenAI | Scan a repository, path, or diff; validate findings; write and verify patches; import third-party scanner results; SARIF, JSON, CSV | npm package; providers OpenAI, Bedrock, OpenRouter, Fireworks; no documented local or Ollama support. Some findings require Trusted Access for Cyber | Apache-2.0 | Actively maintained; command usage in this skill's `SKILL.md` (the current README names the binary `cs`) | Results stored locally; code goes to the chosen provider |
| Codex Security in Codex web | OpenAI | Same product family, hosted | ChatGPT Pro, Enterprise, Business, Edu (secondary source; the vendor page returned 403) | Hosted | Research preview (about 2026-03) | Not verified |
| CodeMender | Google | Finds flaws, builds a proof of concept in a sandbox you manage, generates a patch, re-runs the exploit to verify. CLI, VS Code, CI/CD | Gemini Enterprise Agent Platform or Google AI Threat Defense; Google Cloud enterprise customers | Not stated | Preview (Pre-GA) since 2026-07-22 | Traffic through your VPC; Google states zero retention of source code data |
| Gemini CLI Security extension | Google | `/security:analyze` reviews the branch diff; `/security:scan-deps` runs OSV-Scanner. Self-described "first-pass analysis" | `gemini extensions install https://github.com/gemini-cli-extensions/security`; Gemini CLI 0.4.0 or later | Apache-2.0 | Extension | Not verified; assume the model provider |
| Copilot Autofix | GitHub | Fix suggestions for CodeQL code-scanning alerts | Public repositories: no licence needed. Private and internal: GitHub Code Security licence. No Copilot subscription needed | Hosted | GA | Alert data and snippets go to GitHub and are not used for training |

## Accessible tools

| Tool | Does | Licence | Local models | Maturity |
| --- | --- | --- | --- | --- |
| CodeCrucible (`block/codecrucible`) | Two-pass LLM scan with prompt sets; see `SKILL.md` | Apache-2.0 | Yes: `--provider ollama` (localhost:11434, no key) and `openai-compat` (vLLM, LM Studio) | Prototype; no releases |
| IRIS (`iris-sast/iris`) | CodeQL plus an LLM | MIT | Yes: open-weight models on a local GPU | Research artifact (ICLR 2025); Java-focused |
| Vulnhuntr (`protectai/vulnhuntr`) | Python only; traces call chains from input to sink; Claude or GPT | AGPL-3.0 | Ollama is experimental; the authors report poor structured output | Maintenance unclear |
| Semgrep Multimodal (formerly Assistant) | Triage and autofix inside Semgrep AppSec Platform | Commercial | No; OpenAI primary, Bedrock fallback | Free-tier availability unverified |
| Snyk Agent Fix (formerly DeepCode AI Fix) | Fixes Snyk Code findings and rescans | Commercial | Not verified | Free-plan availability unverified |

## Not generally available

- **Big Sleep** (Google DeepMind and Project Zero): research only, no public
  product. Do not present it as usable.
- **Gemini cyber model variants**: limited to governments and trusted partners;
  Google Fairwind Program is vetted-only (governments, critical infrastructure,
  core technology platforms, academic labs).
- **GPT cyber model tiers**: OpenAI Trusted Access for Cyber (per OpenAI
  announcements, not verified from the primary page).
- **Codex Security in Codex web**: research preview, plan-gated.

Vetted-defender programs (Anthropic Cyber Verification Program, OpenAI Trusted
Access for Cyber, Google Fairwind) are access programs, not tools. They reduce
cyber safeguards or widen model access for vetted defenders. The Anthropic
program requires a paid plan and an application through its Verification
Portal.

## Operating rules

- **Check the data policy first.** Send code to a provider only where the
  repository's data policy allows it. Otherwise use a local model.
- **Pin and restrict Actions.** Pin every GitHub Action to a commit SHA, not
  `@main`. Run LLM PR-review actions only on trusted (non-fork) PRs:
  `claude-code-security-review` states it is not hardened against prompt
  injection.
- **Sandbox repo-trusting tools.** `claude-security` treats the repository as
  trusted and adds no isolation. Run it under a sandbox for third-party or
  untrusted code.
- **Set the model explicitly.** The Action README default is an older model;
  `claude-security` recommends the most capable models available to the
  account.
- **Cap cost** where the tool offers it (`--max-cost` in Codex Security and
  CodeCrucible), and do not size a budget from a dry run alone.
- **Treat findings as leads.** An LLM finding is a lead, not a result. Feed it
  through this skill's triage and verify it before reporting.
- **Merge with deterministic output.** Export SARIF where offered and
  deduplicate against deterministic results before triage.

## Sources

Accessed 2026-11-17.

| Source | Publisher | Used for |
| --- | --- | --- |
| https://code.claude.com/docs/en/security | Anthropic | `/security-review` |
| https://github.com/anthropics/claude-code-security-review | Anthropic | Action, prompt-injection warning |
| https://claude.com/product/claude-security | Anthropic | `claude-security` plugin and app |
| https://code.claude.com/docs/en/security-guidance | Anthropic | `security-guidance` plugin |
| https://support.claude.com/en/articles/14604842 | Anthropic | Cyber Verification Program (updated 2026-10-06) |
| https://github.com/openai/codex-security | OpenAI | Codex Security CLI and SDK |
| https://cloud.google.com/blog/products/identity-security/find-and-fix-software-vulnerabilities-with-codemender | Google | CodeMender |
| https://deepmind.google/fairwind-program/ | Google DeepMind | Fairwind Program |
| https://github.com/gemini-cli-extensions/security | Google | Gemini CLI Security extension |
| https://docs.github.com/en/code-security/concepts/code-scanning/copilot-autofix-for-code-scanning | GitHub | Copilot Autofix |
| https://github.com/protectai/vulnhuntr | Protect AI | Vulnhuntr |
| https://docs.semgrep.dev/semgrep-assistant/overview | Semgrep | Semgrep Multimodal |
| https://docs.snyk.io/scan-with-snyk/snyk-code/manage-code-vulnerabilities/fix-code-vulnerabilities-automatically | Snyk | Snyk Agent Fix |
