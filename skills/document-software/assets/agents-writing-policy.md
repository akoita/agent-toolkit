## Writing documentation

Write each document for one named reader and one task. Hold it to three tests:

- **Useful:** lead with the answer, result or command. Every section helps the
  reader decide, do or verify something. Cut history, narration and what the
  code already says.
- **Concise:** one point per paragraph, at most four sentences, sentences under
  about 25 words, plain words. Use a list or table for parallel items, and
  restructure prose blocks longer than about 120 words. Source line wrapping is
  not paragraph structure.
- **Complete:** give what the reader needs to finish without asking:
  prerequisites, copy-paste-safe commands, the expected result, and what to do
  when it fails. Link to the canonical source instead of copying it.

Describe the system by concept, not as a changelog, and draw a Mermaid diagram
for each flow, state machine or component map. Split a section past about 150
lines and a page past about 4,000 words. State what is true now, label
proposals and plans, and delete stale content in the same change. When the
tests pull apart, completeness wins in procedures and concision wins in
overviews.

The full guide is the agent-toolkit `document-software` skill
(`references/writing.md`). This section is installed by its
`scripts/install_policy.py`; edit the skill, not this copy.
