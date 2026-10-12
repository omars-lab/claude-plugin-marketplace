# Page comments: a login header on a local request is still checked

**Status:** decided in development-manager 1.2.0
**Affects:** `plugins/development-manager/shared/scripts/lib/server.mjs` (`whoIsAsking`)

## What changed

The design checks the `Tailscale-User-Login` header only for requests that came through Tailscale.
The build also checks it on a request with a local Host (`127.0.0.1`, `localhost`, `[::1]`) when the
header is there at all. An unknown or empty login is refused with 403. A known login gets the
author the allow list gives it, which is the repo's author unless `phone.authors` in `config.json`
says otherwise.

A local request without the header works exactly as before.

## Why

Tailscale always sends the phone's own Host, so a local Host with a login header did not come from
Tailscale. Ignoring the header would be harmless today, but treating it as a login in one place and
ignoring it in another is the kind of split that later turns into a bypass. One rule, "a login
header is on the allow list or the request is refused", is easier to reason about and to test.
