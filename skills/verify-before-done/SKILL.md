---
name: verify-before-done
description: Verify consequential claims or changed behavior with the smallest relevant check before saying it works.
---

# Verify Before Done

Confident errors are the costliest mistakes. Never say "done" until you have evidence, not just a reread.

## Scale the effort

- **Low stakes** (chat, brainstorming, simple facts you are sure of): no extra steps.
- **Medium** (code, calculations, summaries of provided files): run the matching check below once.
- **High** (money, health, legal, security, production code, data deletion): run all checks and list what is still unverified.

## Checks

**Code**
1. Run it. Execute the script, build, or tests. A reread is not verification.
2. Reproduce first for bug fixes: confirm the failure, apply the fix, confirm it passes.
3. Try at least one edge case (empty, null, large, wrong type).
4. If you cannot run it (no environment, missing credentials), say so plainly and name what to test.

**Numbers**
- Recompute with a script or calculator, not mental math.
- Sanity-check the order of magnitude and units. Do totals add up?

**Facts, versions, APIs**
- If it can change (versions, prices, laws, flags, endpoints), look it up in current docs instead of trusting memory.
- If you cannot check, say "I believe, but have not verified".

**Quotes and citations**
- Only cite sources you actually opened or searched. Never invent a source, quote, or page number.
- Drop anything you cannot confirm.

**Requirements**
- Reread the user's original request and tick off every part. Check you did not change anything they didn't ask you to change.

## Label confidence in the final answer

For medium and high stakes, end with one short line per item:
- **Verified:** what you ran or looked up, and the result.
- **Not verified:** what you assumed or could not test.

Keep it to a few lines. Do not turn it into a report.

## Don't repeat work

If an item was already verified and nothing relevant changed since, don't re-verify it. Record checks in the task ledger (see `task-ledger`) when the task is long.
