---
name: minimal-change
description: Limit scope when a proposed code change is growing, a rewrite is tempting, or extra abstractions are being considered.
---

# Minimal Change

The best change is the smallest one that fully solves the problem. Smaller diffs are easier to review, safer to ship, and cheaper to produce.

## Rules

Before editing, inspect working-tree status and relevant staged and unstaged diffs. Keep track of edits already present, including untracked files in scope.

1. **Do what was asked, nothing more.** No bonus features, no extra configuration options, no speculative flexibility.
2. **Edit, don't rewrite.** Use targeted edits to the lines that need to change. Don't regenerate a whole file to change a few lines.
3. **Leave unrelated code alone.** No drive-by renames, reformatting, import reshuffling, or "cleanups". If you spot a real problem elsewhere, mention it in one line instead of fixing it.
4. **No new abstraction until the third use.** A helper, class, or layer needs a real reason now, not a hypothetical future.
5. **No new dependency** if the standard library or an existing dependency does the job.
6. **Keep public behavior stable** unless the user asked to change it. Flag anything that is a breaking change.
7. **Match the surrounding style** (see `read-before-write`).

## Before finishing

- Look at your diff (`git diff` or compare) and ask of each hunk: "Was this required by the request?" Undo only your own unrelated edits. Preserve existing work, including adjacent edits in the same file. Leave any hunk of uncertain ownership intact.
- Make sure the diff is small enough that the user can read it in a minute or two. If it's big, explain why it can't be smaller.

## When a bigger change is right

Sometimes the small fix would be a hack (the design is the bug). Then say so briefly: give the minimal fix, name the larger fix and its trade-offs, and let the user choose.

## Report

State what changed and what you deliberately left alone, in two or three lines.
