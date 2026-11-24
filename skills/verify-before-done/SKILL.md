---
name: verify-before-done
description: Verify consequential claims or changed behavior with the smallest relevant check before saying it works.
---

# Verify Before Done

Choose the smallest project check that exercises the user's acceptance criterion. Reuse a result if the relevant code, inputs and environment are unchanged.

For a bug, preserve the original failing input. After the fix, compare its actual output with the expected value. If the suite passes but that input still fails, the bug is open. Investigate the mismatch.

For tests, check the exit status, whether the intended case ran, and its result. Zero discovered tests, a skipped target, a timeout, or a missing command leaves the behavior unverified. Check discovery or the blocker before retrying. Broaden coverage when callers or deployment risks warrant it.

For numbers, recompute and check units. For changing facts or quotes, check the relevant primary source. Match each consequential claim to evidence.

Report the command or source and the observed result in a short sentence. For a failure, include the decisive diagnostic and any remaining uncertainty. Read more log output only when it could change the diagnosis.
