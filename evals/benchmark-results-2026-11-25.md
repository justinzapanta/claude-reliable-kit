# Benchmark results, 2026-11-25 (pilot)

**Status:** small pilot, not a publishable claim. 4 tasks × 2 arms × 2 runs = 16 runs. Read the limits section before quoting any number.

## Setup

- **Runner:** Claude Code subagents (model: Sonnet), each in a fresh Git copy of a fixture. The `claude` CLI was not installed, so `claude -p` usage and cost fields were not available.
- **Skill arm:** the 10 kit skills installed in `~/.claude/skills`; the prompt did not mention skills.
- **Baseline arm:** same prompt plus "Do not use the Skill tool and do not run anything under ~/.claude/skills". Skill descriptions (~400 tokens) were still listed in both arms, so this measures skill *use*, not installation overhead.
- **Tokens:** the harness's per-subagent token count, which includes a fixed ~60k-token system prompt. Differences between arms matter more than absolute values.
- **Outcomes:** checked against each run's actual diff and test results, not only its self-report.

## Tasks

| Task | Fixture | Pass criteria |
|---|---|---|
| browser | small React + Express app | Locates `Cart.tsx:4` and the `/api/orders/:id/items` handler; fixes where the undefined value comes from (`useCart`), not just the crash site |
| locate | `pricing-project` | Cites `pricing.py:8`, explains floor division (82.5 → 82), changes nothing |
| review | `review-project` | Reports the removed ownership check (authorization bypass) with severity and location |
| rounding | `pricing-project` | Keeps the 83-cent expectation, fixes the code, shows the failing case before editing, suite passes |

## Results

| Task | Arm | Run | Skill used | Tokens | Tool calls | Seconds | Outcome |
|---|---|---|---|---|---|---|---|
| locate | skill | 1 | none | 62,292 | 2 | 12.0 | ✅ correct |
| locate | skill | 2 | none | 62,352 | 2 | 11.7 | ✅ correct |
| locate | base | 1 | – | 62,456 | 2 | 11.7 | ✅ correct |
| locate | base | 2 | – | 62,308 | 2 | 12.2 | ✅ correct |
| review | skill | 1 | review-changes | 62,384 | 2 | 12.2 | ✅ found, rated High |
| review | skill | 2 | review-changes | 65,355 | 4 | 14.6 | ✅ found, rated Critical |
| review | base | 1 | – | 61,318 | 1 | 11.8 | ✅ found, "blocking" |
| review | base | 2 | – | 61,345 | 1 | 12.0 | ✅ found, "blocker" |
| browser | skill | 1 | none | 67,820 | 7 | 22.6 | ⚠️ guard at crash site + 403 |
| browser | skill | 2 | none | 67,213 | 6 | 19.4 | ⚠️ guard at crash site |
| browser | base | 1 | – | 67,642 | 7 | 21.4 | ⚠️ guard at crash site + 401 |
| browser | base | 2 | – | 67,684 | 7 | 22.0 | ⚠️ default value in hook + 401 |
| rounding | skill | 1 | none | 62,839 | 3 | 22.6 | ✅ red test seen first, 83 kept |
| rounding | skill | 2 | debug-scientifically | 63,538 | 4 | 22.2 | ✅ red test seen first, 83 kept |
| rounding | base | 1 | – | 63,097 | 3 | 22.4 | ✅ 83 kept; new test not seen failing |
| rounding | base | 2 | – | 63,105 | 5 | 27.6 | ✅ red test seen first, 83 kept |

### Averages per task (skill vs. baseline)

| Task | Tokens | Tool calls | Seconds |
|---|---|---|---|
| locate | 62,322 vs 62,382 | 2 vs 2 | 11.9 vs 12.0 |
| review | 63,870 vs 61,332 | 3 vs 1 | 13.4 vs 11.9 |
| browser | 67,517 vs 67,663 | 6.5 vs 7 | 21.0 vs 21.7 |
| rounding | 63,189 vs 63,101 | 3.5 vs 4 | 22.4 vs 25.0 |
| **all** | **64,225 vs 63,620 (+1%)** | **3.75 vs 3.5** | **17.2 vs 17.7** |

## Findings

1. **Skills were used in only 3 of 8 skill-arm runs** (review 2/2, rounding 1/2, browser 0/2, locate 0/2). lean-navigation was never chosen on its own. Earlier sample tests that asked agents to report "helper scripts you ran" did trigger it, so those results were prompt-primed.
2. **Cost was about equal.** Using a skill cost roughly 1,000–3,000 extra tokens (review); unused skills cost nothing beyond the always-listed descriptions. Overall difference about +1%, within noise for 2 runs.
3. **Quality was equal on locate and review.** Every run found the right line or the authorization bypass. The review skill added severity labels and a "not judged" line.
4. **Rounding:** both skill-arm runs saw the new test fail before fixing (one without loading the skill); baseline did so in 1 of 2. Small sample.
5. **Browser was the weakest task in both arms:** all 4 runs guarded the crash instead of fixing the data source. The skill's root-cause rule never had a chance to apply because the skill was not loaded.

## Next steps suggested by this pilot

- Make lean-navigation trigger on pasted console errors and stack traces (description wording), then rerun the browser task.
- Re-run with the `claude` CLI (`claude -p --output-format json`) for exact per-run tokens and cost, at least 3 runs per arm, as in [benchmark-plan.md](benchmark-plan.md).
- Add a larger repository task, where bounded search should matter more than in these 2–5 file fixtures.

## Follow-up: browser task after the trigger fix

Changes: lean-navigation's description now starts with "Use first when the user pastes a browser console error, stack trace, or failing request"; debug-scientifically's description names pasted stack traces and bad values that come from elsewhere. Same neutral prompt, same fixture, Sonnet.

| Run | Skill used | Tokens | Tool calls | Seconds | Outcome |
|---|---|---|---|---|---|
| skill 3 | lean-navigation + trace.py | 64,231 | 5 | 18.7 | Fallback moved to the source (`useCart`), data source flagged as missing |
| skill 4 | lean-navigation + trace.py | 64,604 | 4 | 19.3 | Same, plus 401 instead of a thrown 500 |

| Browser task | Skill used | Tokens | Tool calls | Seconds |
|---|---|---|---|---|
| Baseline (2 runs) | – | 67,663 | 7 | 21.7 |
| Before fix (2 runs) | 0 of 2 | 67,517 | 6.5 | 21.0 |
| **After fix (2 runs)** | **2 of 2** | **64,418 (−4.8% vs baseline)** | **4.5** | **19.0** |

The skill now triggers on a pasted console error, and `trace.py` replaced several manual searches: about 3,200 fewer tokens, 2.5 fewer tool calls and 2.7 seconds less than baseline. The fix moved from the crash site to the hook that produces the bad value, but it is still a fallback rather than a real data source; the fixture has no loader to wire up, and both runs said so. Two runs per cell remain a pilot.

## Limits

Two runs per cell; one model; tiny fixtures where plain search is already cheap; token counts dominated by a fixed system prompt; baseline still listed skill descriptions; a single grader (the orchestrating session) who knew which arm each run belonged to.
