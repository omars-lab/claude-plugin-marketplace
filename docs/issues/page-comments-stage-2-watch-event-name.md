# Page comments: the watcher says `ev=shot`, not `ev=shot_ready`

**Status:** decided in development-manager 1.1.0
**Affects:** `plugins/development-manager/shared/scripts/lib/watch.mjs`; design sections 7 and 12

## What changed

The design lists `shot_ready` and `shot_missing` as the two picture lines the watcher prints. The
build prints `ev=shot` and `ev=shot_missing`.

## Why

The line is named after the event in the thread file, which is `shot`, as with the other lines:
a `shot` event that points at a file on this Mac prints `ev=shot` with the file's `path`. One name
for one thing means Claude and any reader of the thread file match on the same word.

`ev=shot` also covers two cases the design did not name:

- a capture that failed on the page prints `ev=shot` with `msg="the capture failed: <reason>"`;
- a picture that was missing and then arrives from iCloud prints `ev=shot` again.

The design's text still says `shot_ready`; read it as `shot`.
