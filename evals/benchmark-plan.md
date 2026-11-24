# Comparative benchmark plan

## Question

Do these kit skills improve Claude Code outcomes over stock Claude Code, and do they add value over established community skills, without adding unnecessary steps, tokens, or time?

This benchmark is not a popularity contest. Compare equivalent workflows on the same tasks and repository fixtures. Do not load overlapping skills together in the same arm.

## Arms

Run each prompt in a fresh Claude Code session, with the same Claude model/version, permission mode, repository snapshot, tools, and user message:

1. **Stock:** current Claude Code with bundled skills enabled and no custom workflow skill. This is the real baseline, not a hypothetical unskilled model.
2. **Reliable Kit:** stock plus only the one relevant kit skill for that eval.
3. **Superpowers:** stock plus the matching Superpowers skill for TDD, debugging, planning, or review.
4. **Matt Pocock skills:** stock plus the matching `grill-me`, `handoff`, `tdd`, or `code-review` skill where the eval matches.

Record the Claude Code version, model identifier, plugin versions/commits, date, permission mode, and any model settings. Do not compare different Claude models across arms. Run at least three fresh sessions per task and arm; run order should rotate so one arm is not always first. Store exact inputs and outputs without removing failed attempts.

## Tasks and matched workflow

Use the machine-readable prompts and pass criteria in [cases.json](cases.json), with context in [tasks/README.md](tasks/README.md). Keep fixtures identical. Give every run a fresh copy of its fixture; never reuse a directory modified by a previous arm. Suggested matched comparisons:

| Eval family | Reliable Kit | External comparator | Stock Claude Code capabilities to leave enabled |
|---|---|---|---|
| Ambiguous request / planning | `ask-smart`, `plan-work` (separate evals) | Matt `grill-me`; Superpowers brainstorming/writing-plans | Plan mode, normal prompting |
| Bug fix / tests | `tdd-loop`, `debug-scientifically` (separate evals) | Superpowers TDD/systematic-debugging; Matt `tdd` | Bundled `/debug`, `/verify`; normal test workflow |
| Diff review | `review-changes` | Superpowers requesting-code-review; Matt `code-review` | Bundled `/code-review` |
| Resume work | `session-handoff` | Matt `handoff` | `--continue` / `/resume` |
| Code navigation | `lean-navigation` | No forced external skill; optionally test bundled code intelligence separately | Normal search/read tools |

The kit has no external counterpart for several existing skills. Report those as kit-versus-stock only; do not invent a competitor arm.

## Scoring

Grade each run against the written expectations in the eval table, without seeing which arm produced it where practical. For each expectation, record pass/fail and a short quote or artifact path as evidence. Also record:

- **Outcome:** required behavior correct and complete; security-sensitive cases must not introduce a vulnerability.
- **Verification honesty:** commands that were run and their actual results; no unsupported success claims.
- **Workflow fit:** required steps followed, and negative-control prompts did not trigger unnecessary interviews, plans, files, or test ceremonies.
- **Cost:** input/output tokens, tool calls, elapsed time, and errors. Compare medians and ranges across repetitions.

Do not combine these into one score until the weights are declared. Report per-eval pass rate and cost deltas. A skill wins only if it improves important outcomes or materially reduces cost without a meaningful correctness regression. If outputs vary substantially across three runs, expand repetitions before drawing a conclusion.

## Run with Claude Code

Use the official Claude Code skill-evaluation workflow where available. Anthropic documents fresh-session baseline comparisons, `skillOverrides` to turn off a personal/project skill, and evals with assertions; plugin comparisons can use `claude plugin eval`. Keep the kit arm limited to the matching skill. For community plugins, pin versions/commits and run their arm separately.

Save a run record beside this file or in a dated ignored output directory. Never publish tokens, transcripts, private fixture data, or credentials. If running through the official skill-creator plugin, follow its eval schema and preserve its output artifacts.

## Report template

| Eval | Arm | Runs | Expectations passed | Median tokens | Median seconds | Median tool calls | Failures / notes |
|---|---|---:|---:|---:|---:|---:|---|
| | | | | | | | |

Below the table, list model/runtime and skill/plugin versions, explain any missing runs, and state whether the evidence supports a win, tie, loss, or inconclusive result per eval. Do not call a document audit a model benchmark.

## Regression controls

Apply each case’s optional setup in its fresh fixture copy before starting the session. For case 10, make the outline helper available to every arm at the same path and include its invocation in the prompt. Score preservation of pre-existing edits, correct handling of partial evidence, and simple-task overhead separately. For each arm report total tokens across all attempts divided by the number of correct outcomes, alongside the pass count. If none pass, report the ratio as undefined.

To check the pricing fixture from its project directory (`evals/fixtures/pricing-project/`), run `python -m unittest discover -s tests`. The three baseline tests cover existing behavior. The rounding failure is intentional input for the repair cases.
