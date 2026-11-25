# Benchmark results, 2026-11-25: shop-app (round 2)

**Status:** 24 runs, 4 tasks × 2 arms × 3 runs. Still a pilot (one model, one fixture), but repeatable: regenerate the exact fixture with [fixtures/make_shop_app.py](fixtures/make_shop_app.py).

## Setup

- **Fixture:** `make_shop_app.py --task <task> --memory`: 86 files (Python backend with 9 API modules and 10 services, React/TS frontend, 208 tests), plus 4 seeded project memories in `.git/lean-memory.json`.
- **Runner:** Claude Code subagents on Sonnet, one fresh fixture per run, neutral prompts that never mention skills.
- **Skill arm:** the kit installed in `~/.claude/skills`. **Baseline arm:** same prompt plus "Do not use the Skill tool and do not run anything under ~/.claude/skills".
- **Tokens:** harness per-run count, including a fixed system prompt of about 60k tokens.
- **Grading:** against the ground truth the generator prints, checked from each run's final answer and diff.

## Tasks

| Task | Prompt (short) | Ground truth |
|---|---|---|
| browser | Cart page crashes for some visitors; pasted `reading 'lines'` stack trace | Root cause in `useCartTotals.ts`: `cart` is `null` for guests; fix there |
| review | "Review my uncommitted changes" | Diff makes coupons stack with sale prices, breaking a recorded finance decision and a test |
| impact | What breaks if `to_cents` returns Decimal, which tests to run? | 8 call sites in 5 service files; tests `test_tax`, `test_pricing`, `test_discounts` |
| tests | "The test suite is failing, fix it" (208 tests, 1 failure) | Floor division in `tax.py`; half-up fix; suite green |

## Results (averages of 3 runs)

| Task | Arm | Skill used | Tokens | Tool calls | Seconds | Correct | Extra context in the answer |
|---|---|---|---|---|---|---|---|
| browser | skill | 3/3 (lean-navigation + debug-scientifically, trace.py) | 70,324 | 5.0 | 25.7 | 3/3 | 3/3 cited the guest-cart memory |
| browser | base | – | 64,773 | 5.0 | 24.6 | 3/3 | inferred from `cart.py` |
| review | skill | 3/3 (review-changes, graph.py impact) | 64,673 | 4.0 | 28.1 | 3/3 | 3/3 quoted the finance decision; listed affected routes |
| review | base | – | 64,268 | 3.0 | 23.2 | 3/3 | inferred the rule from the failing test and old docstring |
| impact | skill | 3/3 (lean-navigation, graph.py node) | 70,247 | 4.7 | 29.8 | 3/3 | 3/3 all 8 call sites with lines; cited money memories |
| impact | base | – | 70,683 | 4.7 | 27.9 | 3/3 | all 5 files; lines in 2/3 |
| tests | skill | 0/3 | 62,599 | 3.0 | 16.2 | 3/3 | – |
| tests | base | – | 62,745 | 3.0 | 15.9 | 3/3 | – |
| **all** | **skill** | **9/12** | **66,961** | **4.2** | **25.0** | **12/12** | |
| **all** | **base** | – | **65,617** | **3.9** | **22.9** | **12/12** | |

## Findings

1. **Correctness was equal: 24/24.** On this fixture Sonnet finds every root cause, regression, and caller without help.
2. **Cost: +2.0% tokens overall with the kit.** Impact was 0.6% cheaper, tests equal, review +0.6%, browser +8.6%. The browser runs loaded two skills (lean-navigation and debug-scientifically), about 5,500 tokens of instructions, which the shorter path did not need here.
3. **The kit changes what Claude knows, not whether it succeeds.** Skill runs quoted recorded decisions (review 3/3, impact 3/3, browser 3/3) and gave exact call-site lines (impact 3/3 vs 2/3). Baseline runs reached the same conclusions from code comments and tests, which this fixture happens to contain; in a real repo where the rule lives only in someone's head or a past incident, memory is the only source.
4. **Skills now trigger reliably for navigation, review, and impact (9/12, up from 3/8 in round 1),** but not for a plain failing test suite (0/3); `squeeze.py` was never used because the `unittest -v` output of 208 tests was small enough to read directly.
5. **Token savings are not shown yet.** Even at 86 files the code is short enough that `grep` and `cat` stay cheap. Bounded search and `squeeze.py` should matter when files are long, logs are large, or the repo is thousands of files.

## Changes this suggests

- Avoid loading two skills for one browser error: lean-navigation already covers tracing, so debug-scientifically's description should defer to it for pasted errors, or lean-navigation should carry the one root-cause rule it needs.
- Test `squeeze.py` where it matters: a build or test log over ~20k characters.
- Add a fixture where the deciding fact exists only in project memory (not in tests or docstrings), to measure memory's real value.
- Re-run on a second model before publishing numbers.

## Round 3: fixes from this round, re-measured

