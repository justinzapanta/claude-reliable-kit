---
name: read-before-write
description: Inspect nearby examples first when unfamiliar project conventions, APIs, or test patterns could affect a code change.
---

# Read Before Write

Correct code that ignores the project's conventions still costs the user time. Spend a few cheap minutes learning the house style first. Use `lean-navigation` so this stays small.

## Quick orientation (5 steps, stop early if clear)

1. **Stack and tooling**: read the manifest (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`), the README's setup/test section, and lint/format config. Note the language version and test command.
2. **Find the nearest neighbor**: locate one existing file that does something similar to the task (another endpoint, component, model, test). Read that one closely. It is your template.
3. **Check for existing helpers**: search for a utility before writing one (`find.py "<verb or noun>"`). Reuse it instead of duplicating.
4. **Note conventions**: naming, file layout, error handling, logging, imports, typing, comments, and test style. Write them as 3-6 bullets.
5. **Find the test pattern**: look at how a similar feature is tested, and where tests live.

## Then write

- Match what you found, even where you would choose differently.
- Prefer the project's existing libraries. Add a new dependency only if nothing existing fits, and say so.
- Put code where similar code lives.
- If conventions conflict across the repo, follow the most recent or most common, and mention it.

## Don't

- Don't scan the whole repo. Read the manifest, one neighbor, and search hits.
- Don't "improve" unrelated code while you're there (see `minimal-change`).

## Report

End with one line: "Followed the pattern in `path/to/neighbor`; reused `helperName`." This lets the user check your reasoning fast.
