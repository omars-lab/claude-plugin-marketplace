# Page comments: the server picks up the phone setting without a restart

**Status:** decided in development-manager 1.2.0
**Affects:** `plugins/development-manager/shared/scripts/lib/server.mjs` (`settings`)

## What changed

The comment server used to read `config.json` once, at start. It now reads it again when the
file's modified time or size changes, checked on each request. The check is a `stat`, so it costs
next to nothing.

## Why

`enable.mjs --phone` writes the phone setting while a comment server may already be running, and
`--phone --undo` removes it. Without a re-read, turning the phone on would need a restart that the
person has to remember, and turning it off would leave the phone working until one. With it, the
phone works as soon as enable finishes, and stops as soon as undo does.

A `config.json` that is half-written or broken reads as empty: the phone is refused until the file
is fixed, and Mac comments are signed `me` instead of the repo's author. A bad edit can only close
the server, never open it wider.
