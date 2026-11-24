# Benchmark status and static comparison

**Status:** no live model A/B runs have been performed. This checkout has no `claude` executable and no Anthropic API key, so recording Claude pass rates, token counts, or timing would be fabricated. This file is a source-based capability audit and a starting hypothesis for the live benchmark in [benchmark-plan.md](benchmark-plan.md), not proof that the kit improves Claude.

**Fixture validation:** the original six-case JSON suite parsed, all referenced fixtures exist, IDs are unique, the pricing fixture's current three tests pass, and the review patch applies cleanly with `git apply --check`. These checks validate benchmark inputs only; they do not measure Claude or establish that any skill works better.

Research checked on 24 November 2026. Claude Code behavior can change; record exact versions when running the benchmark.

## Stock Claude Code already covers

Anthropic's current docs list bundled `/debug`, `/code-review`, and `/verify` skills. Claude Code also supports plan mode, session resume with `--continue` / `/resume`, and common test workflows. Personal/project skills can extend these flows, and Anthropic recommends comparing fresh sessions with and without a skill, grading expectations, and tracking pass rate, token use, and time. This makes stock Claude Code the meaningful baseline, rather than an imagined model with no workflows. Sources: [bundled skills and evaluation guidance](https://code.claude.com/docs/en/skills), [common workflows](https://code.claude.com/docs/en/common-workflows), [project memory](https://code.claude.com/docs/en/memory).

## Kit fit versus established alternatives

This table compares the written scope of each workflow. “Overlap” means Claude Code or a community skill already documents a similar workflow. “Possible distinction” is a hypothesis to test, not a measured advantage.

| Kit workflow | Stock Claude Code overlap | Community reference | Possible distinction worth testing |
|---|---|---|---|
| `ask-smart` | Plan mode supports a review checkpoint; normal prompting handles clarification | Matt Pocock `grill-me` | Bounded, decision-changing questions and proceeding on reversible assumptions may use less time than a thorough interview. Test whether it still catches requirements the user cares about. |
| `plan-work` | Plan mode already inspects and proposes before edits | Superpowers brainstorming/writing-plans; planning-with-files | Lightweight planning without mandatory files may be lower overhead for medium work. Test completion and missed requirements, not plan length. |
| `tdd-loop` | Claude's test guidance covers adding/running tests; `/verify` checks behavior | Superpowers TDD; Matt `tdd` | Explicitly watching a focused test fail for the intended reason is the key differentiator. Measure correct red/green behavior and regression rate. |
| `debug-scientifically` | Bundled `/debug` exists | Superpowers systematic-debugging | The kit uses a shorter hypothesis loop. Test whether it finds root causes as reliably, especially after a first hypothesis fails. |
| `review-changes` | Bundled `/code-review` exists | Superpowers requesting-code-review; Matt `code-review` | Severity labels and a short actionable finding format may improve signal, but must not miss defects. |
| `verify-before-done` | Bundled `/verify` exists | Superpowers verification-before-completion | Strong overlap. This skill is a likely duplicate for Claude Code users and should be retained only if evals show a distinct benefit or it supports Claude.ai users. |
| `session-handoff` | `--continue` and `/resume` continue Claude sessions | Matt `handoff` | A portable handoff note can cross tools, accounts, or people; compare it with native session resume for fidelity and rework. |
| `task-ledger` | Auto memory and project instruction files persist selected context | planning-with-files | A task-specific requirement ledger may preserve explicit acceptance criteria better than general memory. Test requirement retention and duplicate bookkeeping cost. |
| `lean-navigation` | Claude can search and read files; code intelligence may add navigation | Planning-with-files emphasizes concise findings | The bundled capped-search and outline scripts offer deterministic output caps. Measure lines/tokens read and answer correctness on a large fixture. |
| `engineering-principles` | CLAUDE.md, auto memory, and prompt guidance already communicate rules | Karpathy-inspired guidelines | This is mostly a compact packaging of common guidance. Likely lower value as an extra skill; compare with placing concise durable rules in project instructions. |
| `minimal-change`, `read-before-write` | Common Claude Code guidance and repo context already support these behaviors | Karpathy-inspired guidelines; Superpowers YAGNI | Their value depends on measurable diff scope and convention adherence, not whether the model can repeat the rule. |
| `edge-case-security` | `/code-review` may inspect security; no guarantee every pass is comprehensive | Superpowers review workflows | A focused input/security checklist may catch more boundary defects. Measure true positives and false alarms on seeded cases. |

References: [Superpowers](https://github.com/obra/superpowers) (including [TDD](https://github.com/obra/superpowers/blob/main/skills/test-driven-development/SKILL.md) and [systematic debugging](https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md)); [Matt Pocock's skills](https://github.com/mattpocock/skills); [planning-with-files](https://github.com/OthmanAdi/planning-with-files); [Karpathy-inspired guidelines](https://github.com/multica-ai/andrej-karpathy-skills).

## Preliminary recommendations

1. Run matched evals before describing the kit as more reliable or cheaper. The README now says it is designed to reduce rework and context, and explicitly says savings have not been measured.
2. Prioritize distinctive tests: TDD's verified red step, compact handoff across tools, navigation output caps, and security boundary detection.
3. Test duplication directly: compare `verify-before-done`, `debug-scientifically`, `review-changes`, and `engineering-principles` against Claude Code's bundled workflows/instructions. Remove, merge, or narrow a skill if it adds no measurable value.
4. Keep negative controls. A planning skill that improves a large task but creates files or questions for a one-line edit may be a net regression.
5. For navigation, compare targeted search against optional mapping on the same large-repo tasks. Record answer accuracy, input/output tokens, tool calls, and elapsed time; do not use emitted bytes alone as a token-saving claim.
6. Check interaction cost when multiple skills are installed. Since descriptions remain in context, evaluate the bundle's always-loaded description overhead as well as the full skill body and workflow calls.

## Interpretation limits

- This audit evaluates documented workflow coverage, not actual generated code or Claude compliance.
- The public projects have different scopes and versions. Pin the exact commits used in a live comparison.
- Three runs per prompt are a small pilot, not a statistically strong generalization claim. Use more repetitions for close or high-variance results.
- Built-in Claude Code skill behavior is version-specific and may change; re-run stock controls with every tested Claude Code version.
