# Claude Reliable Kit

**Claude Code skills for code navigation, debugging, and code review.**

[Quick start](#install-claude-code-skills-in-a-repository) · [Skill catalog](#choose-a-developer-skill) · [Download skills](releases/) · [Contribute](CONTRIBUTING.md)

Find where a feature lives, trace a failing test to its cause, and review a patch for regressions. **Claude Reliable Kit** is an MIT-licensed collection of 13 developer skills for Claude Code and Claude.ai. Each skill covers one task. Start with [Lean Navigation](skills/lean-navigation/SKILL.md) if your main problem is finding the right code in an unfamiliar repository.

## Install Claude Code skills in a repository

1. Download the kit. In the project where you use Claude Code, create the directory `.claude/skills/`.
2. Copy the entire `skills/lean-navigation/` folder into that directory, including its Python scripts. The resulting path should be `.claude/skills/lean-navigation/SKILL.md`. To install all 13, copy the **contents** of the kit’s `skills/` directory into `.claude/skills/`.
3. Open Claude Code in the project and try the prompt below. Commit the skill folders if you want teammates to have the same workflows. For a personal installation across local projects, use `~/.claude/skills/`.

> /lean-navigation Find where checkout calculates tax. Show me the definition, one caller, and the rounding rule.

**Using Claude.ai chat?** Choose a [packaged skill ZIP](releases/) and upload it in your Skills settings. Provide the files for the task in that chat. Local repository searches require access to the project files and a Python 3 execution environment.

## How Lean Navigation finds relevant code

Claude can select an installed skill from its description or you can invoke it by name. Its `SKILL.md` gives Claude a search strategy. When the file is known, it reads the relevant lines. When only a symbol or error is known, the Python helper searches the project and returns short excerpts with paths and line numbers. The default search shows up to six matches within a 1,600-character output budget.

Try this from the root of the downloaded kit using the included pricing fixture:

```sh
python skills/lean-navigation/scripts/find.py tax_cents evals/fixtures/pricing-project --symbol --ext py
```

The result points to the definition at `pricing.py:4` and its caller at `pricing.py:12`. Reading the return expression at line 8 explains the behavior: integer division rounds fractional cents down. A location question can stop at the first match. A rounding bug warrants the extra read and a focused test. [Example source](evals/fixtures/pricing-project/pricing.py)

For a regression after local edits, add `--changed` to search staged, unstaged, and new unignored files in a Git working tree. For a browser bug, the skill can use an available browser tool to capture the visible error, then use that text to find the handler. Browser automation requires a browser tool in the session.

## Choose a developer skill

### Explore and diagnose

| Skill | When to use it |
| --- | --- |
| [lean-navigation](skills/lean-navigation/SKILL.md) | Reads too much. Combines a compact map with targeted search when useful, then opens relevant ranges; helper output is bounded. |
| [read-before-write](skills/read-before-write/SKILL.md) | Code that works but doesn't fit the project. Learn conventions from a neighbor file first. |
| [debug-scientifically](skills/debug-scientifically/SKILL.md) | Guess-and-patch. Reproduce, rank hypotheses, test the cheapest one. |

### Plan and implement

| Skill | When to use it |
| --- | --- |
| [ask-smart](skills/ask-smart/SKILL.md) | Wrong assumptions, or too many questions. Ask only when the answer changes the result. |
| [plan-work](skills/plan-work/SKILL.md) | One assistant coordinates product, engineering, delivery, and QA decisions for complex tasks. |
| [engineering-principles](skills/engineering-principles/SKILL.md) | Overbuilt or unfamiliar code. Inspect first, prefer simple solutions, and preserve project conventions. |
| [minimal-change](skills/minimal-change/SKILL.md) | Over-engineering and rewrites. Smallest diff that solves the problem. |
| [tdd-loop](skills/tdd-loop/SKILL.md) | Implementing before knowing what success means. Red-green-refactor with a verified failure and targeted tests. |

### Review and hand off

| Skill | When to use it |
| --- | --- |
| [review-changes](skills/review-changes/SKILL.md) | Bugs hiding in a broad diff. Review the actual changes for correctness, regressions, and security. |
| [edge-case-security](skills/edge-case-security/SKILL.md) | Happy-path-only code. Systematic edge-case and security pass. |
| [verify-before-done](skills/verify-before-done/SKILL.md) | Says "done" without running anything. Run, recompute, look up, then label what is verified. |
| [task-ledger](skills/task-ledger/SKILL.md) | Losing requirements on long tasks; forgetting preferences. 30-entry ledger plus lean memory. |
| [session-handoff](skills/session-handoff/SKILL.md) | Work that must continue in another session. Leave a concise, evidence-based resume note. |

## Does the kit save Claude tokens?

The local search scripts make no model requests. Returning a short excerpt limits how much tool output reaches Claude. Total usage also depends on how often Claude searches, what it reads next, and whether it solves the task correctly. End-to-end token savings are unmeasured. The [benchmark plan](evals/benchmark-plan.md) tracks correctness, tokens, time, and tool calls across comparable runs.

## Evaluate or contribute

The [evaluation cases](evals/cases.json) include a rounding bug where a lead and tester recommend the wrong fix. The expected behavior is to reproduce the failure and check the stated rounding rule before changing code or test expectations. To contribute a case, include the prompt, the smallest shareable fixture, and an outcome someone else can verify. [Contributor guide](CONTRIBUTING.md) · [MIT license](LICENSE)