**Change 1:** pasted browser errors now load only lean-navigation (debug-scientifically's description defers to it; lean-navigation carries the root-cause rule).

| Browser task | Skills loaded | Tokens | Tool calls | Seconds | Correct |
|---|---|---|---|---|---|
| Baseline (round 2) | – | 64,773 | 5.0 | 24.6 | 3/3 |
| Kit before fix (round 2) | lean-navigation + debug-scientifically | 70,324 | 5.0 | 25.7 | 3/3 |
| **Kit after fix** | **lean-navigation only (3/3), trace.py** | **61,814 (-4.6% vs baseline)** | 4.7 | 23.2 | 3/3 |

With this fix the round-2 totals become **64,833 (kit) vs 65,617 (baseline), -1.2%**, with equal accuracy.

**Change 2:** a noisy-log task (`make_shop_app.py --task noisy`): 310 tests print 537,913 characters; one real failure (`>` instead of `>=` at the free-shipping threshold).

- `squeeze.py` on that run: **537,913 -> 1,680 characters (-99.7%)**, keeping the failing test, the `695 != 0` traceback, the summary, and exit code 1.
- Agent runs: kit 61,480 tokens / 4.7 calls / 28.7 s; baseline 62,103 / 4.3 / 28.3 s; correct 3/3 each. **No run loaded a skill or used `squeeze.py`**: every run, with or without the kit, filtered the log with `grep` or a redirect, and the tool's own output cap kept the raw log out of context. So in this harness `squeeze.py` saves effort only when called explicitly, for example by `tdd-loop` or from a `CLAUDE.md` rule.

## Round 4: a fact that exists only in project memory

Fixture: `make_shop_app.py --task memory --memory [--claude-md]`. Request: "extend the refund window from 30 to 60 days". Memory #5 (and nothing in code, tests, or docs) says the window stays 30 days for legal and chargeback reasons, and longer goodwill returns go through store credit. **Pass** = does not silently change the limit; cites the decision and asks or proposes store credit. The CLAUDE.md arm received `templates/CLAUDE.md` as project instructions at the top of the prompt, the way Claude Code loads it.

| Arm | Passed | Tokens | Tool calls | Seconds | What happened |
|---|---|---|---|---|---|
| Baseline | 0/3 | 65,104 | 4.7 | 16.7 | Changed 30 to 60 |
| Kit only | 0/3 | 64,901 | 4.3 | 15.8 | No skill loaded for a one-line edit; changed 30 to 60 |
| **Kit + CLAUDE.md** | **3/3** | **64,931** | **2.0** | 17.1 | Ran `memory.py recall` and `graph.py node`, quoted decision #5, stopped and asked, offered the store-credit path |

**Finding:** project memory only helps if something makes Claude look at it before a small edit. Skill descriptions alone did not (0/3); the one-line `CLAUDE.md` rule did (3/3), at the same token cost and with fewer tool calls. The kit's README now treats `templates/CLAUDE.md` as part of installation.

## Round 5: evidence graph on a multi-requirement change

Request: a 5-requirement pricing change in the shop app (free-shipping boundary, VIP and welcome-code shipping rules, per-state tax), with the evidence-graph rule in `templates/CLAUDE.md`. **Pass** = all requirements correct, checked by a script against the final code.

| Arm | Passed | Tokens | Seconds | Red test first | Used the ledger |
|---|---|---|---|---|---|
| Baseline | 3/3 | 68.9k | 37 | 0/3 | - |
| Kit, round A | 3/3 | 75.0k | 65 | 3/3 | 1/3 |
| Kit, round B (after quick-path fix) | 3/3 | 78.6k | 56 | 3/3 | 2/3, both ran `prove` and `coverage` |
| Kit, round C (after `--files` fix) | 3/3 | 78.1k | 50 | 3/3 | 2/3, `prove` only; 0 script errors (round B: 2) |

**Fixes between rounds:** `ledger.py add req` takes several requirements at once and `fact --proves all` proves them all, so the proof is 3 commands; the CLAUDE.md rule now shows that path. In round B, `coverage` flagged changed files with no test (`checkout.py`, routes) that the runs then covered. Two round-B runs failed their first `memory.py add --files a b` (space-separated); `--files` in `memory.py` and `ledger.py` now accepts commas, spaces, or repeated flags, with regression tests. Round C confirmed it: every run saved memories with `--files` (5-6 each) and no script command failed. Two of three round-C runs also flagged an ambiguity unprompted (VIP20 free shipping even when a sale price beats the coupon) instead of guessing silently. No round-C run used `coverage`; the CLAUDE.md rule lists it as optional ("when you changed shared code"), so adoption is left as is.

**Finding:** the evidence graph does not change accuracy on a task Claude already solves; it costs about 10-14% more tokens and buys a recorded proof (red test first, every requirement tied to a passing run, untested changed files listed). Use it for multi-step or risky work, not one-line edits.

## Limits

One model (Sonnet); one synthetic fixture with helpful docstrings and tests; 3 runs per cell; token counts dominated by a fixed ~60k system prompt; grader (the orchestrating session) knew each run's arm.
