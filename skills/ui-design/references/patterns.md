# Feature patterns

What each common feature needs to be complete and well built. Print one with `design.py pattern <feature>`. Check every line before saying the feature is done; skip a line only when it truly does not apply, and say so.

## form
Also: input, fields, edit, create, wizard, multi-step, contact
- Must have: a visible label above each field, required fields marked (or optional ones, whichever is fewer), the right input type, `autocomplete`, and `inputmode`.
- Layout: one column; related fields grouped under short headings; the primary button at the end, aligned with the fields; a secondary action as a quieter button or link.
- States: pristine, focused, filled, invalid (message under the field, linked with `aria-describedby`, `aria-invalid`), submitting (button keeps its width and shows progress), success, server error (summary at top with links to fields).
- Validate on submit or on blur, never while the user is still typing. Keep entered data after an error.
- Multi-step: show the step count, allow going back without losing data, review before submit.
- Mistakes: placeholder as label, disabled submit with no reason, clearing the form on error, a "Reset" button next to "Submit".

## settings
Also: preferences, account, profile, configuration, options
- Group by what people look for (Profile, Notifications, Security, Billing, Danger zone), with in-page navigation when there are more than 4 groups.
- Decide the save model and make it obvious: toggles save instantly (with a quiet confirmation), text fields save with an explicit button per section.
- Every setting has a label and a one-line consequence ("Email me a summary every Monday").
- Danger zone last, visually separated; destructive actions need a confirmation that names what will be lost.
- Mistakes: one giant save button for unrelated sections, settings that silently fail, switches used for actions.

## auth
Also: login, sign in, sign up, register, password, reset, onboarding login, 2fa, magic link
- Sign in: email and password with `autocomplete="email"` and `current-password`, a show-password toggle, "Forgot password?" next to the password field, and passkeys or SSO if the product supports them.
- Sign up: as few fields as possible, password rules shown before typing, `new-password`, and terms linked rather than pasted.
- Errors: never reveal whether an email exists ("Email or password is incorrect"); rate-limit messages explain when to retry.
- Reset: confirm the email was sent (same message whether or not it exists), the link expires, and success signs the user in.
- Mistakes: blocking paste into password fields, CAPTCHA before the first try, losing the destination page after login.

## table
Also: data table, grid, list view, records, admin list, spreadsheet, rows
- Must have: column headers that sort (with `aria-sort`), right-aligned numbers with tabular figures, left-aligned text, a sticky header for long tables, and a count ("1-50 of 1,204").
- Interaction: filters above the table, with active ones shown as removable chips; row actions in a menu at the end of the row; bulk select with a bulk-action bar; pagination or "load more" (avoid infinite scroll for work data).
- States: loading (skeleton rows), empty (explain and offer the first action), no results for the filters (offer to clear them), error with retry, a long cell (truncate with the full value on hover or focus).
- Phones: turn rows into stacked cards, or keep 2-3 key columns with horizontal scroll inside the table only.
- Engineering: real `<table>` markup, virtualize beyond about 500 rows, and keep the sort and filter state in the URL.

## dashboard
Also: overview, home, analytics, metrics, kpi, reports, admin home
- Lead with the 3-5 numbers that drive decisions; each shows the value, a comparison (vs last period), and a period selector that applies to the whole page.
- Then trends (line charts over time), then breakdowns (bar charts), then detail tables. Each chart answers one question in its title.
- Charts: a consistent, color-blind-safe palette; labels on the lines instead of legends where possible; no 3D; no pie charts with more than 4 slices.
- States: loading skeletons shaped like the final cards, no data yet (onboarding), partial data, stale data (show "updated 5 min ago").
- Mistakes: 12 equal cards with no hierarchy, vanity metrics, colors that mean different things on different charts.

## list
Also: feed, inbox, timeline, activity, notifications list, cards list, catalog
- Each item shows its most important fact first, a secondary line, and its time; unread or new items are marked by more than color alone.
- Actions: the main action on click, secondary actions on hover and focus (and always visible on touch).
- States: loading, empty (with a next step), end of list, error, new items arriving (a "3 new" pill instead of jumping the scroll).
- Mistakes: identical cards with no scannable anchor, timestamps without a timezone hint, layout shift when images load.

## detail
Also: detail page, record, item page, profile page, product page, view page
- Title and key status at the top with the main actions; then the facts people check most; then secondary sections.
- Show who changed what and when, if the data is shared.
- Edit in place for single fields, or a dedicated edit mode for many; never both mixed on one page.
- States: loading, not found (with a way back), no permission (say who can grant it), deleted.
- Mistakes: a page of equal-weight label:value pairs, hiding the primary action in a menu.

## search
Also: search bar, find, autocomplete, command palette, results
- The input is always findable (top of the page, or a `/` or Cmd+K shortcut), with a clear button and the query kept in the URL.
- Suggestions while typing (debounced about 150ms), with keyboard support: arrows move, Enter opens, Esc closes.
- Results: the matched text highlighted, the result type and location shown, counts per category.
- No results: show the query, suggest spelling fixes or broader filters, and offer popular items.
- Engineering: cancel stale requests, `role="combobox"` with `aria-activedescendant`, and announce result counts politely.

