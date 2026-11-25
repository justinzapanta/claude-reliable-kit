---
name: review-changes
description: Reviews a diff, PR, branch, or commit for real defects: correctness, regressions, security, missed requirements. Use when asked to review or before a release.
---

# Review Changes

Review as a skeptical maintainer. Find defects the change introduces, not style preferences. Zero findings is a valid result.

## Sequence

1. **Get the change map first, even for a one-file diff.** Run `python ${CLAUDE_SKILL_DIR}/../lean-navigation/scripts/graph.py impact --dir .` (add `--base <ref>` for a branch or PR). It lists changed symbols, callers, importers, tests to run, routes, and project memory recorded on those files. A change that contradicts a recorded decision or repeats a recorded bug is a finding; quote the memory. If the script is missing, use `git diff` and search callers by hand.
2. **Confirm the target.** The ref resolves (or the patch file applies to the files it names), the diff is not empty, and the checkout is on the reviewed code before running anything. Read what the change map points to, plus stated requirements; skip unrelated files.
3. **Spec check.** If there is a spec, issue, or request: list requirements the diff misses and changes nobody asked for, quoting the requirement line. A spec being silent about a case does not make breaking it acceptable.
4. **Trace behavior.** Follow changed code through its callers and data boundaries. Check error paths, state changes, concurrency, compatibility, and security where relevant.
5. **Probe tests** (when authorized and practical). Run the tests the change map lists; `python ${CLAUDE_SKILL_DIR}/../task-ledger/scripts/ledger.py coverage --base <ref>` shows which affected tests, callers, and routes nothing has exercised yet. For a key new condition, invert it briefly and rerun: if the tests stay green, a test is missing. Restore it. Test output is evidence, not proof for untested paths.

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
