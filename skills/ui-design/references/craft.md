# Craft reference

Read the section you need. Every number here is a default: the project's existing tokens and the user's brief win.

## Mode sets the ambition

| Mode | Examples | Spacing | Type ratio | Motion | Bold moves |
|---|---|---|---|---|---|
| Operate | app, dashboard, settings, admin | dense to standard (8-32px) | 1.125-1.2 | feedback only | none; clarity is the style |
| Read | docs, blog, help | standard (16-48px) | 1.2-1.25 | almost none | typography |
| Persuade | landing, pricing, sign-up | spacious (24-96px) | 1.25-1.333 | one authored moment | one signature element |
| Experience | portfolio, event, game | free | 1.333-1.618 | can lead | several, but intentional |

## Color

- Roles, not hues: bg, surface, surface-raised, text, text-muted, border, accent, accent-text, danger, success. Components use roles only.
- Contrast (WCAG 2.2 AA): body text 4.5:1; large text (24px, or 18.66px bold) 3:1; icons, borders of inputs, and focus rings 3:1 against their background. `design.py contrast` gives the nearest passing color.
- Muted text on a colored surface: tint it toward the surface hue instead of using grey.
- One accent used sparingly beats three. Status (error, success) never by color alone: add an icon or text.
- Dark mode is its own palette, not an inversion: background near #0b0b0c to #18181b rather than pure black, lighter surfaces for elevation instead of shadows, slightly less saturated accents, and every color token defined in both themes (`design.py audit` reports missing ones and checks dark-theme contrast).
- Set `color-scheme` and a `theme-color` meta that matches the background.

## Type

- 1-2 families: one for text, optionally one for display. Use the project's fonts; for a new brand page choose a face that fits the subject instead of the default sans.
- Body 16px (inputs at least 16px so iOS does not zoom), line height 1.4-1.6 for body, 1.1-1.3 for headings, measure 60-75ch (`max-width: 65ch`).
- 5-7 sizes from one scale (`design.py scale --ratio <r>`). Display text at most about 6rem; letter-spacing no tighter than -0.04em.
- Heading levels in order (no h1 to h3 jumps). `font-variant-numeric: tabular-nums` for numbers that are compared in columns. `text-wrap: balance` on headings.

## Space, shape, depth

- 4px grid: 4, 8, 12, 16, 24, 32, 48, 64, 96. Related items closer than unrelated ones; space above a heading larger than below it.
- 2-3 radii; a child's radius is never larger than its parent's.
- 2-3 elevation levels from tokens; shadows have both offset and blur, never pure black at high opacity.
- Layers: a named z-index scale (base, dropdown, sticky, overlay, modal, toast) instead of 9999.

## Components and states

Every interactive component: default, hover (only on `(hover: hover)` devices), focus-visible (2px ring, 3:1 contrast, not hidden under sticky headers), active, disabled. Data views add loading (a skeleton shaped like the result), empty (what to do next), error (what happened and how to fix it), and long content (truncate with `min-width: 0` on flex children, or wrap).

Forms: visible label above the field (a placeholder is not a label), help text before errors, the error next to its field, submit button stays enabled and explains what is missing.

## Motion

| Interaction | Duration | Easing |
|---|---|---|
| Button press | 100-160ms | ease-out, `scale(0.97)` |
| Tooltip, dropdown, menu | 150-250ms | ease-out |
| Modal, drawer | 200-400ms | ease-out to enter, faster exit |
| List stagger | 30-80ms per item | ease-out |

Animate only transform and opacity. Never `transition: all`, never ease-in for UI, never enter from `scale(0)` (start near 0.95 with opacity 0). Popovers grow from their trigger. Reduced motion means fade instead of move, not nothing. Skip animation on actions done many times a day.

## Responsive

Check 320 or 375, 768, 1024 or 1280, and 1440. No horizontal scroll at any width. Containers use `max-width`, not fixed widths. Never block pinch zoom. Touch targets 44px with 8px gaps on mobile (24px is the WCAG 2.2 AA minimum).

Render check, when a browser is available:

```js
[document.documentElement.scrollWidth <= innerWidth,
 [...document.querySelectorAll('a,button,input,select,textarea,[role=button]')]
   .filter(e => { const r = e.getBoundingClientRect(); return r.width && (r.width < 24 || r.height < 24); })
   .map(e => e.outerHTML.slice(0, 60))]
```

## Generated defaults to avoid (unless the brief asks)

| Default | Instead |
|---|---|
| Purple-to-blue or indigo gradient hero | Brand color, a photo, or a solid surface with strong type |
| Gradient text | Solid color; weight and size for emphasis |
| Three identical icon-heading-text cards | Vary by content: a list, a table, one large feature plus two small |
| Tracked all-caps eyebrow above every heading | Only when the label carries information |
| Cards inside cards | One container; use spacing and dividers inside |
| Emoji as icons | One SVG icon set at consistent size and stroke |
| Glass and blur everywhere | One surface style; blur only for overlays |
| Fade-up on every section, hover lift on every card | One authored motion moment |
| 01 / 02 / 03 numbering | Only for real sequences |
| "Seamless", "unlock", "elevate", invented stats | Concrete claims the product can back up |

## Critique template

```
First impression: <what the eye hits first, and is that right?>
Works well: <1-3 things to keep>
| Severity | Finding | Evidence | Fix |
| Blocker/High/Medium/Nit | ... | measured / judged / needs a human | ... |
Top 3: Before | After | Why
```

Evidence: **measured** means `design.py` or a screenshot showed it; **judged** is your opinion; **needs a human** covers screen-reader flow, brand fit, and real-user comprehension. Automated checks catch only part of accessibility problems; say so instead of claiming full compliance.
