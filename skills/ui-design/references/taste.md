# Taste: designing for this project, not for every project

Good taste here means the design could only belong to this product. A design that would fit any product is the generic default, however polished it is.

## 1. Read the project before choosing anything

Answer these from the brief, README, existing UI, and brand before opening `design.py direction`:

1. **World:** what does the product deal with? Name 3 concrete things: materials, objects, places, or words from that world (a coffee roaster: beans, roast curves, burlap, origin labels).
2. **People:** who uses it, how often, and in what situation (a nurse between patients, a trader with four monitors, a parent on a phone at night)?
3. **Promise:** what should they feel after using it (calm, in control, delighted, reassured, impressed)?
4. **Existing identity:** logo, brand color, fonts, photos, tone of voice. These win over any direction.

## 2. Pick the direction by fit, then make it this project's own

- Run `design.py direction "<world, people, promise>" --dir .` and read the top 3 fits. Pick the one that matches the people and the promise, not just the industry word. A fintech product for teenagers is closer to playful-consumer than to fintech-trust.
- Blend at most two: take the structure and density of one, and the voice (type, color, imagery) of the other. Say which part comes from where.
- **Subject twist:** take one detail from the project's world into the signature element. For example, a roast-curve line as section dividers for the coffee roaster, a tide-table layout for the surf school, or ledger rules in the invoicing app. One twist, done well.
- The generated design code (for example `fintech-trust:d1003674`) is stable for the project. Save it with `memory.py add decision` so every later screen stays consistent. Never reuse another project's code or palette.

## 3. What good taste looks like in the result

- **One focal point per view.** Squint: the most important thing is the first thing you see.
- **Contrast of scale.** Headings clearly larger than body (at least the type ratio), and one element allowed to be much larger.
- **Restraint with color.** Neutrals carry most of the page, the accent marks action and meaning, and status colors are used only for status.
- **Alignment and rhythm.** Everything sits on one grid; spacing comes from the scale; related things are closer than unrelated ones.
- **Type details.** Real quotes and dashes, tabular figures for numbers, sensible line length, no orphaned single words in headings (`text-wrap: balance`).
- **Specific content.** Real-looking data and copy in mockups, not lorem ipsum or "John Doe". Images that show this product's world.
- **Finished edges.** Hover, focus, empty, loading, and error states; favicon and page titles; a 404 page that helps.
- **Consistency over novelty.** A second screen should look like it belongs with the first; new patterns need a reason.

## 4. Checks against the generic default

Before finishing, answer honestly:

- Swap the logo for a competitor's: would anyone notice the page is not theirs? If not, strengthen the twist or the voice.
- Does any section exist only because landing pages usually have it?
- Is there anything a user would remember tomorrow? Is it the right thing?
- Does the visual weight match what matters most to the people using it?

## 5. Studying references well

Each direction lists products to study. Learn the decisions, not the surface: how they set hierarchy, density, type, and empty states. Do not copy their logos, illustrations, layouts pixel for pixel, or copy text. Describe what you took ("Stripe-like tabular amounts and calm status badges"), never "make it look like Stripe".