## filters
Also: facets, sort, refine, faceted search
- Show filters beside results on wide screens and in a sheet on phones, with the result count on the "Show results" button.
- Active filters appear as removable chips with a "Clear all".
- Counts next to options; disable or hide options with zero results.
- Keep filter state in the URL so it can be shared and survives a reload.

## checkout
Also: cart, payment, purchase, order, buy, billing
- Cart: item, options, quantity stepper, line price, remove, subtotal; shipping and taxes estimated before checkout.
- Checkout: guest checkout allowed; steps shown (contact, shipping, payment, review); the order summary always visible (collapsible on phones).
- Payment: the provider's secure fields, accepted methods shown, the total repeated on the pay button ("Pay $48.20").
- Errors: card declines explained in plain words with what to try; never clear entered addresses.
- After: confirmation with order number, what happens next, and an email receipt.
- Mistakes: surprise fees at the last step, forced account creation, fake urgency timers.

## pricing
Also: plans, tiers, subscription, upgrade, paywall
- 2-4 plans side by side, the recommended one marked; a monthly/yearly switch that shows the saving honestly.
- Each plan states who it is for in one line, the price with its unit, the main limits, and one clear button.
- A full comparison table below for people who need it; answers to billing questions (cancel, refunds, taxes).
- Mistakes: hiding the price behind "Contact us" for every plan, unexplained limits, dark patterns on cancel.

## landing
Also: homepage, marketing page, hero, launch page, website home
- Above the fold: what it is, who it is for, and one primary action, plus real product proof (a screenshot, demo, or photo).
- Then: how it works (3 concrete steps, or a real example), proof (named customers, numbers that can be checked), objections answered, and the action again.
- Write the copy before the layout; every section earns its place.
- Mistakes: the generic gradient hero, three identical feature cards, invented testimonials, five competing buttons.

## onboarding
Also: first run, welcome, getting started, setup, tour, empty first use
- Get people to the first real result fast: ask only what changes the first experience, and let them skip the rest.
- Prefer a filled example or template over an empty screen; checklists of 3-5 steps with progress.
- Teach in context (an inline hint where the action is) instead of a modal tour.
- Mistakes: 6-slide carousels, asking for permissions before showing value, no way to resume later.

## empty state
Also: empty, zero state, no data, first use, blank state
- Say what will appear here, why it is empty, and offer the action that fills it (or a sample to explore).
- Different copy for "nothing yet", "no results for these filters" (offer to clear), and "something went wrong" (offer retry).
- Mistakes: a sad illustration with no action, reusing one generic message everywhere.

## notifications
Also: toast, alert, banner, snackbar, message, feedback, inline alert
- Toast for the result of an action (auto-dismiss after about 5s, pause on hover, an undo when possible); a banner for page-wide states; inline messages next to the thing they are about.
- `role="status"` for confirmations and `role="alert"` only for urgent errors; never move focus to a toast.
- Errors say what happened and what to do; success messages are short.
- Mistakes: stacking many toasts, errors that disappear before they are read, color as the only signal.

## modal
Also: dialog, popup, overlay, confirm, drawer, sheet, lightbox
- Use one only when the task must interrupt the page; prefer inline expansion or a new page for long tasks.
- Native `<dialog>` with `showModal()`: focus moves in, Tab stays inside, Esc and a visible close button close it, and focus returns to the trigger.
- The title names the task; buttons say the outcome ("Delete project", "Keep editing"); the destructive button is not the default focus.
- Phones: full-screen sheet or bottom sheet; the content scrolls inside, not the page behind.
- Mistakes: modals on top of modals, closing on outside click when there is unsaved input.

## navigation
Also: nav, navbar, header, sidebar, menu, tabs, breadcrumbs, mobile menu, tab bar
- Up to about 7 top-level items; the current location is always shown (`aria-current="page"`).
- App: a sidebar for many sections, a top bar for a few; collapse to a bottom tab bar (3-5 items) or a menu on phones.
- Site: logo home link, primary links, one primary action; skip link to main content first in the tab order.
- Menus open on click, not hover only; Esc closes them and returns focus.
- Mistakes: hamburger menus on desktop, icon-only navigation without labels, a different nav on every page.

## upload
Also: file upload, dropzone, attachment, image upload, import
- A button plus drag and drop (never drag only); accepted types and size limits stated up front.
- Each file shows name, size, progress, cancel, and then success or a specific error with retry.
- Images get a preview; imports get a validation summary before anything is applied.
- Engineering: validate type and size on the client and again on the server; keep the page usable during uploads.

## chat
Also: chat, messaging, conversation, ai chat, assistant, comments, thread
- The composer is always reachable: multi-line, Enter sends, Shift+Enter adds a line, and it keeps the draft.
- Messages: clear authorship, timestamps on demand, readable width (about 70ch), and code blocks with copy buttons.
- Streaming or typing state; a stop button while generating; retry and edit on failure.
- Engineering: `aria-live="polite"` for new messages (not each streamed token), scroll stays where the user put it, and jump-to-latest appears when they scroll up.
- Mistakes: bubbles for long AI answers that are hard to read, losing the draft on error.

## calendar
Also: schedule, booking, appointment, date picker, availability, events
- Show availability before asking for details; the time zone is visible and changeable.
- Date pickers allow typing the date as well as picking it; disabled dates explain why.
- Booking confirms date, time, time zone, and what happens next, with an add-to-calendar link.
- Mistakes: picker-only date entry, ambiguous formats (03/04), no way to reschedule.
