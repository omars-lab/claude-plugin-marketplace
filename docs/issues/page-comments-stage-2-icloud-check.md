# Page comments: "is iCloud Drive on?" checks only the folder

**Status:** decided in development-manager 1.1.0
**Affects:** `plugins/development-manager/shared/scripts/lib/shots.mjs` (`shotTarget`); design section 14

## What changed

The design says pictures fall back to `.page-comments/shots/` when the iCloud Drive folder does not
exist, or when `brctl accounts` shows no signed-in account. The build checks only the folder.

## Why

On this Mac, with iCloud Drive signed in and in use, `brctl accounts` printed nothing and
exited 0 (checked 2026-10-12). Its output cannot tell "signed in" from "signed out", so a check
built on it would have sent every picture to the local fallback.

The folder check is what matters for saving: if `~/Library/Mobile Documents/com~apple~CloudDocs`
exists, a file written there is saved, and iCloud uploads it when it can. What macOS does to that
folder when someone signs out of iCloud was not checked; if the folder stays, pictures keep being
saved there and simply stop syncing.

Also noted: `brctl` has no command to download a file that is only a `.<name>.icloud` placeholder.
When the watcher prints `ev=shot_missing`, Claude takes a new picture of the live page, as the
design says, rather than trying to fetch the old one.
