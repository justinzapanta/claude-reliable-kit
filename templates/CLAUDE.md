# Project rules for Claude (Claude Reliable Kit)

Copy these lines into your project's `CLAUDE.md`, or run `python install.py --claude-md`. They apply in every session, even when Claude does not load a skill.
If you installed the kit inside the project, replace `~/.claude/skills` with `.claude/skills`.

- Before editing a file, run `python ~/.claude/skills/task-ledger/scripts/memory.py recall --file <path>` and respect recorded decisions; if a request conflicts with one, say so and ask before changing it.
- After fixing a non-obvious bug or making a decision someone could undo by accident, record it: `python ~/.claude/skills/task-ledger/scripts/memory.py add <bug|decision|gotcha> "<text>" --files <paths>`.
- For a pasted browser console error, stack trace, or failing request, run `python ~/.claude/skills/lean-navigation/scripts/trace.py --dir . "<error lines>"` before searching by hand.
- Before changing a function or file, run `python ~/.claude/skills/lean-navigation/scripts/graph.py brief <name-or-path> --dir .`: one call shows callers, tests, recorded decisions, and recent commits.
- When a request has 3 or more requirements, prove them before saying done (3 commands, about 3 seconds): `python ~/.claude/skills/task-ledger/scripts/ledger.py add req "<r1>" "<r2>" ...`, then after the work `ledger.py fact "suite passes" --run "<test command>" --proves all` (or one fact per requirement), then `ledger.py prove`. Add `ledger.py coverage` when you changed shared code.
- Fix where a bad value is produced, not only where it crashes; a `?.` guard alone is not a fix.
- For a bug fix with a test suite, write the failing test and see it fail before changing code.
- Run long test or build commands through `python ~/.claude/skills/lean-navigation/scripts/squeeze.py -- <command>`.

## Optional: shorter replies

Output tokens cost more than input tokens. Add these if you want terse answers (`install.py --lean-replies`).

- Lead with the answer or the change made; skip preamble, restating the request, and closing summaries of what was just shown.
- Report results as short lists or tables; quote only the decisive line of an error or log.
- Do not narrate each tool call; one line before a long step is enough.
