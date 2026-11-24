---
name: tdd-loop
description: Test-first fixes. Use when fixing a reproducible bug or failing test, adding behavior with a runnable test suite, or when asked for TDD, a regression test, or to verify a fix.
---

# TDD Loop

Turn the intended behavior into a failing test before writing the implementation. Keep each loop small enough that every failure is easy to explain.

## Red, green, refactor

1. Read the nearest implementation and tests. Find the project's test command and conventions.
2. State the behavior and its important boundaries. Name the production change that would make the test fail; if none would, the test is useless.
3. Write one focused test at the layer that owns the behavior. Run it before touching production code. It must fail because the behavior is missing, not because of a typo, fixture, or environment problem. If it already passes, rethink the test.
4. Write the smallest implementation that makes it pass. No unrelated cleanup or speculative abstraction.
5. Rerun the focused test and see it pass. Then run the suite for the code you touched, or the full suite when a shared contract changed.
6. Refactor only to improve clarity or remove duplication, and rerun the same checks.

Work in vertical slices: one test, then its code, then the next. Never write all the tests first.

## Test quality

- **No tautologies:** the expected value must come from the requirement or a hand-worked example, never from the same formula the code uses.
- **Mock only at system boundaries** (network, clock, payment provider, filesystem when needed). Never mock the behavior under test.
- **Regression proof for a bug fix:** temporarily revert the fix and confirm the new test fails, then restore it.
- A test that is hard to write often signals an unclear design; say so rather than forcing it.
- Prefer one meaningful test over many redundant ones.

## When TDD doesn't fit

If a test is impractical, say why and use the closest honest check. If the user asks not to run tests, respect it and report the behavior as unverified. Never report an unrun test as passing.

## Report

The behavior covered, the exact test command, and its observed result (red, then green), plus any remaining gap.
