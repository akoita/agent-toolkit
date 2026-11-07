# Practice catalog

Each practice below has an id in [practices.json](practices.json), the
condition under which it applies, what "present" means, and how to adopt it.
The audit script checks the deterministic part; the notes say what an agent
must still judge.

## Agents

### agents-md

`AGENTS.md` is the one instruction file every coding agent reads. It holds
rules, not tutorials. A complete file has at least these sections:

| Section | What it says |
| --- | --- |
| Architecture boundaries | Each top-level package or app and the one concern it owns; which way dependencies flow. |
| Commands and quality gates | Toolchain versions and the copy-paste commands; one command that runs the full gate before a PR. |
| Change delivery | Branch and PR rules, who may merge, how stacked work ships. |
| Data and safety rules | What data may leave the machine, and the side effects that need a person's approval. |

Add a short "When you are changing X, read Y" table that links the
engineering guides. Keep the file under about 4,000 words; move recipes to
`docs/engineering/`.

### claude-imports-agents

`CLAUDE.md` contains the line `@AGENTS.md`, so Claude Code reads the same
rules as other agents. Keep Claude-only notes below that line.

### toolkit-plugins

The repository's tracked `.claude/settings.json` enables
`utilities@agent-toolkit` and `baseline@agent-toolkit` from the
`agent-toolkit` marketplace. Cloud and teammate sessions then load the
skills without a per-machine install. `install_policy.py` from
`document-software` adds the marketplace and the utilities plugin; add the
baseline entry beside it. Make sure `.gitignore` does not hide the file.

### agent-access

Applies to applications and services. Every feature an agent could use on
the person's behalf has an agent surface: a CLI command, an API route or an
MCP tool. The feature catalog's Agent access column records it, or says
`none` with a reason. The audit only reports `review`: an agent must judge
which features matter. Review any new MCP server with `security-ai`.

## Docs

### writing-policy

`AGENTS.md` carries the managed writing-policy block. Install and refresh it
with `document-software`'s `install_policy.py`; never hand-edit inside its
markers.

### readme

The root README states purpose, status, quick start, how to verify, and
where deeper documentation lives. It is short enough to read before
installing.

### docs-map

Applies once `docs/` has three or more pages. `docs/README.md` points to each
entry point and explains document types without repeating their contents.

### architecture-overview

Applies once `docs/` has three or more pages. A living page under
`docs/architecture/`, or an Architecture section in the README for a compact
project, describes what exists now.

### feature-catalog

Applies to applications and services. `docs/features/README.md` holds one
table (Feature, Status, Where it runs, Agent access, What it does) with
statuses `available`, `partial`, `planned` or `retired`, and one page per
feature. Build it from code and tests, not plans. The templates live in
`document-software`.

### engineering-guides

Applies once `docs/` has three or more pages. `docs/engineering/` holds one
recipe per recurring kind of change, each linked from `AGENTS.md`. Write a
guide from a real past change; an empty directory does not count.

### docs-check-ci

Applies when the repository has CI and a docs tree. CI runs
`document-software`'s `docs_check.py` or an equivalent link checker, so
broken links and stale catalog rows fail the build.
