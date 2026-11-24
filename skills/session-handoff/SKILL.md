---
name: session-handoff
description: Writes a concise resume note. Use when the user pauses, asks for a handoff, context runs low, or work moves to another session, tool, or person.
---

# Session Handoff

Write a resume point that lets someone continue safely without repeating discovery. Give it in chat unless the user wants a file; if a file is useful, save it outside the repository (the system temp folder) unless the user names a place, and say where.

## Include

1. **Goal:** one sentence in the user's terms.
2. **Status:** done, in progress, or blocked, with what changed.
3. **Key context:** paths, decisions, constraints, assumptions. Link existing plans, issues, and commits by path or ID instead of copying them.
4. **Evidence:** checks actually run and their results. Mark guesses as guesses; never present unrun tests or unfinished work as done.
5. **Open work:** unresolved questions, risks, blockers.
6. **Next action:** the single best concrete step, plus which skill fits it (for example `debug-scientifically`).

Note OS, runtime, or setup assumptions if the next session may run elsewhere. Include only what is needed to resume: no tool logs, full plans, secrets, credentials, or private data.
