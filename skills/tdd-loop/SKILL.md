---
name: tdd-loop
description: Use a verified failing test first for behavior changes when the project has a practical test path or TDD is requested.
---

# TDD Loop

Turn the intended behavior into evidence before writing its implementation. Keep the loop small enough that each failure is easy to explain.

## Red, green, refactor

1. Read the nearest implementation and tests. Find the project's test command and conventions.
2. State the behavior and important boundary cases. Write one focused test at the layer that owns that behavior.
3. Run that test before changing production code. Confirm it fails because the behavior is missing, not because the test, fixture, or environment is broken. If it passes already, reassess the test.
4. Make the smallest implementation that satisfies the failing test. Avoid unrelated cleanup and speculative abstractions.
5. Rerun the focused test and confirm it passes. Record its outcome once for verification. Broaden the checks when a changed contract or caller needs coverage.
6. Refactor only when it improves clarity or removes duplication; rerun the relevant checks after refactoring.

## Practical judgment

- For a bug, reproduce the user's failure first and preserve it as a regression test when practical.
- For an external integration, test observable contracts and failure behavior; avoid mocking away the behavior under test.
- If a test is infeasible, explain why and use the closest honest check. Never report an unrun test as passing.
- If the user asks not to run tests, respect that instruction and report the unverified behavior.
- Keep the suite proportional to the change. Prefer one meaningful test over many redundant cases.

## Report

State the behavior covered, the checks actually run, and any remaining gap. Include the exact command when useful.
