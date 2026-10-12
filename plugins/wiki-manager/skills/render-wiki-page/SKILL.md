---
name: render-wiki-page
description: Open a wiki page in the NotePlan app and screenshot what a reader actually sees, so a review judges the render rather than the markdown source. Use before reviewing, verdicting or fixing any wiki article, when a page "looks fine in the source" but may render wrong, when checking whether bold/italic/links/frontmatter render correctly, after a frontmatter migration, or when a screenshot of a note is needed for any reason. Triggers "render the page", "screenshot the note", "what does this look like in NotePlan", "open this in NotePlan", "show me the render", "capture the page", "does this render correctly".
---

# Render a wiki page — look at the app, not the markdown

Reviewing a page from its markdown is guessing. **NotePlan is an editor, not a preview**, and the
gap between source and render is where the real findings live. Run this skill first; review the
image, not the file.

## What the source cannot tell you

| In the app | Why the source hides it |
|---|---|
| `**` and backtick markers print in grey *and* the formatting is applied | Both at once. Dimmed asterisks around a bold span are **normal** — not a finding. |
| Inline markup spanning a wrapped line renders as literal text | Depends on the window width, not the file. |
| HTML comments are visible to the reader | They are "hidden" only by convention. |
| There is no callout syntax | `> [!note]` renders as a literal italic line. |
| A `>` blockquote gets a grey ground, italics and a left rule | Which is why quoting your own prose misattributes it. |
| Remote images never load | The concept map must be a local attachment. |
| A PROPERTIES panel renders the frontmatter as editable rows | It occupies a whole screen above the H1. |

## The one command

```
python3 bin/wiki_render.py --page "<path to .md>" --section Evidence --screens 2 --out <dir>
```

Then **Read the PNGs it prints**. That is the point of the skill; the capture is not the work.

| Flag | Use |
|---|---|
| `--section <heading>` | Scroll straight to `## Evidence` / `## Context` / `## Gaps`. Omit for the H1. |
| `--screens N` | Capture N screens, paging down between. 2 covers a typical article. |
| `--region x,y,w,h` | Re-crop if the window moved. Default is the editor column. |
| `--no-collapse` | Skip the sidebar collapse when it is already collapsed. |
| `--selftest` | Offset maths and URL encoding. No display needed. |

## Why it is built the way it is

Each step exists because something failed without it:

- **Activate NotePlan first.** Otherwise another app's window floats over the capture. A GeoGebra
  window landed in the middle of a probe shot.
- **Collapse the left sidebar** (`toggleSidebar?forceCollapse=yes`). Dead pixels otherwise.
- **Pass a computed `highlightStart`.** This is the step that is easy to get wrong.
  `highlightStart=0` does **not** land on the body — offset 0 is the top of the *file*, so the
  shot is a screenful of PROPERTIES panel with the H1 just creeping in at the bottom edge. The
  offset is counted from the file start, frontmatter included, so the tool computes the real
  character offset of the heading. (An earlier research pass claimed `highlightStart=0` would land
  at the top of the body. It was tested against the app and it does not.)
- **Crop with `screencapture -R`.** NotePlan keeps a right-hand calendar/Timeline panel open that
  no x-callback closes. Cropping is the only way to exclude it, and it roughly halves the pixels
  per shot — which matters at ~200 shots across the wiki.
- **Page down via System Events**, not NotePlan. System Events is a *separately authorized*
  Apple-events target, which is why `key code 121` works while direct NotePlan automation fails.

## The -1743 wall

Direct Apple-events automation of NotePlan (`osascript … tell application "NotePlan"`, and the
whole `noteplan_ui` MCP tool) fails with **-1743** = `errAEEventNotPermitted`. That is a TCC
Automation denial recorded against the *terminal* process — not a NotePlan limitation, and not
something a script can grant itself. It needs one human click:

**System Settings → Privacy & Security → Automation → <terminal app> → NotePlan.**

Until then, use this skill's path (x-callback URLs + System Events), which needs no such grant.
Granting it would additionally unlock `showNote … in background`, `setTheme`, and `noteplan_ui`.

NotePlan's own MCP server ships dormant `screenshotWindow` / `scrollWindow` implementations
written against a **newer** build than the installed 3.21.2/1533, so a NotePlan update would give
native in-app capture and make most of this obsolete.

## Do not

- **Do not trigger a modal dialog.** A NotePlan alert blocks every subsequent x-callback and the
  run wedges with no error.
- **Do not reason from the markdown once you have the image.** If they disagree, the image wins —
  that is the entire premise.
- **Do not report dimmed `**` markers as a defect.** That is how the editor draws applied bold.
