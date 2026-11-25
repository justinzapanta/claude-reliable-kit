---
name: engineering-principles
description: Keeps code changes small, project-fitting, and verified. Use when editing unfamiliar code, when a fix grows into a rewrite, or before saying a change works.
---

# Engineering Principles

Every changed line should trace back to the request, fit the project, and be backed by a check you actually ran.

## Before editing

- Check `git status` and the relevant diff. Note edits already present, including untracked files, so you never overwrite or revert someone else's work.
- Open the closest working example in the affected module (a sibling handler, test, or helper). Follow its naming, data contracts, error handling, and test style. If examples disagree, follow the one on the current code path.
- One call for the file or function you will touch: `python ${CLAUDE_SKILL_DIR}/../lean-navigation/scripts/graph.py brief <path-or-name> --dir .` (definition, callers, tests, recorded decisions, recent commits; skip if missing). Respect a recorded decision or say why it no longer holds.
- Search for an existing helper before writing a new one. For a version-sensitive API, check the installed code or current docs, not memory.
- Write down the observable check that will prove the change works.

## While editing

- Do what was asked, nothing more: no bonus features, options, or speculative flexibility.
- Edit the lines that need to change; don't regenerate whole files.
- Leave unrelated code alone: no drive-by renames, reformatting, or import shuffles. Mention a real problem elsewhere in one line instead.
- No new abstraction until the third use. No new dependency if the standard library or an existing one does the job. No error handling for cases that cannot happen.
- Remove code your own change made unused; leave pre-existing dead code alone.
- Keep public behavior stable unless asked; flag any breaking change.
- If the small fix would be a hack because the design is the bug, give the minimal fix, name the larger fix and its trade-off, and let the user choose.

## Before saying it works

On a task with a ledger, run `python ${CLAUDE_SKILL_DIR}/../task-ledger/scripts/ledger.py prove` (requirements without passing, current evidence) and `python ${CLAUDE_SKILL_DIR}/../task-ledger/scripts/ledger.py coverage` (tests, callers, and routes the change affects that no evidence checked) before saying it works. Match each claim to evidence:

| Claim | Evidence needed |
|---|---|
| "Fixed" | The original failing input now gives the expected output |
| "Tests pass" | Exit status, the intended tests actually ran, and their result |
| "Requirements met" | Each stated requirement checked one by one |
| "Only X changed" | Your own diff, reviewed hunk by hunk |
| A number or fact | Recomputed, units checked, or a primary source |

- Zero tests collected, a skipped target, a timeout, or a missing command means **unverified**, not passed.
- A green suite while the original input still fails means the bug is open.
- Reuse an earlier result only if code, inputs, and environment are unchanged.
- "Should work", "probably", and "seems to" mean you have not checked yet.

## Report

Two or three lines: what changed, what you deliberately left alone, and the check you ran with its observed result. Name anything left unverified.
