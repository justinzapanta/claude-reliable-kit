---
name: debug-scientifically
description: Debug a failure when the cause is unclear, repeated fixes failed, or the user asks for root-cause analysis.
---

# Debug Scientifically

Find the cause before changing code. A fix you can't explain is a guess.

## Process

1. **Read the evidence.** Read the full error message and stack trace. Note the first line in the user's code, the exact error type, and the input that triggered it. Don't skim.
2. **Reproduce.** Get a minimal command or test that fails. If you can't reproduce it, say so and ask for what's missing (version, input, environment). Don't fix what you can't see fail.
3. **Hypotheses.** List 2-4 plausible causes, ranked by likelihood. One line each.
4. **Cheapest test first.** For the top hypothesis, choose the quickest check that would confirm or kill it: a print, an assertion, a one-line script, a `git diff` of recent changes. Run it. Update the ranking.
5. **Locate.** Narrow with `lean-navigation`: search the error string, then read only the relevant function. Bisect when the failure is "it used to work" (`git bisect`, or comment out halves).
6. **Fix the cause**, not the symptom. Prefer the smallest change (see `minimal-change`). Don't suppress an exception just to silence it.
7. **Confirm.** Check the original reproduction and affected behavior. Reuse a TDD run covering the same input, code and environment. Add a regression test when cheap.
8. **Explain in 3 lines:** root cause, the fix, how you verified.

## Common traps

- Fixing the line in the traceback when the bad value came from earlier.
- Changing several things at once, so you can't tell which one worked.
- Assuming the environment matches yours (versions, env vars, OS, paths).
- Trusting a recalled API signature. Check the docs for the installed version.
- Declaring success without rerunning the failing case.

## If stuck after two hypotheses fail

After two failed explanations, revisit the first point where actual behavior differs from the contract. Check the test expectation, fixture, environment, and implementation against that contract. Pick the next observation that separates the remaining causes. Ask for a missing log or input only when local evidence cannot resolve it.

Preserve the original failing input. If a team proposes changing the expected result, require a documented requirement that supports it. After fixing the cause, rerun that exact input and a nearby case that already worked. Report the observed results and any remaining disagreement.
