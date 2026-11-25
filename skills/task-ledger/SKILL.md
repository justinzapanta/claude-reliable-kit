---
name: task-ledger
description: Project memory and an evidence graph for tasks. Use when starting work on files touched before, after a fix or decision worth keeping, or to prove a multi-step task is done.
---

# Project Memory and Evidence Graph

Two small stores that stop you from re-reading the repo or rediscovering what was already learned. `${CLAUDE_SKILL_DIR}` is this skill's folder (outside Claude Code, the folder this file is in). Run the scripts from the project directory; don't read their source.

## Project memory (long-lived)

`memory` means `python ${CLAUDE_SKILL_DIR}/scripts/memory.py`. Each memory is one line linked to files and to other memories.

| When | Command |
|---|---|
| Before editing, debugging, or reviewing files | `memory recall --file <path>` or `memory recall --changed` |
| Looking for past context by topic | `memory recall rounding refund` |
| A bug's root cause is found and fixed | `memory add bug "<cause and fix>" --files <paths> --tags <topic>` |
| A choice with a reason someone could undo by accident | `memory add decision "<what and why>" --files <paths>` |
| A trap that cost time (setup, ordering, hidden coupling) | `memory add gotcha "<trap>" --files <paths>` |
| How a part of the system works, learned the hard way | `memory add concept "<summary>" --files <paths>` |
| Connect related memories | `memory link <id> <id>` or `--link <id>` on add |
| Memories may be outdated | `memory stale`, then `forget` or re-`add` |
| New or empty memory on an existing repo | `memory seed` (fix commits and warning comments, marked inferred; `--dry-run` first) |

Recall ranks memories on the exact file, then on neighbouring files through `lean-navigation`'s code graph (imports and importers), then the same folder. Treat recalled memories as leads to verify, not facts: check `stale` when the file changed. Store conclusions, not conversations; one memory per fact; never secret values (the script refuses obvious ones). `pref` entries hold stable user preferences; before adding one, read [references/memory.md](references/memory.md).

It lives in `.git/lean-memory.json` (private, never committed). To share with a team, set `LEAN_MEMORY_FILE` to a committed path. If the user installed the kit's memory hook, editing a file with recorded decisions pauses once and shows them; read them, then retry the edit or stop and ask if it conflicts.

## Evidence graph (one task)

For multi-step work, debugging, or anything you will claim is done. `ledger` means `python ${CLAUDE_SKILL_DIR}/scripts/ledger.py`. It records what the task needs, what you tried, and what proves it, linked to files.

| Step | Command |
|---|---|
| Goal and requirements | `ledger goal "..."`, then `ledger add req "<r1>" "<r2>" ...` (one per acceptance check) |
| A guess to confirm or rule out | `ledger hypo "..." --files <paths>` |
| Evidence: run a command now | `ledger fact "..." --run "<command>" [--expect-exit 1] --proves <id>|all [--kills <id>] --files <paths>` |
| Evidence seen without a command | `ledger fact "..." --seen "<observation>" --proves <id>` (weaker) |
| Choices and locations | `ledger add decision|loc|open "..."` |
| Before saying done | `ledger prove`: requirements without passing, current evidence; failing, stale, or only observed evidence |
| What the change touches but nothing checked | `ledger coverage [--base <ref>]`: affected tests not run, callers not looked at, routes not exercised |
| See the whole graph | `ledger tree` |
| At the end | `ledger close`: proven bug causes and decisions go to project memory |

`fact --run` stores the command, exit code, and up to three decisive output lines, plus fingerprints of `--files`; editing those files later makes requirement evidence stale until you rerun it. A red run before a fix proves a hypothesis and stays valid. Never mark a requirement done without a fact; `prove` reports such entries. The ledger is `.git/task-ledger.json` in a Git project (`LEDGER_FILE` overrides), capped at 60 entries.
