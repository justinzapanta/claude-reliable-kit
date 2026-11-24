---
name: task-ledger
description: Keeps a small requirements-and-decisions ledger. Use for long tasks with many requirements, work spanning sessions, or risk of losing context. Skip for short tasks.
---

# Task Ledger and Lean Memory

A small file that stops you from losing requirements, repeating checks, or re-reading files. It is a notebook, not a report. Hard cap: **30 entries**.

## Entry kinds

| kind | use for |
|---|---|
| `req` | each requirement from the user's request (so none get dropped) |
| `decision` | a choice you made and why, one line |
| `loc` | `path:line - why it matters` (saves re-searching) |
| `verified` | a check you ran and its result |
| `open` | something unverified, uncertain, or still to do |
| `pref` | stable user preference or fact (the "hot" memory) |

## Workflow

The helper is `scripts/ledger.py` in this skill's folder. Call it by full path from the project directory (`${CLAUDE_SKILL_DIR}` is this skill's folder; outside Claude Code use the folder this file is in); below, `ledger` means `python ${CLAUDE_SKILL_DIR}/scripts/ledger.py`.

1. **Start** (only if the task qualifies): `ledger init`, then `ledger add req "..."` for each requirement.
2. **During**: `ledger add decision|loc|open "..."` as things happen. One short line each.
3. **After a check passes**: `ledger verify <id> "how it was checked"`. Mark a finished requirement with `ledger done <id>`. Don't re-verify items whose related code hasn't changed.
4. **Before answering**: `ledger summary` and confirm every `req` is done and every `open` is either resolved or reported to the user.
5. **Resuming**: run `ledger summary` (1,600 characters, pending first) from the same project. Expand a clipped entry with `ledger get <id>` only when needed. Read a Markdown export directly as a handoff.

## Memory and persistence

Inside a Git project the ledger is `.git/task-ledger.json` (persists, never committed); elsewhere `ledger.json`; `LEDGER_FILE` overrides. Before adding a `pref` entry or resuming a saved ledger, read [references/memory.md](references/memory.md). Never store secret values.

## Keep it small

If it nears 30 entries, run `ledger trim` (drops the oldest verified/loc/decision entries first, never `open` or `pref`). Merge duplicates by hand.
