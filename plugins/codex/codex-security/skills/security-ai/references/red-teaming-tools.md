# AI red-teaming and guardrail tools

Choose by two questions: what does the tool actually test, and can it gate a
build. Most of these produce findings; only some produce a pass/fail signal a
pipeline can act on. Verify the current invocation against the project's own
documentation before putting it in a pipeline — flags here move faster than
this file.

## Scanners and red-teaming harnesses

| Tool | Install | Invocation | What it actually tests | CI-friendly |
| --- | --- | --- | --- | --- |
| **promptfoo** (MIT) | `npm i -g promptfoo` | `promptfoo redteam init --no-gui`, then `promptfoo redteam run`, then `promptfoo redteam report` | Application-level red teaming with plugins for BFLA, BOLA, RBAC, SSRF, `agentic:memory-poisoning`, `tool-discovery`, `excessive-agency`, `rag-poisoning`, `indirect-prompt-injection`, and custom policies; Crescendo and GOAT multi-turn strategies | Best in class. **Exit code 100** on failure or below `PROMPTFOO_PASS_RATE_THRESHOLD`; `-o results.json -o results.junit.xml`; official `promptfoo/promptfoo-action@v1` with `type: redteam` |
| **garak** (NVIDIA, Apache-2.0) | `pip install -U garak` | `python -m garak --target_type openai --target_name <model> --probes encoding` | Model-level probing: 40+ probes including `dan`, `encoding`, `promptinject`, `latentinjection`, `leakreplay`, `packagehallucination`, `sysprompt_extraction`, plus `agent_breaker` for tool-aware multi-turn agent exploitation | Weak. **No documented pass/fail exit code and no official GitHub Action** — parse the JSONL report yourself and set your own threshold |
| **PyRIT** (Microsoft, MIT) | `pip install pyrit` | Python orchestration, or `pyrit_scan` for YAML-driven non-interactive runs | Multi-turn attack orchestration (Crescendo, PAIR, TAP), converters that bypass input filters, and scorers | Usable non-interactively via `pyrit_scan`; gating is yours to build |
| **DeepTeam** (Apache-2.0) | `pip install -U deepteam` | `deepteam run config.yaml` | 50+ vulnerabilities including agentic goal theft, recursive hijacking, excessive agency, and tool-orchestration abuse, mapped to the OWASP LLM Top 10 and NIST AI RMF | Config-driven and scriptable, but **exit-code gating is undocumented** |
| **giskard-scan** | `pip install giskard-scan` | Per project documentation | Agent vulnerability scanning: red teaming, prompt injection, adversarial scenario generation | **Currently a beta — 1.0.0b3 on PyPI — so the API will break.** Supports JUnit XML output. Note the earlier v2 `Giskard-AI/giskard` is no longer maintained |

Notes that change how these are recommended:

- **PyRIT moved repositories.** `Azure/PyRIT` is **archived** (confirmed via
  the GitHub API; last push March 2026) in favour of **`microsoft/PyRIT`**.
  Link the new one. The PyPI package `pyrit` is published by the Microsoft AI
  Red Team (confirmed from PyPI metadata, current version 1.0.0), so
  `pip install pyrit` is the right command — the brief for this skill flagged
  it as inferred, and it has since been verified.
- promptfoo is the default recommendation whenever the goal is a gate rather
  than a report, because it is the only one here with a documented failure
  exit code and a maintained action.
- garak tests the model endpoint; promptfoo and DeepTeam test the application
  around it. They are complements, not alternatives. A clean garak run says
  nothing about your tool allowlist.

## Runtime layers, not scanners

These sit in the request path in production. They reduce incident rate; they
are not a substitute for the structural controls in
`references/agent-runtime-hardening.md`.

| Tool | Install | Invocation | Coverage |
| --- | --- | --- | --- |
| **NeMo Guardrails** (NVIDIA) | `pip install nemoguardrails` | `nemoguardrails chat --config=PATH` | Input, dialog, retrieval, execution, and output rails; tool-calling guardrails added in 0.23 |
| **Guardrails AI** | `pip install guardrails-ai && guardrails configure` | `guardrails hub install hub://…` | Validator hub composed into input and output validation |

## Classifiers

**Llama Guard 4 12B** and **Llama Prompt Guard 2** (86M and 22M variants) are
the common open-weight safety and injection classifiers.

Two caveats that must accompany any recommendation:

- They are released under the **Llama Community Licence, which is not an OSI
  licence.** Check the acceptable-use and attribution terms against your
  deployment before adopting.
- **Meta itself documents Llama Guard as injectable.** A classifier reading
  attacker-controlled text is subject to the same class of attack it screens
  for. Pair it with a structural control; never let it be the only thing
  between untrusted input and a capability.

## Excluded, and why

State these when someone proposes them from memory:

- **`llm-guard` is archived** (confirmed via the GitHub API; reported archive
  date 2026-07-09 is from secondary sources and unverified, though the
  archived state and a final commit in July 2026 are confirmed).
- **`Rebuff` is archived** (confirmed via the GitHub API; reported archive
  date 2025-05-16 is unverified, and the repository has had no commits since
  August 2024).

Do not put an archived project in a pipeline that is meant to detect
tomorrow's attacks.

## Using the results

- Red-team pass rates are reliability measurements, so apply the `pass^k`
  discipline from `references/agent-runtime-hardening.md`: a control that
  survives one adversarial suite run is not a control.
- Pin the tool version, the target model version, and the probe or plugin set
  in the recorded result. A pass rate without those three is not comparable
  to next month's run.
- A finding from any of these tools is evidence for the shared reporting
  contract only if the command and its output are captured. A tool name in a
  report without an invocation is not evidence.
