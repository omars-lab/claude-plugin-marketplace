# Page comments: behind Tailscale Serve the Host header is the tailnet name with the port

**Status:** decided in development-manager 1.2.0
**Affects:** `plugins/development-manager/shared/scripts/lib/server.mjs` (`phoneSetting`, `whoIsAsking`); design sections 9 and 13

## What the design left open

Section 13 says Tailscale's docs do not say which Host header the comment server sees behind
`tailscale serve`, and to allow only what is seen.

## What was seen

On Tailscale 1.102.4 (2026-10-12), a request from another device on the tailnet reached the
comment server with:

- `Host: <mac>.<tailnet>.ts.net:8766`: the tailnet name, with the HTTPS port;
- `Tailscale-User-Login: <login>`: the signed-in person, even when the request sent a forged copy
  of the header (Tailscale replaced it);
- `X-Forwarded-For` with the tailnet address of the other device, and `X-Forwarded-Proto: https`;
- `Origin` passed through unchanged, as `https://<mac>.<tailnet>.ts.net:8766`.

## What the server accepts

- The Host must be one of the server's own local names (`127.0.0.1`, `localhost`, `[::1]` with
  its port), or exactly `<host>:<port>` from the `phone` setting in `config.json`. The bare name
  without a port is accepted only when the port is 443, because only then does a browser leave it
  out.
- A request with the phone's Host must carry a `Tailscale-User-Login` that is on the allow list,
  or it gets 403 and the log says `ev=reject reason=no_login` or `reason=login_not_allowed`.
- A write from the phone must carry `Origin: https://<host>:<port>`; a write from the Mac must
  carry `http://<local host>`. Each request gets the Origin that matches how it arrived.
- The live-reload socket is held to the same checks.

## What this does not stop

A program already running on the Mac can send a request to `127.0.0.1` with the phone's Host and a
made-up login. That was tried: with the phone's Host and no login it gets 403; with an allowed
login it would pass. This is no new hole. A program on the Mac can already read the page token
from the injected script tag and comment as the Mac user, so the server has always trusted it.
