# Lean memory and persistence

Load this only when adding a `pref` entry or resuming a saved ledger.

## Memory rules (`pref` entries)

- Store **conclusions, not conversations**: "prefers Python + FastAPI, replies in Tagalog-English mix", not the chat that showed it.
- Write only when: the user says "remember", the user corrects you, or a preference appears twice.
- Newer facts overwrite older contradicting ones (the script's `add --replace <id>` does this).
- Mark source: `--src user` (stated) or `--src inferred` (guessed). Check inferred entries before relying on them.
- **Never store secret values or sensitive personal data.** Record the configuration name or secret manager reference when the task needs it.
- The user can see, edit, and delete everything. Show the ledger on request.

## Persistence (be honest with the user)

Inside a Git project the ledger is stored as `.git/task-ledger.json`, so it persists between sessions but is never committed. Outside Git it is `ledger.json` in the current directory. Set `LEDGER_FILE` to choose another path. `init` prints the location. In a temporary workspace, use `export` for a readable Markdown handoff (written next to the ledger). If the platform's Memory feature is on, prefer that for `pref` entries.
