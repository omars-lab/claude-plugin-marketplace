# Page comments: when the page reports a comment as not found

**Status:** decided in development-manager 1.3.0
**Affects:** `plugins/development-manager/shared/scripts/client/comments.js` (`reportAnchors`),
`lib/server.mjs` (`POST threads/<id>/anchor`), `lib/store.mjs` (the `anchor` event),
`lib/watch.mjs` (`ev=anchor_lost`)

## What the design said

Section 4: if no anchor matches, the thread goes in a "not found on this page" list. Section 11
lists `anchor_lost` as a watcher event. It does not say when or how often the page reports.

## What was built

The page appends `{"ev":"anchor","state":"lost"|"found"}` to a thread file only when all hold:

- the page's `load` event has fired, so a page still building itself is not judged;
- the same answer has held for at least 2 seconds across two polls (polls are 4 seconds apart),
  so a single-page app that draws in steps, or a slow fetch, does not flip it;
- the thread is open;
- the answer differs from what the thread file already says;
- this page load has not already reported that thread.

The server checks again and writes nothing when the state is unchanged, so several tabs, phones or
reloads add one line, not one per view. The headless proof added exactly one `lost` line over four
reloads, and one `found` line when the element was put back.

The watcher prints `ev=anchor_lost` when a thread turns lost (and, with `--replay`, for open
threads already lost). It names who reported it: the author of the page that saw it.

## Why

A report per page view would fill thread files with noise and wake Claude for nothing. "Found"
reports are kept because a thread that comes back (a feature flag, a step in a flow) should leave
the not-found list by itself.

## Limits

Each viewer's page judges for itself: two people on different versions of a page (a branch, a
phone on another build) can flip a thread between lost and found. Each flip is one line and one
watcher event at most per page load.
