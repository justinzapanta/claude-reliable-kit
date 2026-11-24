# Eval tasks

Each task is a prompt where Claude tends to go wrong. Run it with and without the relevant skill, then score.

| id | skill | prompt (short) | pass if |
|---|---|---|---|
| nav-1 | lean-navigation | "Where is the retry logic in this repo and why does it give up after 3 tries?" (give a 50-file repo) | Finds it with a search + slice, reads < 150 lines, cites path:line |
| nav-2 | lean-navigation | "What columns does this 200k-row CSV have and how many nulls in each?" | Uses head/script, never prints the whole file |
| ver-1 | verify-before-done | "Write a function that parses ISO dates and returns the week number" | Runs it, tests year-boundary dates (e.g. 2021-01-03) |
| ver-2 | verify-before-done | "Total these 14 invoice lines and apply 12% VAT" | Computed by script, total matches |
| ver-3 | verify-before-done | "Cite 3 papers on X with DOIs" | Every cited paper confirmed to exist, or dropped |
| rbw-1 | read-before-write | "Add a /health endpoint to this Flask app" (app uses blueprints + custom error helper) | Uses blueprint + existing helper, matches test style |
| dbg-1 | debug-scientifically | Traceback where the bad value originates two calls earlier | Fixes the origin, not the crashing line; reruns repro |
| min-1 | minimal-change | "Fix the off-by-one in paginate()" (file has other messy code) | Diff touches only the bug, plus maybe one test |
| ask-1 | ask-smart | "Build me an app" | Asks 1-2 sharp questions with options, or states assumptions |
| ask-2 | ask-smart | "Rename variable x to count in utils.py" | Does it, no questions |
| sec-1 | edge-case-security | Login endpoint that builds SQL by string concatenation | Finds injection, gives parameterized fix, flags password handling |
| led-1 | task-ledger | 8-step refactor with 5 stated requirements | All 5 requirements addressed, none dropped |
| plan-1 | plan-work | "Add audit logging to our admin actions" in an unfamiliar repo | Inspects first; gives sequenced milestones, observable acceptance criteria, and material risks without speculative implementation |
| plan-2 | plan-work | "Change the button label from Save to Apply" | Makes the small change directly; creates no plan files |
| tdd-1 | tdd-loop | "Fix the date parser failing on leap day" with a reproducible fixture | Adds/runs a focused failing regression test first, fixes behavior, then reruns it |
| tdd-2 | tdd-loop | "Add an optional limit parameter to this API" | Tests default and supplied limit behavior using the project's existing conventions |
| review-1 | review-changes | Diff where a permission check was removed from one update route | Reports the concrete authorization bypass first, with severity and diff location |
| review-2 | review-changes | Cosmetic refactor with no concrete defects | Does not invent findings; names checks or coverage not inspected |
| eng-1 | engineering-principles | "Add retries" to a client with an existing retry helper | Finds and reuses the helper, checks semantics, avoids a duplicate abstraction |
| eng-2 | engineering-principles | Request to modernize an entire module to fix one bug | Makes or proposes the narrow fix and leaves unrelated style untouched |
| handoff-1 | session-handoff | Pause halfway through a migration after tests pass for phase one | Handoff distinguishes completed work, actual evidence, remaining risks, and a concrete next step |

## Comparative suite and fixtures

`cases.json` is the reproducible comparative suite with prompt, expected behavior, and per-case assertions. `fixtures/` contains the exact product brief, Python project, vulnerable patch, and handoff state. Reset/copy the fixture before every arm so edits from one run cannot affect another. See [benchmark-plan.md](../benchmark-plan.md) for matched stock Claude Code, kit, Superpowers, and Matt Pocock arms, and [benchmark-audit.md](../benchmark-audit.md) for the current static comparison and whether runtime results exist.

## Scoring

Per task record: pass/fail, tokens used, tool calls, notes. Compare the with-skill run against the same baseline prompt without the skill. A skill ships only if it improves pass rate or cuts tokens without lowering pass rate. Include at least one clear negative case per skill to catch over-triggering and unnecessary process. Record model, runtime, and date so results are interpretable; a small prompt set is a regression check, not a universal benchmark.
