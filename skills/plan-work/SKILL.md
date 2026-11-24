---
name: plan-work
description: Coordinate product, engineering, delivery, and QA decisions for complex work or a requested team review.
---

# Plan Work

For a clear local edit, go directly to the change and its focused check. For complex work, have one assistant own the outcome. Select the questions below that could change the decision. Keep one working plan.

## Decide

- Product: Who benefits, and what observable result would make this worth shipping? If the answer depends on a policy only the user can set, ask one focused question.
- Engineering: Trace the affected code path. Where two approaches are credible, compare the simplest viable one with its strongest alternative on the constraint that matters. Identify evidence that would reverse the choice.
- Delivery: Find the dependency most likely to invalidate the plan. Check it early. Sequence the smallest end-to-end change that delivers the outcome. For a hard-to-reverse change, identify a recovery path.
- QA: Identify a plausible case where the change appears to work but fails the user. Choose a check that distinguishes that failure from success.

## Resolve disagreement

When a test fails or a consequential decision rests on an assumption, write the acceptance criterion from the requirement first. Treat a proposed diagnosis as a hypothesis, even if the lead or user favors it. Choose the strongest plausible competing explanation and a check where the two predict different outcomes. Run that check when available. If it contradicts the preferred plan, change the plan. If both fit, keep the decision open and name the missing observation. Agreement is appropriate when evidence settles the question. One concrete counterexample is enough to reopen a decision.

## Execute

Respect the requested scope. For implementation work, carry the decision through the edit and the relevant checks. For a planning request, deliver milestones with observable acceptance criteria. Reuse search results and checks already in context. Load another skill only when a specific unresolved question needs its workflow.

Keep discussion internal. Return one decision or delivered result, its evidence, and any remaining uncertainty that affects the user. Stop exploring when further information would no longer change the decision. Record a handoff only when work must continue later.

Example: For checkout retries, establish whether a timeout can follow a successful charge. Inspect the existing payment identifier and retry path. If the provider supports idempotency, reuse the same key for the same purchase. Verify that a simulated timeout and retry produces one charge. An unresolved provider guarantee belongs in the delivery decision.
