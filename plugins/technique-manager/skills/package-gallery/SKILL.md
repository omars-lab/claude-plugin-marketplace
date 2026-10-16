---
name: package-gallery
description: Combine the recreated technique pages into a gallery for each view (internal for checking, post for sharing), built from the same React component library, and zip the post view — redacted pages, components, vendored React — so it opens offline and is safe to share or publish
---

# Package the Technique Gallery

You turn the pages made by `recreate-technique` into something shareable: a gallery page with a card for each technique, and a zip that works offline when unzipped anywhere.

## Paths

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
# Don't search ~/.claude/plugins/cache: a plugin installed from a local marketplace loads from its repo folder.
PG="<base directory of this skill>"
RT="$(dirname "$PG")/recreate-technique"
TECH="$HOME/Desktop/📸 Screenshots of Techniques"
```

## Tasks

Create with `TaskCreate`: `Re-render pages`, `Build gallery`, `Validate pages`, `Zip gallery`.

## Step 1: Re-render every page

Components may have changed since a page was made, so render them all again first. It costs nothing, because each page is just its spec plus the shared library:

```bash
python3 "$RT/scripts/render_page.py" --all
```

If it reports errors, stop and fix them (see `recreate-technique`). Do not zip a partial gallery without saying so.

## Step 2: Build the gallery

```bash
python3 "$PG/scripts/build_gallery.py" --title "Claude techniques"
```

It writes `$TECH/pages/post/index.html` (titles and summaries redacted, no thumbnails) and `$TECH/pages/internal/index.html` (with screenshot thumbnails), each with `<Gallery>` and `<TechniqueCard>` from `claude-ui.js`: cards sorted newest first, filters by mechanism, a link to each page. Report any `skipped` specs (a spec with no rendered page).

## Step 2b: Validate in a browser

Run the mechanical pass from `/technique-manager:validate-pages` (Playwright) on everything, gallery included:

```bash
VP="$(dirname "$PG")/validate-pages"
conda run -n technique-check python "$VP/scripts/validate_pages.py" --no-shots
```

If anything fails, stop and fix it the way `validate-pages` describes. A zip should never contain a page that does not render.

## Step 3: Privacy check before sharing

```bash
python3 "$RT/scripts/scan_privacy.py" --all --post
```

It must come back empty, because `render_page.py` won't write a post page that still has findings. If some specs have no post page, use `AskUserQuestion`: **add redactions and re-render first (Recommended)**, as `recreate-technique` Step 3 describes, or zip without those techniques. Never zip the internal view.

## Step 4: Zip

```bash
python3 "$PG/scripts/zip_gallery.py"              # pages/post/ → $TECH/techniques-YYYYMMDD.zip
```

The script zips **only `pages/post/`**: no specs, no internal view, no original screenshots. It refuses if any local `src`/`href` does not resolve inside `pages/post/`. The zip has one top folder, `techniques/`, which holds `index.html`, the pages and `_lib/` (components, CSS, vendored React and htm).

## Step 5: Verify

```bash
V=$(mktemp -d) && unzip -q "$TECH"/techniques-*.zip -d "$V" && open "$V/techniques/index.html"
```

Click through to one page and back. Report the zip path, file count and size.

## Then: sync to the studio

If `~/.config/technique-manager/studio.json` exists, offer `/technique-manager:sync-studio` to add the new techniques to the studio folder (through iCloud Drive on a Mac that has it, else over SSH), alongside the ones already there.

## Optional: publish

Only if the user asks: offer to publish `post/index.html` as a private Artifact, with the post pages and `_lib/` as supporting `files` so the relative links keep working. Never publish the internal view.

## Output

```
Gallery: 📸 Screenshots of Techniques/pages/post/index.html (N techniques, M mechanisms)
Internal: 📸 Screenshots of Techniques/pages/internal/index.html
Zip:     📸 Screenshots of Techniques/techniques-YYYYMMDD.zip (F files, S MB)
```
