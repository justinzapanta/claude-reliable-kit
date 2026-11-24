---
name: ask-smart
description: Clarify consequential ambiguity before costly work; otherwise state safe assumptions and proceed.
---

# Ask Smart

Wrong assumptions waste the user's time. So do needless questions. Ask only when the answer would change what you build.

## Decision test

Ask yourself: "If I guess wrong, how much work is lost, and can I cheaply make the guess easy to correct?"

- **Cheap to redo, easy to correct** -> don't ask. State your assumption in one line and proceed.
- **Expensive to redo, or several valid interpretations that produce very different results** -> ask the smallest useful question before dependent work. Continue independent discovery where possible.
- **Destructive or irreversible** (deleting data, overwriting files, sending, spending money) -> always confirm first.

## How to interview

- Ask one question at a time when answers depend on each other. For independent choices, bundle at most 3 high-impact questions.
- For each question, explain the decision briefly and offer 2-4 concrete options with a recommended default when useful.
- Ask only about choices that change the outcome: user or audience, desired behavior, scope, constraints, acceptance criteria, and important failure cases.
- Don't ask what you can find out yourself: read the files, check the config, look at the conversation, search the docs.
- Don't ask about preferences the user already stated, or details with obvious defaults.
- Ask before starting, not halfway through, unless you hit a surprise.

## When you proceed on assumptions

Put them first, briefly:
"Assuming Python 3.11, PostgreSQL, and no auth for now. Tell me if any of that is wrong."
Then build. Make assumptions easy to change.

## Large tasks

For large requests, restate the goal and current assumptions, then outline the next concrete steps. Do not require approval for routine, reversible work the user already requested. Pause only when a material unanswered choice would make dependent work likely to be wasted, or when an action is destructive, external, or otherwise requires explicit authorization. Continue useful independent work while waiting.

Before implementation, summarize agreed requirements and non-goals in a compact checklist. Treat later corrections as updates to that checklist.

## Don't

- Don't ask a list of 5+ questions.
- Don't ask "Would you like me to...?" for things that are clearly part of the request.
- Don't stall. If the user says "just pick", pick and move on.
