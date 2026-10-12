# Capturing what a wiki page actually looks like

**Date:** 2026-09-16 · **Shipped in:** wiki-manager 0.11.0

## Why a capture pipeline at all

The newcomer review judges readability, and NotePlan is an **editor, not a preview**. It prints
`**` and backtick markers in grey *while also* applying the formatting, shows HTML comments,
renders `>` with a grey ground and italics, has no callout syntax, never loads a remote image, and
turns inline markup that spans a wrapped line into literal text. None of that is visible in the
markdown. Reviewing from source is guessing, so the review looks at the render.

At ~73 pages and 2–3 screens each that is roughly 200 captures. Ad-hoc shell commands were the
wrong shape; the variation (page, section, screen count) belongs in a tool as parameters.

## What was tried

Direct Apple-events automation first: `osascript … tell application "NotePlan"`, and the
`noteplan_ui` MCP tool. Both fail with **-1743** (`errAEEventNotPermitted`).

That is not a NotePlan limitation. It is a TCC Automation denial recorded against the *terminal*
process, and it cannot be granted non-interactively — it needs one human click in
**System Settings → Privacy & Security → Automation**. So the pipeline had to be built out of
things that need no such grant.

`System Events` turns out to be a **separately authorized** Apple-events target, which is why
`key code 121` (page down) succeeds where talking to NotePlan directly does not. That asymmetry is
what makes scrolling possible at all.

## The research prediction that did not hold

A research pass reported that `openNote?…&highlightStart=0&highlightLength=1` would land the
editor at the top of the note **body**, eliminating a wasted first screenshot, and estimated the
saving at roughly 180 → 100 captures.

Tested against the app, it does not. `highlightStart` counts from the start of the **file**,
frontmatter included, so offset 0 is the top of the frontmatter: the capture was a full screen of
References panel plus a ten-row PROPERTIES panel, with the H1 only just reaching the bottom edge.

The fix was to keep the mechanism and drop the magic number. The tool computes the **real
character offset of the target heading** and passes that. With `--section Evidence` on the
Guardrails page (offset 670) the capture opens on the H1, the short answer, `## Evidence` and the
first bullets — one screen, no panels. The mechanism was right; the constant was wrong.

This is the standing rule earning its keep: the claim was plausible, well-argued and wrong, and
one screenshot settled it.

## What shipped

`bin/wiki_render.py` (`--page`, `--section`, `--screens`, `--region`, `--no-collapse`,
`--selftest`) plus the **render-wiki-page** skill. Five steps, each present because something
failed without it:

| Step | Failure it prevents |
|---|---|
| `open -a NotePlan` | Another app's window floats over the shot — a GeoGebra window landed in the middle of one probe. |
| `toggleSidebar?forceCollapse=yes` | The left sidebar is dead pixels. |
| `openNote` with a computed `highlightStart` | Otherwise the shot is the PROPERTIES panel (above). |
| `screencapture -R <region>` | The right-hand calendar/Timeline panel stays open — no x-callback closes it — and cropping also roughly halves the pixels per shot. |
| `key code 121` via System Events | Direct NotePlan automation is blocked by -1743. |

Every subprocess has a timeout and logs `ev=` lines before and after, so a stalled sweep is
bracketed rather than silently frozen.

The selftest covers offset maths and URL encoding (every page title is a question, so `?` and `/`
must encode or they split the query string). It deliberately does **not** mock the capture: a test
that mocked NotePlan, the display and `screencapture` would only prove the mock works.

One bug found by the selftest and worth recording: `^#{1,6}\s+Evidence\s*$` under `re.MULTILINE`
matches `"## Evidence\n"` — `\s*` eats the newline and `$` then matches on the following blank
line, so the highlight spilled past the heading. `[ \t]*$` is the correct expression of the
intent, which was "trailing spaces on this line".

## Still open

- Automation permission is a one-time human click and would unlock `showNote … in background`,
  `setTheme` and the whole `noteplan_ui` tool. Worth doing, but not something a script can do.
- NotePlan's own MCP server ships **dormant** `screenshotWindow` / `scrollWindow` implementations
  written against a newer build than the installed 3.21.2/1533. A NotePlan update would give
  native in-app capture and make most of this obsolete.
- `--region` is calibrated to one window geometry. It is a flag rather than a constant for that
  reason, but nothing detects a moved window; a wrong region shows up as an obviously wrong image.
