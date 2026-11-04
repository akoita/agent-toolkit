# Writing documentation

Every document must be useful, concise, and complete for one reader doing one
task. This reference covers how to write the text; [standard.md](standard.md)
covers where each document lives and how it ages.

## The three tests

- **Useful:** the reader can decide, do, or verify something after reading.
  Lead with the answer, result, or command. Cut history, narration, and what
  clear code already says.
- **Concise:** every sentence carries information the reader needs. Prefer one
  precise sentence to three approximate ones.
- **Complete:** the reader can finish the task without asking anyone. Give the
  prerequisites, the exact steps, the expected result, and what to do when it
  fails.

When the tests pull apart, completeness wins in procedures (guides, runbooks,
install steps) and concision wins in overviews (README, architecture). A short
runbook that skips the rollback is not concise, it is broken.

## Start from the reader

Before writing, name three things, even if only to yourself:

1. Who reads this: a new contributor, an operator, a user, a reviewer.
2. What they are trying to do when they open it.
3. What they already know, so you neither repeat it nor skip it.

Write for that reader. A document that serves two very different readers
usually needs to become two documents, or one with clearly separated parts.

## Structure

- **Lead with the point.** The first sentence of a document and of each section
  states the answer, decision, or purpose. Never open with "This document
  describes".
- **Headings name tasks or questions** the reader scans for, such as "Install
  on Windows" or "Why Postgres", not "Overview" or "Miscellaneous".
- **One point per paragraph,** at most about four sentences. Source line
  wrapping is not paragraph structure.
- **Lists for parallel items, tables for items compared on several
  attributes,** numbered lists for steps in order. Prose for reasoning.
- **Restructure any prose block longer than about 120 words** into shorter
  paragraphs, a list, or a table.

Length budgets keep each type honest:

| Type | Budget | Must contain |
| --- | --- | --- |
| Root README | Readable in two minutes | Purpose, status, quick start, how to verify, links to deeper docs |
| Guide | One task | Prerequisites, numbered steps, expected result, common failures |
| Runbook | One operation | Trigger, safety checks, steps, verification, rollback, escalation |
| Architecture overview | One sitting | Boundaries, components, main flows, constraints, links to decisions |
| ADR | One decision | Context, decision, alternatives considered, consequences, status, date |
| Reference | Lookup, not reading | Every option or field with type, default, and an example |

## Sentences and words

- Keep sentences under about 25 words. Split a sentence that carries two ideas.
- Use the active voice and name the actor: "the worker retries the job", not
  "the job is retried".
- Prefer concrete nouns and numbers with units: "under 3 seconds", not "fast".
- Use the same term for the same thing everywhere, matching the code's names.
  Define a term once where it first appears.
- Cut filler: "simply", "just", "basically", "very", "in order to", "it should
  be noted that", "as mentioned above".
- State uncertainty plainly ("not yet measured") instead of hedging every
  sentence.

| Instead of | Write |
| --- | --- |
| In order to start the service, it is necessary to run the following command. | Start the service: |
| The system is highly scalable and robust. | Each worker handles 50 jobs a minute; add workers to scale. |
| This section will explain how configuration works. | Configuration comes from `config.toml`, then environment variables. |

## Commands and examples

- Give the exact command, ready to copy and paste into the shells your readers
  use (for example both bash and zsh).
- Avoid placeholders that break a shell, such as `<your-token>`. Use an
  environment variable (`"$API_TOKEN"`) or a clearly fake value and say what
  to replace.
- Show the expected output or the sign of success after a command that matters.
- Keep examples real: run them, or take them from tests. Never invent output.
- Link to the authoritative file instead of copying long configuration or code.

## Keep it current

- Describe what is true now. Label proposals, plans, and historical notes as
  such, and keep them out of current-state documents.
- Update the affected documents in the same change as the code.
- Delete stale, duplicated, or misplaced content whenever you touch a document.
  Moving it to an archive is better than leaving it in the reader's path.

## Diagrams

Draw a diagram only when it answers a question that prose answers badly, such
as how components connect or how a request flows. Keep its source editable
(Mermaid or similar), use the code's names, and add one sentence saying what
to read from it.

## Review before you commit

Read your diff as the reader would, then check:

1. Does the first sentence of each new section state its point?
2. Can the reader finish the task with only this document and its links?
3. Is there a sentence, paragraph, or section the reader would not miss?
4. Do every command, path, and name match the repository?
5. Did you remove what this change made stale?
