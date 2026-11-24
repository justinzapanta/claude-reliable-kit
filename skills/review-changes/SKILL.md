---
name: review-changes
description: Review a diff on request or before release for concrete correctness, regression, and security defects.
---

# Review Changes

Review the change as a skeptical maintainer. The goal is to find defects introduced by the diff, not to restate style preferences.

## Review sequence

1. Establish the diff and its scope. Read the relevant surrounding code, tests, and stated requirements; avoid reading unrelated files.
2. Trace changed behavior through its callers and data boundaries. Check error paths, state changes, concurrency, compatibility, and security where relevant.
3. Run focused checks only when authorized and practical. Treat test output as evidence, not proof that untested paths are correct.
4. Report findings first, ordered by severity. Each finding must identify a concrete scenario, the consequence, and a file and line location in the diff.

## Finding bar

- **Critical:** likely severe data loss, security compromise, or service outage.
- **High:** major behavior is broken for a realistic case, or an important security boundary is bypassed.
- **Medium:** meaningful but limited bug, regression, or missing failure handling.
- **Low:** minor correctness issue with a concrete impact.

Only report issues that the author can act on. Don't report hypothetical risks without a credible trigger, formatting preferences, or pre-existing problems unless they make this change unsafe. If no findings meet the bar, say so, then name important checks not performed. Do not claim "no bugs".

## Output

For each finding: `[Severity] Short title` — scenario and impact; `path:line`; a concise suggested fix when clear. End with checks run and relevant coverage gaps. If the request was for an explanation rather than a formal review, adapt the format.
