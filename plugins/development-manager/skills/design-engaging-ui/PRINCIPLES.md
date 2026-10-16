# What makes a page appealing and engaging

`design-engaging-ui` reads this file at run time, so a principle can be added or sharpened without
touching the skill. Each principle is something you can see on the page or check in the browser,
not a matter of taste.

- **Appealing** means it looks like it was made on purpose, for this job: one clear thing to look
  at first, one consistent look, and nothing that reads as a template.
- **Engaging** means the page is worth opening again, and pleasant while it is open: it answers
  every click, shows what changed, and makes progress visible. It never means keeping people on
  the page with tricks (see "Not engagement" at the end).

Score each principle `pass`, `fail` or `not checked`, at 1280 and at 390 px wide. A principle
passes only when it holds at both widths.

## Hierarchy: what to look at first

| Id | Principle | How to see it | Common fix |
|---|---|---|---|
| H1 | One thing is clearly the most important on each view | Squint at the screenshot, or blur it: one block still stands out | Make the main number, list or action larger and bolder; make the rest quieter |
| H2 | The first action is obvious and above the fold | Someone new could say what to click first within five seconds | One filled button for the main action; the rest as plain or outlined buttons |
| H3 | Related things sit together and unrelated things sit apart | Spacing inside a group is clearly smaller than between groups | Use the spacing scale: small steps inside a card, large steps between sections |
| H4 | Headings, labels and body text are clearly different sizes | No two levels look alike; no more than 4 or 5 text sizes on the page | Use the type scale; cut sizes that are close to each other |

## Design system: one look, the page's own

| Id | Principle | How to see it | Common fix |
|---|---|---|---|
| D1 | Colours, type, spacing, corners and shadows come from one set of values | Search the styles for colours and pixel sizes written inline; lay the views side by side | Put the values in one file (CSS variables or a theme) and use only those |
| D2 | A small palette: neutrals plus one accent, and colours for success, warning and error | Count the distinct colours in use; the accent marks actions and the current place, not decoration | Pick one accent; turn the other colours into neutrals |
| D3 | It is not the default AI look | No purple-to-blue gradients, glowing cards, emoji in headings, or every block a rounded card with a shadow | Go back to the brief's three words and pick a direction that fits them (with `frontend-design`) |
| D4 | Every control is styled to match: inputs, dropdowns, checkboxes, scroll bars, focus rings | Look at the search box and filters next to the buttons | Style the plain browser controls with the same border, radius and spacing |

## States: what the page says when there is nothing, or something went wrong

| Id | Principle | How to see it | Common fix |
|---|---|---|---|
| S1 | An empty view says what is missing and how to fill it | Open a view with no data, or filter to nothing | One line on why it is empty and a button or command to fill it |
| S2 | Loading shows the shape of what is coming | Slow the network in the browser tools and reload | A placeholder in the layout of the content (a skeleton), not a lone spinner in an empty page |
| S3 | An error says what happened and what to do next, in plain words | Stop the API or break a request and reload | Name what failed, keep the rest of the page working, and offer a retry |
| S4 | Long text, many items and odd data don't break the layout | Try a very long name, 500 rows and a missing field | Truncate with the full text on hover, paginate or virtualize, and show a dash for a missing value |

## Feedback: the page answers every action

| Id | Principle | How to see it | Common fix |
|---|---|---|---|
| F1 | Every click, tap or key gets a visible answer within a tenth of a second | Click each control and watch: something changes at once | Hover and pressed styles; mark the item chosen at once, before the server answers |
| F2 | Anything that takes over a second shows it is working, and the result when it is done | Run the slowest action | Disable the button and show progress on it, then a short confirmation where the action was |
| F3 | Something that can't easily be undone asks first, or offers an undo | Delete or archive something | An undo for a few seconds is better than a confirm box; confirm only what is truly final |

## Motion: small, quick, and optional

| Id | Principle | How to see it | Common fix |
|---|---|---|---|
| M1 | Motion explains a change (where something came from or went), and is quick | Watch a panel open or an item move; small changes take about 150 to 250 ms | Animate opacity and position only; cut motion that is only decoration |
| M2 | Motion stops when the person's system asks for less | Turn on "Reduce motion" in the system settings (or emulate it in the browser tools) | Wrap animations in `@media (prefers-reduced-motion: no-preference)` |

## Engagement: worth opening again

| Id | Principle | How to see it | Common fix |
|---|---|---|---|
| E1 | The first screen shows something current, not only navigation | Open the page cold: the newest items, counts or what is waiting are on the first screen | Lead with a short "now" strip: what is new, what needs you, the one number that matters |
| E2 | It shows what changed since the last visit | Open it, change something elsewhere, open it again | Mark new items, or a "since your last visit" line; this needs the last visit stored somewhere |
| E3 | Progress is visible and finishing feels finished | Work through a list: the count goes down, and an emptied list says so warmly | Show counts and progress; give "all done" its own state rather than a blank space |

## Accessibility: everyone can use it

Run an automated scan (Lighthouse through the Chrome dev tools, or axe) first, then read the page
yourself. The scanners pass an image described as "image" and a button labelled "click".

| Id | Principle | How to see it | Common fix |
|---|---|---|---|
| A1 | Text has enough contrast: 4.5 to 1 for body text, 3 to 1 for large text and control edges | The scan's contrast findings; check light and dark mode | Darken the text or the accent until it passes; never put grey text on a coloured fill |
| A2 | Labels, headings and image descriptions mean something | Read them out of context: headings go in order without skipping levels, and each button says what it does | Write each label for someone who can't see the page |
| A3 | The keyboard alone works, and focus is always visible | Tab through the main action; the focus ring is easy to see and moves in reading order | Real buttons and links; a focus style that matches the design rather than none |
| A4 | Tap targets are big enough and the page fits a phone | At 390 px: no sideways scrolling, nothing cut off, targets at least 44 by 44 px (WCAG's minimum is 24) | Stack or wrap at narrow widths; pad small icons out to the target size |

## Not engagement

These raise time on the page and cost the person. Do not add them, and flag them when you find
them:

- fake urgency or scarcity ("only 2 left", countdown timers that reset);
- a streak that scolds or a badge for showing up;
- infinite scroll on a page someone needs to finish;
- notifications or pop-ups that ask before the page has shown anything useful;
- hiding the way out (a close button that is hard to find, an unsubscribe in grey).

## Adding a principle

Add one when a page had a problem this file did not name, and the same problem could come up on
another page. Give it the next free id in its group, and say in "How to see it" what you looked at
that showed the problem. If `improve-hub`'s rubric has a matching look row, point that row here.
