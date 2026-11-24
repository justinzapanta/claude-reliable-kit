---
name: task-ledger
description: Keep a compact task ledger only when work spans sessions, many decisions, or likely context loss; avoid duplicate notes.
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

1. **Start** (only if the task qualifies): `python scripts/ledger.py init`, then add each requirement as `req`.
2. **During**: add `decision`, `loc`, and `open` entries as they happen. One short line each.
3. **After a check passes**: `python scripts/ledger.py verify <id> "how it was checked"`. Don't re-verify items whose related code hasn't changed.
4. **Before answering**: `python scripts/ledger.py summary` and confirm every `req` is done and every `open` is either resolved or reported to the user.
5. **Resuming**: point `LEDGER_FILE` at the saved JSON and run `summary` (1,600 characters, pending first). Expand a clipped entry with `get ID` only when needed. Read a Markdown export directly as a handoff.

## Lean memory rules (`pref` entries)

- Store **conclusions, not conversations**: "prefers Python + FastAPI, replies in Tagalog-English mix", not the chat that showed it.
- Write only when: the user says "remember", the user corrects you, or a preference appears twice.
- Newer facts overwrite older contradicting ones (the script's `add --replace <id>` does this).
- Mark source: `--src user` (stated) or `--src inferred` (guessed). Check inferred entries before relying on them.
- **Never store secret values or sensitive personal data.** Record the configuration name or secret manager reference when the task needs it.
- The user can see, edit, and delete everything. Show the ledger on request.

## Persistence (be honest with the user)

Local JSON persists in the project directory. In a temporary workspace, save the JSON to resume with the helper, or use `export` for a readable Markdown handoff. If the platform's Memory feature is on, prefer that for `pref` entries.

## Keep it small

If it nears 30 entries, run `python scripts/ledger.py trim` (drops the oldest verified/loc/decision entries first, never `open` or `pref`). Merge duplicates by hand.
