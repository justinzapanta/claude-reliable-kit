---
name: lean-navigation
description: Locate code, investigate local changes, or trace a browser symptom to its source with bounded searches.
---

# Lean Navigation

Use evidence already in the conversation first. If it answers the question, stop. For a known file, open the relevant range directly.

For an unknown location, search the narrowest plausible directory for the exact identifier or error. Run the helper by its path inside this skill, passing the project directory explicitly. Example from the skill directory:

```sh
python scripts/find.py tax_cents /path/to/project --symbol --ext py
```

The default reply fits 1,600 characters and up to six matches. Python definitions rank first. For a location question, return the matching path and line. For a behavior question, read the enclosing function and follow the caller only if the answer depends on it. For a bug, inspect the failing case and the implementation it exercises.

For a regression after local edits, add `--changed` to search current contents of staged, unstaged, and new unignored files. Check the diff around a hit to see whether the matching line actually changed. If the clue is absent, widen to callers or unchanged dependencies.

A partial outline or truncated search leaves unexamined code. An empty partial result cannot establish absence. Refine the query if a missing result could change the answer. Use an outline for an unfamiliar long file, or a compact map for an architecture question with no search term. Keep raw logs and data local and return only the relevant count, error, or rows. Reuse prior reads until the file changes. Stop once the requested conclusion has supporting evidence.

## Browser to source

Use the available browser tool. For an interaction, request interactive elements only (with agent-browser, `snapshot -i`). Choose the control by its accessible name and use its current ref. After a page change, refresh refs before acting again. For a reading task, extract the relevant section. Use a screenshot when visual appearance matters.

For a UI bug, capture one distinguishing clue such as the exact error or route. Search that clue in the project with the bundled helper, inspect the matching handler, then check the same UI action after the fix. Keep each result to the text or visible state needed for the decision.
