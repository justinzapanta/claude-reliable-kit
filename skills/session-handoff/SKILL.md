---
name: session-handoff
description: Write a concise, evidence-based handoff when work will continue in another session, tool, or person.
---

# Session Handoff

Write a resume point that lets someone continue safely without repeating discovery. Put it where the user or repository expects; don't create files unless a durable handoff was requested or clearly useful.

## Include

1. **Goal:** one sentence in the user's terms.
2. **Status:** completed, in progress, or blocked, with what changed.
3. **Key context:** relevant paths, decisions, constraints, and assumptions.
4. **Evidence:** commands or checks actually run and their results; distinguish observed facts from guesses.
5. **Open work:** unresolved questions, risks, and blockers.
6. **Next action:** the single best concrete step to continue.

## Keep it reliable

- Link to files and locations instead of copying large source excerpts.
- Include only context needed to resume. Do not dump tool logs or repeat the full plan.
- Don't mark unfinished work complete or imply validation that did not happen.
- Never include secrets, credentials, or private data in a handoff.
- If the next session may run in a different environment, note relevant OS, runtime, or setup assumptions.
