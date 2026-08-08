# Contributing

## Layout

```text
plugins/
├── claude/<plugin>/
│   ├── .claude-plugin/plugin.json
│   ├── agents/
│   ├── skills/<skill>/
│   └── README.md
├── codex/<plugin>/
│   ├── .codex-plugin/plugin.json
│   ├── skills/<skill>/
│   └── README.md
└── portable/<plugin>/                # Agent Plugins portable source packages
    ├── plugin.json
    └── skills/<skill>/
tools/<name>/                         # Standalone skills, not shipped as plugins
skills/<skill>/                       # skills CLI mirrors of canonical sources
                                      # (a skill shared across platforms is also
                                      #  mirrored into the other platform's package)
docs/                                 # Mechanics shared by every skill
.claude-plugin/marketplace.json       # Claude Code catalog
.agents/plugins/marketplace.json      # Codex catalog
```

Native plugin directories are normally both canonical sources and installable
packages. Claude and Codex remain separate because their manifests, agent
definitions, installation scopes, and runtime capabilities differ. Security is
the experimental exception: `plugins/portable/security/` is its canonical
Agent Plugins v1.0.0 source, while the native manifests, catalog entries, and
skill trees are generated compatibility adapters. Native security READMEs and
Claude agent definitions remain client-specific and hand-authored.

Top-level `skills/` is a checked-in distribution catalog for the skills CLI,
not a second source of truth. Each directory is an exact mirror of its canonical
plugin skill or standalone tool, including nested scripts, references, and
`agents/openai.yaml` metadata.

It has to be a real copy. The skills CLI discovers a top-level `skills/`
directory by default and does not follow symlinks. Without the catalog the
default `npx skills add` finds only `maestro`, with no error — and a silently
partial catalog is a worse failure than duplication. `--full-depth` finds every
skill without the mirror, but nothing prompts a user to pass it.

The catalog is not the only generated mirror. A skill whose content is
genuinely platform-neutral can be authored once and shipped by both platforms.
The `security` skills are authored in the portable package and mirrored into
both native packages. That holds only while the bodies carry no
platform-specific instruction. A skill that has to say something different to
each platform gets two canonical sources instead, the way `maestro` and
`codex-maestro` do.

Edit the canonical source first, then run:

```bash
python .github/scripts/sync_skills.py
python .github/scripts/sync_plugin_adapters.py
```

Both commands accept `--check` to report drift without writing.
`tests/test_skills_cli_catalog.py` rejects missing, extra, byte-different, or
differently-executable files in every skill mirror, and
`tests/test_agent_plugins_package.py` rejects portable package, schema, or
generated-adapter drift.

## Where documentation goes

| Content | Location |
| --- | --- |
| What a skill does, its models, agents, and manual install | That skill's `README.md` |
| Multi-phase procedure, worker contracts, result formats | That skill's `SKILL.md` |
| Mechanics identical across skills | `docs/` |
| Catalog and quickstart | Root `README.md` |

A skill that ships its own installer must support installing, updating, and
removing with it. Document all three in the skill's README, and keep user-owned
files — agent definitions, configuration — reported rather than deleted unless
the user passes `--force`.

Keep the root README short enough to read before installing. A procedure that
applies to one skill belongs with that skill, not at the end of the README.

## Adding a skill

1. Decide whether it ships as a plugin or a standalone tool. Give a workflow
   its own plugin when it needs an independent install or release lifecycle;
   bundle skills only when users should normally install and version them
   together. Standalone workflows live under `tools/`.
2. Create the package under `plugins/<platform>/<plugin>/` with its manifest,
   `skills/<skill>/SKILL.md`, and any `agents/` or `references/` it ships.
3. Add a `README.md` to the package covering its models, agents, configuration,
   and manual install.
4. Register it in the platform catalog: `.claude-plugin/marketplace.json` or
   `.agents/plugins/marketplace.json`.
5. Register the skill in `.github/scripts/sync_skills.py` and
   `tests/test_skills_cli_catalog.py`, then run the sync script to create its
   mirrors — `skills/<skill>/` always, plus the other platform's package when
   the skill is shared.
6. Add a row to the skills table in the root README.
7. Add package tests mirroring `tests/test_claude_plugin_package.py` or
   `tests/test_codex_plugin_package.py`.

The version gate and release workflow discover packages from the tree, so they
pick up a new plugin with no extra wiring.

For a portable package, put only Agent Plugins v1 component types at their
fixed locations and keep native-only metadata in the repository-owned
`io.github.akoita.agent-toolkit` extension. Update
`.github/scripts/sync_plugin_adapters.py` when adding a generated native
adapter; the portable source, native packages, and catalogs must all pass their
check modes before review.

## Conventions

- Keep every skill project-agnostic: no repository-specific paths, secrets, or
  company context.
- Keep canonical skills inside their installable native or portable plugin
  package.
- Never edit a generated mirror directly, in `skills/` or in a package that
  ships a shared skill. Change the canonical source and run `sync_skills.py`;
  `sync_skills.py` names every mirror it manages.
- Use platform-specific IDs when runtime namespaces differ; the shared product
  concept can still carry one name in user-facing documentation.
- Never merge Claude and Codex configuration. Portable extension data may
  generate both adapters, but each platform still reads its own manifest,
  agent format, and catalog.

## Releasing

Releasing is automated, and the version bump is enforced.

**On every pull request**, `version-gate` fails if any file inside a plugin
package changed while that package's manifest still declares the same version.
Both checks — `tests` and `version-gate` — must pass before a merge. Changes
outside `plugins/` need no bump.

Run the suite locally with either runner:

```bash
python -m unittest discover -s tests
python -m pytest -q
```

CI uses `unittest` because every test is written against it, which keeps the
workflow free of installed dependencies.

**On merge to `main`**, if the version changed, `release` tags the commit and
opens a **draft** GitHub release with generated notes. Review the notes and
publish it; nothing is published automatically.

Packages are discovered from the tree, so adding a skill needs no change to the
workflows. The release job requires all packages to declare the same version:
this repository releases in lockstep so that one repository tag is unambiguous.
If versions ever diverge deliberately, the job stops rather than guessing a tag
name, and tagging becomes a manual per-plugin step.

Bump the plugin manifest and the matching catalog entry together. Generated
security adapters take their version from `plugins/portable/security/plugin.json`;
after changing it, run both synchronization scripts.

- `plugins/<platform>/<plugin>/.{claude,codex}-plugin/plugin.json`
- the plugin's entry in `.claude-plugin/marketplace.json`, where the Claude
  catalog carries a version

Claude Code caches packages by version, so content shipped under an unchanged
version can be ignored by an existing installation.
`tests/test_claude_plugin_package.py` asserts that the marketplace entry and the
plugin manifest agree.
