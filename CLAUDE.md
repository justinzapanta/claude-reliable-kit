# Working on Claude Reliable Kit

A kit of 10 Claude Code skills (`skills/`) with stdlib-only Python helpers, release ZIPs (`releases/`), tests (`tests/`), and benchmarks (`evals/`).

## Commands

- Before every commit: `python tools/check.py` (unit + lint tests, release ZIP check, quick fuzz; about 1-2 minutes)
- Before a release: `python tools/check.py --full` (adds deep fuzz and the 6,000-file stress test); add `--repos <dir>` to run the real-repository workbench
- A single test file: `python -m unittest tests.test_scripts -v`
- Rebuild release ZIPs after any change under `skills/`: `python tools/package_skills.py`, then `python tools/package_skills.py --check`
- Install into a sandbox to try changes: `python install.py --all --project <scratch-repo>` (`--dry-run` to preview, `--uninstall` to remove)
- Benchmark fixture: `python evals/fixtures/make_shop_app.py <out-dir> --task <browser|review|impact|tests|noisy|memory> --memory [--claude-md]`

## Rules

- Helpers stay standard-library Python 3 with no network access, and every command's output stays bounded (about 1,600 characters by default).
- Each skill description is at most 200 characters, third person, and includes "Use when"; `tests/test_skills.py` enforces this and the body-size limit. Descriptions load in every session, so every character costs tokens.
- Refer to another skill's script as `${CLAUDE_SKILL_DIR}/../<skill>/scripts/<file>.py` so it resolves when the kit is installed side by side.
- Hooks must never break editing: catch every error and exit 0 (`LEAN_HOOK_DEBUG=1` re-raises for debugging).
- Caches live inside `.git/` (`lean-graph.json`, `lean-memory.json`, `task-ledger.json`, `lean-hook-seen.json`, `lean-squeeze-stats.json`) so they are never committed. Bump `VERSION` in `graph.py` whenever parsing rules change.
- Keep the README skill catalog, `templates/CLAUDE.md`, and the "How the skills work together" table in sync with the skills.
- Write ideas from other projects in our own words and credit them in the README; never copy their text or code.
- Claims about cost or quality need a benchmark run recorded in `evals/`, with its limits stated.
- Every bug fix gets a regression test (see `HardeningTests`). Never write control characters into sources: `tests/test_skills.py` rejects them (a regex `` once became a backspace and silently broke a pattern).
