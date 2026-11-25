---
name: ui-design
description: Designs, builds, and checks UI. Use when making or reviewing a page, component, form, or theme.
---

# UI Design and Engineering

Design for this project, never a house style: read its world, pick what fits, make it its own, engineer it properly, and prove it. Helper: `python ${CLAUDE_SKILL_DIR}/scripts/design.py` (stdlib, short output; run it, don't read it). References, read when needed: [taste](references/taste.md), [craft](references/craft.md) (numbers, critique), [engineering](references/engineering.md) (components, ARIA, CSS, performance).

## 1. Context first

- `design.py tokens`: if the project has a design system, extend it; reuse its components (`lean-navigation` finds them). Never start a second palette.
- `python ${CLAUDE_SKILL_DIR}/../task-ledger/scripts/memory.py recall --file <style or component path>`: a saved design code or brand decision wins.
- The brief, brand, or screenshot beats taste. Unclear audience on a big build: `ask-smart`.

## 2. Direction for this project (new project or redesign)

1. Name the project's **world** (3 concrete things from its subject), **people** (who, how often, where), and **promise** (the feeling after use).
2. `design.py direction "<world, people, promise>" --dir .` (add `--brand <hex>` if there is a brand color). It ranks fitting directions and generates a design unique to this project: contrast-checked light and dark palettes, fonts, type ratio, radius, layout, signature, and what to avoid. Choose among the top fits by people and promise, not the industry word alone; blend two at most.
3. Add one **subject twist** from the world to the signature element. Ask: would this page still look right with a competitor's logo? If yes, push the twist.
4. Apply it: `design.py direction ... --css` gives tokens to paste into the token file. Save the design code: `memory.py add decision "Design: <code>, <fonts>" --files <token file>`. Later screens reuse it.

## 3. Build the feature like a design engineer

- `design.py pattern <feature>` (form, table, dashboard, search, checkout, settings, auth, modal, navigation, landing, and more) gives what the feature must include, its states, and its mistakes. Cover every line or say why it does not apply.
- Choose each component for the job, not by habit: `design.py choose "<what the user must do>"` (pick one of 4, delete a project, edit a row in context, show 2,000 invoices). Give a one-line reason for each non-obvious choice: "radio, not select: 3 options worth comparing".
- Tokens only (no raw hex or px outside the token file); themes swap variables, set before first paint.
- Components: fixed variants and sizes, native elements (`<button>`, `<a href>`, `<dialog>`, labelled inputs), every state: hover, focus-visible, active, disabled, loading, empty, error, long text. Custom widgets follow the ARIA pattern.
- Hierarchy from size, weight, and space before color. Body 16px, lines 60-75 characters, targets 24px minimum (44px touch).
- Motion: transform and opacity, ease-out, 150-300ms, reduced-motion fallback. Mobile first: no horizontal scroll at 320px.
- Copy: specific, sentence case, buttons say verb plus object. No filler or invented numbers.
- Unless the brief asks: no purple gradients, gradient text, emoji icons, identical icon-card grids, eyebrows everywhere, cards in cards.

## 4. Verify before saying done

1. `design.py audit --changed` (or paths). Fix every ERROR; fix each warning or say why it stays. Never edit the checker or a token to hide a finding.
2. If you can render: screenshots at 375, 768, 1280; no horizontal scroll; Tab through every control and overlay; dark mode.
3. Re-check the pattern list and remove one thing that does not earn its place.
4. Multi-part work: `python ${CLAUDE_SKILL_DIR}/../task-ledger/scripts/ledger.py fact "design audit clean" --run "python ${CLAUDE_SKILL_DIR}/scripts/design.py audit --strict --changed" --proves all` (`task-ledger`).

Stop after 3 fix rounds and report what is still open.

## Reviewing a design

Order: first impression, whether the main task is easy, fit to this project's people, hierarchy, consistency, accessibility, code health. Open with what works. Tag findings Blocker, High, Medium, or Nit, with evidence: measured (script or screenshot), judged, or needs a human. Top 3 fixes as Before | After | Why. Diffs: pair with `review-changes`.

## Report

Lead with the checks (audit result, widths rendered or "not rendered", keyboard pass), then the design code and why it fits, the twist, the component choices with their reasons, and what changed. Never call a UI accessible or responsive unless a check showed it.
