---
name: review-changes
description: Reviews a diff, PR, branch, or commit for real defects: correctness, regressions, security, missed requirements. Use when asked to review or before a release.
---

# Review Changes

Review as a skeptical maintainer. Find defects the change introduces, not style preferences. Zero findings is a valid result.

## Sequence

1. **Confirm the target.** The ref resolves (or the patch file applies to the files it names), the diff is not empty, and the checkout is on the reviewed code before running anything. Read the surrounding code, tests, and stated requirements; skip unrelated files.
2. **Spec check.** If there is a spec, issue, or request: list requirements the diff misses and changes nobody asked for, quoting the requirement line. A spec being silent about a case does not make breaking it acceptable.
3. **Trace behavior.** Follow changed code through its callers and data boundaries. Check error paths, state changes, concurrency, compatibility, and security where relevant.
4. **Probe tests** (when authorized and practical). Run focused tests. For a key new condition, invert it briefly and rerun: if the tests stay green, a test is missing. Restore it. Test output is evidence, not proof for untested paths.

## Severity bar

- **Critical:** likely severe data loss, security compromise, or outage.
- **High:** major behavior broken in a realistic case, or an important security boundary bypassed.
- **Medium:** meaningful but limited bug, regression, or missing failure handling.
- **Low:** minor correctness issue with concrete impact.

Report only what the author can act on, with a credible trigger. Label pre-existing defects separately from new regressions, and include them only if they make this change unsafe.

## Output

For each finding: `[Severity] Short title`: scenario and impact; `path:line`; a concise fix when clear. Then a short "Not judged" line for anything you set aside, and the checks you ran. Never claim "no bugs"; say what was and was not examined.

## Receiving review feedback

Check each suggestion against the codebase before acting (search for real usages before "implementing properly"). Clarify every unclear item before changing anything, and push back with evidence when a suggestion is wrong.
