---
name: plan-work
description: Plans multi-step work. Use for features, migrations, or integrations spanning several files or systems, or when asked for a plan or roadmap. Skip for a clear local edit.
---

# Plan Work

A plan holds only the decisions an implementer could not make alone. For a clear local edit, skip planning and make the change.

## Decide what matters

Answer only the questions that could change the plan:

- **Product:** who benefits, and what observable result makes this worth shipping? If it depends on a policy only the user can set, ask one focused question (see `ask-smart`).
- **Engineering:** trace the affected code path. Where two approaches are credible, compare the simplest viable one with its strongest alternative on the constraint that matters, and name the evidence that would reverse the choice.
- **Delivery:** find the dependency most likely to break the plan and check it first. For a hard-to-reverse change, name the rollback path.
- **QA:** name a case where the change looks done but fails the user, and the check that tells them apart.

## Write the plan

Slice the work vertically: each step delivers something runnable end to end. For each step:

```
N. <outcome>
   Files: <paths to create or change, or "unknown until step N" if no code is available>
   Interfaces: <what it consumes and produces, if other steps depend on it>
   Verify: <command or check> -> <expected result>
```

End with risks and open questions, each with an owner (you or the user).

## Self-check before sharing

- Every stated requirement maps to a step.
- Names and types stay consistent across steps.
- No placeholder steps ("handle edge cases", "add tests"): name the cases and the tests.
- The plan is shorter than the code it describes.

## Execute

Respect the requested scope. For a planning-only request, deliver the plan and stop; don't create files unless asked. For implementation, carry each step through its Verify line before starting the next. When evidence contradicts the plan, change the plan. Keep internal discussion internal: return the decision or result, its evidence, and remaining uncertainty.
