---
name: validate-pages
description: Check the recreated technique pages and gallery in a real headless browser (Playwright) — console errors, React mounting, missing components, block counts against the spec, images, phone-width overflow, light and dark mode — then compare each page's screenshot with the original to judge how faithful it is
---

# Validate Technique Pages

You check that the pages made by `recreate-technique` (and the gallery from `package-gallery`) **actually render the right content**, not just that the files exist. There are two passes:

1. **Mechanical** (`validate_pages.py`, Playwright): pass/fail checks on every page × light/dark × desktop/phone.
2. **Fidelity** (you, with Vision): compare the rendered screenshot with the original screenshot.

Run it after `recreate-technique` and before `package-gallery` zips anything. `package-gallery` calls it too.

## Paths and setup

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
# Don't search ~/.claude/plugins/cache: a plugin installed from a local marketplace loads from its repo folder.
VP="<base directory of this skill>"
TECH="$HOME/Desktop/📸 Screenshots of Techniques"
```

Playwright runs in its own conda env, the same pattern as `screenshot-ocr`:

```bash
conda env list | grep -q technique-check || {
  conda create -y -n technique-check python=3.12 &&
  conda run -n technique-check pip install playwright &&
  conda run -n technique-check python -m playwright install chromium
}
```

If conda is not available, use `AskUserQuestion` to offer `pip install --user playwright` instead, or to skip the mechanical pass.

If pip can't build `greenlet`, install a wheel instead: `pip install --only-binary :all: playwright`.

**If Chromium won't launch** ("Chromium did not launch", usually missing system libraries such as libatk on a Linux sandbox without sudo), don't keep retrying the install. Fall back to a jsdom smoke test in Node: load each page with `runScripts: "dangerously"` and `resources: "usable"`, then check that `#root` mounted, that there is no `.cu-missing`, and that the number of `.cu-screen` children matches the number of spec blocks. Load each page a second time **without** `runScripts` and run the same checks; that is what Quick Look sees. This covers mounting and content only. It can't take screenshots, check overflow or compare themes, so mark the fidelity review as skipped and say so in the output.

## Tasks

Create with `TaskCreate`: `Mechanical checks`, `Fidelity review`, `Fix and re-check`.

## Step 1: Mechanical checks

```bash
conda run -n technique-check python "$VP/scripts/validate_pages.py" --catalog
conda run -n technique-check python "$VP/scripts/validate_pages.py" --only <slug>   # one page
```

What it checks, for each page in both themes and at 1280px and 375px wide:

| Check | Fails when |
|---|---|
| Loads cleanly | any console error, uncaught exception, or failed request |
| React mounted | `#root` is empty (a broken `_lib/` path or a JS error) |
| Components | any block rendered the "No component for block type" placeholder |
| Content | rendered block count ≠ spec block count; header ≠ spec title |
| Images | any `<img>` has not loaded (including the original-screenshot comparison) |
| Mobile | the page scrolls sideways at 375px |
| Gallery | cards ≠ rendered pages, or a card links to a missing page |
| Redaction | a post page shows any replaced identifier (whole-token match) |
| No JavaScript | with scripts off, `#root` is empty or has the wrong block count: the page would be blank in macOS Quick Look and Finder previews |

Both views are checked: `pages/internal/` and `pages/post/`. Pass `--view post` to check one.

It saves screenshots to `$TECH/pages/<view>/_check/<slug>.<theme>.<width>.png`. `zip_gallery.py` leaves `_check/` out of the zip.

## Step 2: Fidelity review

For each page, Read the original screenshot (`pages/internal/img/<slug>.png`) and `pages/internal/_check/<slug>.dark.desktop.png` side by side. Then read the post page's text once more for names the scanner can't recognize. Score fidelity from 0 to 5 and list the differences:

- **Content:** every prompt, reply line, tool call, task and recap that teaches the technique is there, in the same order.
- **Glyphs and states:** `›` `●` `⎿` `✻` `※` are correct, and so are task states and the mode footer.
- **Teaching:** the header's `why` / `when` / `how` match what the screenshot actually shows.
- **Look:** colors are not checked. The aim is a recognizable Claude Code feel, not a pixel copy.

Then check `light.phone` for readability only.

## Step 3: Fix and re-check

Route each problem to its fix:

| Problem | Fix |
|---|---|
| Missing component / a look no component covers | Add a component in `claude-ui.js` (see `recreate-technique`, "The component rule") |
| Wrong or missing content | Edit `pages/specs/<slug>.json`, then `render_page.py --spec …` |
| Overflow at phone width | Fix the component's CSS in `claude-ui.css` (it fixes every page) |
| Broken image or `_lib` path | Re-run `render_page.py --all` (it re-syncs `_lib/` and `img/`) |

Re-run Step 1 until it passes. Use `AskUserQuestion` before changing a component, because the change reaches every page.

## Output

```
Mechanical: 24 checks, 0 failed (6 pages + gallery + catalog × light/dark × desktop/phone)
Fidelity:
  5  hook-runs-linter-after-edit
  3  one-line-principle: task list order differs; recap missing
Fixes applied: <list>   Next: /technique-manager:package-gallery
```
