# Claude Reliable Kit

**Claude Code skills for code navigation, debugging, and code review.**

[Quick start](#install-claude-code-skills-in-a-repository) · [Skill catalog](#choose-a-developer-skill) · [Download skills](releases/) · [Contribute](CONTRIBUTING.md)

Find where a feature lives, trace a failing test to its cause, and review a patch for regressions. **Claude Reliable Kit** is an MIT-licensed collection of 10 developer skills for Claude Code and Claude.ai. Each skill covers one task. Start with [Lean Navigation](skills/lean-navigation/SKILL.md) if your main problem is finding the right code in an unfamiliar repository.

## Install Claude Code skills in a repository

**One command** (Python 3.9+, no dependencies). Run it from your project folder; preview first with `--dry-run`:

```sh
python path/to/claude-reliable-kit/install.py --all            # skills in ~/.claude/skills + rules + memory hook + seeded memory
python path/to/claude-reliable-kit/install.py --all --project . # same, but inside this project so your team gets it on commit
python path/to/claude-reliable-kit/install.py --uninstall      # remove skills, the CLAUDE.md block, and the hook
```

| Flag | What it does |
|---|---|
| (none) | Copies the 10 skills; removes the 3 skills merged into `engineering-principles` if they carry the installer ownership marker |
| `--claude-md` | Adds the rules from [templates/CLAUDE.md](templates/CLAUDE.md) to your `CLAUDE.md` in a marked block. **Recommended:** skills load only when Claude decides they fit, and for a one-line edit it usually decides they don't. In our benchmark, project memory stopped a change that broke a recorded legal decision in 3/3 runs with these rules and 0/3 without them |
| `--hook` | Registers a Claude Code hook: the first time Claude edits a file with recorded decisions, the edit pauses once and shows them. Works even when no skill loads. Backs up `settings.json` first |
| `--seed` | Fills project memory from fix commits and warning comments (`NOTE:`, `WARNING:`, `DO NOT`) so it is useful on day one |
| `--lean-replies` | Adds optional rules for shorter answers; output tokens cost the most |
| `--all` | `--claude-md --hook --seed` |

Unmarked skill folders (including manual installs) are preserved. If one conflicts, back it up and move it aside before upgrading. Use `--force` only to deliberately replace a conflicting active skill.

**By hand:** copy the contents of `skills/` into `~/.claude/skills/` (or `.claude/skills/` in a project) and paste [templates/CLAUDE.md](templates/CLAUDE.md) into your `CLAUDE.md`. Then open Claude Code and try:

> /lean-navigation Find where checkout calculates tax. Show me the definition, one caller, and the rounding rule.

**Using Claude.ai chat?** Choose a [packaged skill ZIP](releases/) and upload it in your Skills settings. Provide the files for the task in that chat. Local repository searches require access to the project files and a Python 3 execution environment.

### Make the skills trigger when you need them

Claude decides on its own when to load a skill, and on small, clear tasks it often skips them. Two ways to get the workflow you want:

- **Call a skill by name** when it matters: `/lean-navigation` for a pasted browser error, `/tdd-loop` for test-first fixes, `/review-changes` before a merge.
- **Add these lines to your project's `CLAUDE.md`.** That file is read in every session, so the rules apply even when no skill loads:

```markdown
- Before editing a file, run `python ~/.claude/skills/task-ledger/scripts/memory.py recall --file <path>` and respect recorded decisions.
- For a pasted browser console error, stack trace, or failing request, run lean-navigation's trace.py before searching by hand.
- Fix where a bad value is produced, not only where it crashes; a `?.` guard alone is not a fix.
- For a bug fix with a test suite, write the failing test and see it fail before changing code.
- Run long test or build commands through `python ~/.claude/skills/lean-navigation/scripts/squeeze.py -- <command>`.
```

Use `.claude/skills/...` instead of `~/.claude/skills/...` if you installed the kit inside the project. A ready-to-copy version is in [templates/CLAUDE.md](templates/CLAUDE.md).

## How Lean Navigation finds relevant code

Claude can select an installed skill from its description or you can invoke it by name. Its `SKILL.md` gives Claude a search strategy. When the file is known, it reads the relevant lines. When only a symbol or error is known, the Python helper searches the project and returns short excerpts with paths and line numbers. The default search shows up to six matches within a 1,600-character output budget.

Try this from the root of the downloaded kit using the included pricing fixture:

```sh
python skills/lean-navigation/scripts/find.py tax_cents evals/fixtures/pricing-project --symbol --ext py
```

The result points to the definition at `pricing.py:4` and its caller at `pricing.py:12`. Reading the return expression at line 8 explains the behavior: integer division rounds fractional cents down. A location question can stop at the first match. A rounding bug warrants the extra read and a focused test. [Example source](evals/fixtures/pricing-project/pricing.py)

`--symbol` ranks definitions first in Python, JS/TS, Go, Rust and similar languages, and lists test files last. When nothing matches, it suggests similar names that really exist, so Claude stops guessing spellings.

For a regression after local edits, add `--changed` to search staged, unstaged, and new unignored files in a Git working tree.

### Browser error to source in one call

Paste a console error, stack trace, or failing request into `trace.py`. It maps stack frames to project files, matches `/api/orders/8812` to a route like `/api/orders/:id`, skips `node_modules` and bundler chunks, and searches identifiers and fixed message text in one bounded pass:

```sh
python skills/lean-navigation/scripts/trace.py --dir path/to/project "Uncaught TypeError: Cannot read properties of undefined (reading 'items')
    at Cart (http://localhost:5173/src/components/Cart.tsx?t=1712:4:22)
GET http://localhost:5173/api/orders/8812/items 500"
```

Output is one `path:line: excerpt` list per clue, within about 1,600 characters. Capturing the error itself needs a browser tool in the session; the skill tells Claude to check console errors and failed requests before snapshots, and to screenshot only for visual questions.

### Code graph: folders, symbols, callers, and what a change can break

`graph.py` indexes the project into folder, file, and symbol nodes with import, call, test, and route edges (Python via `ast`; JS/TS, Go, Rust and similar via patterns). The index lives in `.git/lean-graph.json`, so it is never committed, and only changed files are re-parsed.

```sh
python skills/lean-navigation/scripts/graph.py tree --dir .            # folder nodes: files, key symbols, folder-to-folder imports
python skills/lean-navigation/scripts/graph.py node tax_cents --dir .  # definition, callers and indirect callers, importers, tests, memory
python skills/lean-navigation/scripts/graph.py brief tax_cents --dir . # node + recorded memory + recent commits: one call before editing
python skills/lean-navigation/scripts/graph.py impact --dir .          # changed symbols -> callers, importers, tests to run, routes
python skills/lean-navigation/scripts/graph.py routes /api --dir .     # Express, Flask, FastAPI, Next.js, SvelteKit, Remix routes
```

`node` and `impact` also show indirect callers, one hop further (for example `order_total` reaching `to_cents` through `best_discount`), and any project memory recorded on the files involved. `impact` reads your Git diff, finds the functions you actually touched, and lists who calls them, which files import them (two levels), which tests to run, and which routes are affected, with a low/medium/high blast-radius hint. `review-changes` starts from it, so a review reads only what the change reaches. Callers are matched by name, so dynamic dispatch is not tracked.

### Compact command output

`squeeze.py` runs a command and returns only what decides the next step: failures, tracebacks, errors, warnings, and summary lines, with progress bars, colors, repeated lines, passing tests, and diff context removed. It keeps the command's exit code and saves the full output to a file it names, so nothing is lost.

```sh
python skills/lean-navigation/scripts/squeeze.py -- python -m pytest -q
python skills/lean-navigation/scripts/squeeze.py -- git status
```

On a 310-test run that printed 537,913 characters, output was 1,680 characters (-99.7%) with the failing assertion, traceback, and summary intact. `squeeze.py --gain` compares raw output with the entire printed reply, including its footer. Short commands can cost extra characters. New totals start fresh after this accounting change. Token counts are estimates.

### Project memory graph

`task-ledger`'s `memory.py` keeps what was learned (decisions, bugs, gotchas, concepts, preferences) as short memories linked to files and to each other, so Claude can jump to past context instead of re-reading the repo.

```sh
python skills/task-ledger/scripts/memory.py add bug "Floor division gave 82 instead of 83 cents" --files shop/core/pricing.py --tags tax
python skills/task-ledger/scripts/memory.py recall --changed     # everything known about the files you are editing
python skills/task-ledger/scripts/memory.py recall --file tests/test_pricing.py   # also finds memories on imported/importing files
python skills/task-ledger/scripts/memory.py stale                # memories whose files changed since they were recorded
```

Recall ranks the exact file first, then files one import away (using the code graph above), then the same folder. Memories live in `.git/lean-memory.json`, private and never committed; set `LEAN_MEMORY_FILE` to a committed path to share them with a team. Obvious secret values are refused.

```sh
python skills/task-ledger/scripts/memory.py seed --dry-run      # preview memories found in fix commits and warning comments
```

**Memory hook.** `memory_hook.py` is a Claude Code `PreToolUse` hook for Edit/Write. The first time in a session that Claude edits a file with recorded decisions, gotchas, or bugs, the edit pauses once with those memories as the reason; Claude reads them, then retries or stops and asks. Files with memories only on their imports get a note instead of a pause, and nothing else is ever blocked. `LEAN_MEMORY_HOOK=note` never pauses; `LEAN_MEMORY_HOOK=off` disables it. Install it with `install.py --hook`.

### Evidence graph: prove a task is done

Inspired by the two linked graphs in [ARTEX](https://github.com/BaaRai/ARTEX) (a map of what exists, and a per-task record of what was tried and what proved it), applied to coding instead of security testing. The code graph and project memory are the map; `task-ledger`'s `ledger.py` is the per-task exploration graph:

```sh
python skills/task-ledger/scripts/ledger.py goal "Free shipping at exactly $75"
python skills/task-ledger/scripts/ledger.py add req "Orders of exactly 7500 cents ship free"
python skills/task-ledger/scripts/ledger.py hypo "shipping_cost uses > instead of >=" --files backend/services/shipping.py
python skills/task-ledger/scripts/ledger.py fact "red before fix" --run "python -m unittest tests.test_shipping_rules" --expect-exit 1 --proves 3
python skills/task-ledger/scripts/ledger.py fact "green after fix" --run "python -m unittest discover -s tests" --proves 2 --files backend/services/shipping.py
python skills/task-ledger/scripts/ledger.py prove      # requirements without passing, current evidence (exit 1 if any)
python skills/task-ledger/scripts/ledger.py coverage   # affected tests not run, callers not looked at, routes not exercised
python skills/task-ledger/scripts/ledger.py tree       # goal -> requirements and hypotheses -> the evidence on each
python skills/task-ledger/scripts/ledger.py close      # proven bug causes and decisions go to project memory
```

Every fact stores the command, its exit code, the decisive output lines, and fingerprints of the files it covers, so editing those files makes the proof stale until it is rerun. `debug-scientifically`, `tdd-loop`, `engineering-principles`, `review-changes`, `plan-work`, `session-handoff`, `ask-smart`, and `edge-case-security` each use it at the step where they claim something.

### How the skills work together

| Moment | Skill | Uses |
|---|---|---|
| Vague request | `ask-smart` | one round of questions with defaults |
| Multi-step work | `plan-work` | `graph.py tree`/`node` for the code path, `memory recall` for past decisions |
| Pasted error or "where is X" | `lean-navigation` | `trace.py`, `find.py`, `graph.py node` |
| Bug | `debug-scientifically` | `trace.py` or `graph.py brief` first; hypotheses and red/green runs in the evidence graph; `ledger close` saves the cause |
| Fix or feature with tests | `tdd-loop` | red and green runs recorded as evidence; `squeeze.py` for long test output |
| Any edit | `engineering-principles` | `graph.py brief` before editing; `ledger prove` and `coverage` before "done" |
| Before merge | `review-changes` | `graph.py impact` (blast radius plus memory), `ledger coverage --base` for what nothing exercised |
| Untrusted input or auth | `edge-case-security` | trust boundaries, abuse-case test |
| Long task | `task-ledger` | evidence graph: requirements, hypotheses, facts; `prove`, `coverage`, `tree`, `close` |
| Pausing | `session-handoff` | `ledger tree` as the evidence section; lessons saved to memory |

Each skill works alone; when the others are installed it calls their scripts instead of re-reading code.

### Credits

Ideas adapted, in our own code and words, from [Code Review Graph](https://github.com/tirth8205/code-review-graph) (code graph and change impact), memory-graph tools for agents (linking decisions and bugs to files), [RTK](https://github.com/rtk-ai/rtk) (compressing command output and reporting savings), [caveman](https://github.com/JuliusBrussee/caveman) (shorter replies), [obra/superpowers](https://github.com/obra/superpowers), [Matt Pocock's skills](https://github.com/mattpocock/skills), [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills), [ECC](https://github.com/affaan-m/ECC), and Anthropic's skill-authoring guide. Those projects are larger and more complete; this kit trades breadth for zero install and small, bounded output.

## Choose a developer skill

### Explore and diagnose

| Skill | When to use it |
| --- | --- |
| [lean-navigation](skills/lean-navigation/SKILL.md) | Reads too much. Code graph (folders, callers, change impact, routes), bounded search, `trace.py` for pasted browser errors, and `squeeze.py` for long test or build output. |
| [debug-scientifically](skills/debug-scientifically/SKILL.md) | Guess-and-patch. Reproduce, rank hypotheses, test the cheapest one. |

### Plan and implement

| Skill | When to use it |
| --- | --- |
| [ask-smart](skills/ask-smart/SKILL.md) | Wrong assumptions, or too many questions. Ask only when the answer changes the result. |
| [plan-work](skills/plan-work/SKILL.md) | One assistant coordinates product, engineering, delivery, and QA decisions for complex tasks. |
| [engineering-principles](skills/engineering-principles/SKILL.md) | Code that doesn't fit the project, sprawling rewrites, or "done" without proof. Copy the nearest working example, make the smallest diff, then run a real check before reporting. |
| [tdd-loop](skills/tdd-loop/SKILL.md) | Implementing before knowing what success means. Red-green-refactor with a verified failure and targeted tests. |

### Review and hand off

| Skill | When to use it |
| --- | --- |
| [review-changes](skills/review-changes/SKILL.md) | Bugs hiding in a broad diff. Review the actual changes for correctness, regressions, and security. |
| [edge-case-security](skills/edge-case-security/SKILL.md) | Happy-path-only code. Systematic edge-case and security pass. |
| [task-ledger](skills/task-ledger/SKILL.md) | Losing requirements on long tasks; forgetting preferences. 30-entry ledger plus lean memory, stored in `.git/` so it is never committed. |
| [session-handoff](skills/session-handoff/SKILL.md) | Work that must continue in another session. Leave a concise, evidence-based resume note. |

## Does the kit save Claude tokens?

The local search scripts make no model requests. Returning a short excerpt limits how much tool output reaches Claude. Total usage also depends on how often Claude searches, what it reads next, and whether it solves the task correctly. Results so far, all on Sonnet with 3 runs per arm ([full results](evals/benchmark-results-2026-11-25-shop-app.md), reproducible with `evals/fixtures/make_shop_app.py`):

| Task (86-file app) | Kit vs. plain Claude | Notes |
|---|---|---|
| Pasted browser error | 61.8k vs 64.8k tokens (-4.6%), 3/3 vs 3/3 correct | `trace.py` maps the error and surfaces project memory in one call |
| Review a change | +0.6% tokens, 3/3 vs 3/3 | Kit quotes the recorded decision the change breaks and lists affected routes |
| "What breaks if I change X?" | -0.6% tokens, 3/3 vs 3/3 | Kit lists all 8 call sites with lines, plus recorded decisions |
| Failing test suite | equal | No skill needed |
| Fact only in project memory | **3/3 vs 0/3** with `templates/CLAUDE.md`; 0/3 with the kit alone | The CLAUDE.md rule is what makes Claude check memory before a small edit |
| 538k-character test log | `squeeze.py`: 537,913 -> 1,680 characters (-99.7%) | Agents filtered with `grep` on their own, so no token difference in runs |
| 5-requirement change with the evidence graph | +10-14% tokens, 3/3 vs 3/3 | Kit wrote the failing test first 3/3 vs 0/3; `ledger prove` + `coverage` tied each requirement to a passing run and listed untested changed files |

Overall: about 1% fewer tokens than plain Claude with equal accuracy, plus context plain Claude cannot see (recorded decisions, indirect callers). An earlier [16-run pilot](evals/benchmark-results-2026-11-25.md) on smaller fixtures showed the triggering gaps these results fixed. The [benchmark plan](evals/benchmark-plan.md) tracks correctness, tokens, time, and tool calls across comparable runs.

## How the kit is tested

`python tools/check.py` runs 94 unit and lint tests, checks the release ZIPs, and fuzzes every script with random and malformed input; `--full` adds a 6,000-file stress repository (graph index in about 4 s). CI runs it on Windows, macOS, and Linux. An adversarial review and real-repository workbench (Flask, Express, FastAPI) found 20 bugs, all fixed with regression tests; see [evals/workbench-2026-11-25.md](evals/workbench-2026-11-25.md).

## Evaluate or contribute

The [evaluation cases](evals/cases.json) include a rounding bug where a lead and tester recommend the wrong fix. The expected behavior is to reproduce the failure and check the stated rounding rule before changing code or test expectations. To contribute a case, include the prompt, the smallest shareable fixture, and an outcome someone else can verify. [Contributor guide](CONTRIBUTING.md) · [MIT license](LICENSE)
