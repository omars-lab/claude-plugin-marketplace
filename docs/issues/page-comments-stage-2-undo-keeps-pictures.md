# Page comments: undo never deletes a picture, even with --purge

**Status:** decided in development-manager 1.1.0
**Affects:** `plugins/development-manager/skills/enable-page-comments/scripts/enable.mjs` (undo);
design section 8

## What changed

The design says undo leaves the pictures in iCloud alone, and that `--purge` deletes the whole
`.page-comments/` folder. When iCloud Drive is off, pictures live in `.page-comments/shots/`, so
`--purge` would have deleted them.

The build keeps them. With `--purge`, undo deletes everything in `.page-comments/` except `shots/`
and the `.gitignore` that keeps it out of git. Pictures in iCloud Drive are never touched, and undo
prints their folder.

## Why

The rule for this stage is that undo never deletes a picture. One rule for both places is easier to
trust than "kept in iCloud, deleted locally". The pictures are Omar's record of what he saw, and
they are not in git, so a deleted picture cannot be brought back. The `.gitignore` stays with them
so they can never be committed by accident after undo.

To delete them, remove the folder by hand.
