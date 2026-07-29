# security

Project-agnostic security skills for Claude Code. Covers the whole software
lifecycle — repository audit, diff review, the deterministic free toolchain,
supply chain, threat modeling — plus the two domain surfaces that need their
own vocabulary: smart contracts and AI systems.

Every recommended tool is free software or a genuinely free tier, drivable from
a command line, and optional: each skill detects what is installed, prints the
exact install command for what is not, and continues with agent-native
reasoning rather than aborting.

## What it ships

Seven skills, each self-contained so it can be installed on its own:

| Skill | Use it for |
| --- | --- |
| `security-audit` | Repository-wide deep audit, and the shared doctrine every other skill restates: severity, evidence, triage, reporting |
| `security-review` | Diff and pull-request scoped review, advisory only |
| `security-scan` | The deterministic toolchain, its exit codes, suppression syntax, and cadence |
| `security-supply-chain` | Dependencies, CI/CD, SBOM, signing, provenance |
| `security-threat-model` | Trust boundaries, assets, abuse paths, repo-grounded |
| `security-smart-contracts` | Solidity and web3 |
| `security-ai` | LLM applications, agents, MCP servers, and the AI supply chain |

Two custom agents in [`agents/`](agents/):

- `security-auditor` — Opus at high effort, read and run only. It investigates
  and reports; it has no `Write` or `Edit` tool and does not patch.
- `security-scan-runner` — Sonnet at medium effort. It runs the toolchain and
  writes artifacts to a directory outside the working tree.

## Doctrine

The skills disagree with most scanner defaults on four points, and they do so
deliberately:

- **A tool finding is a lead, not a finding.** It is promoted only with a
  written attack path and a `file:line`, or it is tagged theoretical.
- **Evidence or silence.** No claim about a component, control, or data flow
  without a code reference.
- **The blocking set stays small and near-zero false positive.** A gate that
  cries wolf above roughly a fifth of the time gets routed around. Everything
  outside secrets, hardcoded credentials, and unsafe deserialization is
  advisory.
- **Scan artifacts contain source code and exploit steps.** They are written
  outside the working tree and are never attached to a pull request by default.

`security-audit` owns the long form of that contract. The other six restate it
in a short inline block, because the skills-CLI mirror copies each skill
directory verbatim and no skill may reference a file outside its own tree.

## Install

```bash
claude plugin marketplace add .
claude plugin install security@agent-toolkit
```

See [Installation](../../../docs/installation.md) for per-project and
agent-led installs.

## Update and remove

```bash
claude plugin update security@agent-toolkit
claude plugin uninstall security
```

Restart Claude Code afterwards; `/reload-plugins` does not pick up a version
change. A manual install is removed by deleting what it created — the skill
directories under `~/.claude/skills/` and the two agent files in
`~/.claude/agents/`. Those agent files are user-owned configuration, so inspect
them before deleting. See [Uninstalling](../../../docs/uninstalling.md).

## Manual install

Copy or symlink the skills you want and copy the two named agents into the
personal Claude directories:

```bash
git clone git@github.com:akoita/agent-toolkit.git
mkdir -p ~/.claude/skills ~/.claude/agents
for s in agent-toolkit/plugins/claude/security/skills/*; do
  ln -s "$(pwd)/$s" ~/.claude/skills/"$(basename "$s")"
done
cp agent-toolkit/plugins/claude/security/agents/*.md ~/.claude/agents/
```

Use a normal copy instead of the symlink when the checkout should not remain
the live source; a copy will not follow later changes. Inspect existing
destinations before either operation and do not overwrite a customized agent
definition.

## Model routing

Audit and threat modeling are judgment work: run them on `opus` at high effort,
and escalate a single analysis pass to `fable` when a wrong framing of a trust
boundary would be expensive to discover late. Running the toolchain, collecting
SARIF, and normalizing output is mechanical: `sonnet` at medium effort is
enough, and the deterministic result does not improve with a larger model.

Diff review sits in between. It runs often enough that cost matters, so start
on `sonnet` and escalate only the diffs that touch authorization, authentication,
cryptography, or CI configuration.

## What these skills will not do

They do not run any scanner against a repository the user does not control,
they do not vendor rule packs, and they ship no offensive tooling. Penetration
testing is a different job from securing a lifecycle and is out of scope.
