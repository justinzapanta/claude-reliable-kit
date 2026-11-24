---
name: engineering-principles
description: Choose a simple, project-fitting design for architecture or implementation decisions with meaningful trade-offs.
---

# Engineering Principles

Treat the repository and user request as the source of truth. Prefer a small correct change that can be explained over a clever design that solves imagined future needs.

## Before editing

- Reuse known conventions and acceptance criteria. Inspect the closest working example when a design choice is still unclear.
- Search for existing helpers and conventions before adding new ones.
- Confirm library or framework behavior from installed code or current documentation when the API matters; don't rely on memory for version-sensitive details.
- Turn vague outcomes into observable acceptance criteria. Ask only for missing information that would materially change the solution.

## While editing

- Trace the failure to its cause before patching symptoms.
- Prefer the narrowest change that meets the stated behavior. Preserve unrelated behavior and avoid drive-by cleanup.
- Use the project's established patterns unless there's evidence they cause the problem.
- Handle realistic boundary and failure cases at trust boundaries. Avoid adding layers, dependencies, configuration, or retries without a concrete need.
- Keep code and explanation direct. Add comments for non-obvious rationale, not line-by-line narration.

## Before delivery

- Inspect the diff for accidental changes and check it against the acceptance criteria.
- Run relevant validation when appropriate; label what was run and what remains unchecked.
- Summarize the implementation and evidence in plain language. Never imply a command or test ran when it did not.
