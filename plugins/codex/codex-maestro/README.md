# codex-maestro

Analyze, plan, implement, review, and verify software changes with
**Astra/medium working alone**. This is the only supported preset.

Maestro is an experimental workflow, not a demonstrated performance upgrade.
The [21-trial routing pilot](../../../docs/research/2026-09-maestro-routing-evaluation.md)
did not establish that installing the skill improves speed, cost, or quality
over using the same model directly. Added workers and mandatory advisor review
did not justify their overhead on the bounded tasks tested. On-demand advice
was never triggered, and multi-worker speedup was not measured.

The full procedure is in [SKILL.md](skills/codex-maestro/SKILL.md). This native
package is generated from the [portable source](../../portable/codex-maestro/);
edit that source and synchronize the package rather than editing its mirrors.

## Install and use

```bash
codex plugin marketplace add akoita/agent-toolkit
codex plugin add codex-maestro@agent-toolkit
```

Start a fresh Codex task using `gpt-6-astra` at `medium` effort and invoke
`$codex-maestro`. No custom-agent setup is required. The skill performs analysis,
planning, implementation, and verification in the root and does not
automatically delegate or add an advisor.

Before substantive work, the skill runs this token-free routing preflight:

```bash
python <installed-skill>/scripts/check_routing.py --enforce
```

It checks persisted root identity, model, and effort. Missing, ambiguous,
malformed, or mixed routing evidence fails closed. The skill cannot change a
running task's model. `--profile default` remains accepted; economy and Astra
parallel profiles and live compatibility probes have been removed.

Explicit user-requested delegation is outside the supported preset. The root
must retain planning, review, publication, and responsibility for verifying
routing and results. There is no automatic worker selection or speedup promise.

## Standalone installer

A skill-only installation is also complete. From a checkout:

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py
```

This installs only the skill under `~/.agents/skills/`; it does not create or
replace custom agents. Use `--link` to follow a stable development checkout.
Windows and WSL have separate homes and installations.

For a copied standalone installation, inspect any local edits before updating:

```bash
python plugins/codex/codex-maestro/skills/codex-maestro/scripts/install.py --force
```

This replaces the skill directory. Existing worker definitions remain untouched.
For a symlink installation, updating its source checkout updates the skill.
For a marketplace installation, follow [Updating](../../../docs/updating.md).
Do not install a duplicate standalone skill alongside the plugin.

## Upgrading from worker presets

Version 0.7.0 retires the economy preset and does not ship the proposed Astra
parallel or advisor presets. Old policy blocks may still request workers;
preview and update them with the
[setup workflow](../../../tools/setup-agent-toolkit/SKILL.md). The installed skill
cannot rewrite existing task instructions; start a fresh task after updating.

The legacy worker templates, `--agent-only` installer option, and standalone
CLI runners remain for explicit maintenance of existing integrations. They
are not part of the supported Maestro workflow and are never invoked by it.
Old custom-agent files, including `luna-worker.toml`, are not removed on upgrade.
Inspect their callers before retiring them; preserve customized definitions.

## Remove

For a marketplace installation:

```bash
codex plugin remove codex-maestro@agent-toolkit
```

For a standalone skill, including legacy unmodified agent definitions:

```bash
python <installed-skill>/scripts/install.py --uninstall
```

Use `--skill-only` to remove just the skill or `--agent-only` to remove just the
legacy worker definitions. Modified agent files are kept unless explicitly
removed with `--force`; the legacy `luna-worker.toml` is reported and preserved.
Restart Codex after removal. See [Uninstalling](../../../docs/uninstalling.md).

## Optional always-loaded policy

Use the [setup workflow](../../../tools/setup-agent-toolkit/SKILL.md) to preview
and apply a managed block to a personal or project `AGENTS.md`. A minimal policy
is:

```markdown
- Use `$codex-maestro` for non-trivial implementation and multi-step debugging.
- Work alone with `gpt-6-astra` at medium effort and verify routing before work.
- Keep analysis, planning, implementation, review, and publication in the root.
- Do not automatically delegate or add an advisor.
- Follow the installed skill and preserve unrelated user changes.
```
