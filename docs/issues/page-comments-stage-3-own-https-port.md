# Page comments: the phone uses its own HTTPS port, not 443

**Status:** decided in development-manager 1.2.0
**Affects:** `plugins/development-manager/skills/enable-page-comments/scripts/enable.mjs` (`enablePhone`, `undoPhone`, `servedAt`); design section 13

## What changed

The design says `tailscale serve --bg 8766`, which serves the comment server on the Mac's tailnet
name at the default HTTPS port, 443. The build serves it on its own HTTPS port instead, the same
number as the comment server's port:

```text
tailscale serve --bg --https=8766 http://127.0.0.1:8766
```

The phone opens `https://<mac>.<tailnet>.ts.net:8766/`. Turning it off is:

```text
tailscale serve --https=8766 off
```

## Why

Port 443 on a Mac's tailnet name is one shared slot. On the Mac this was built on, 443 already
pointed at another local app. `tailscale serve --bg 8766` would have replaced that entry, and undo
would then have had to remove it, taking Omar's other app off his phone. With its own port, the
comment server's entry sits beside whatever else is served, and turning it off touches only that
port.

One port per repo also means two repos with page comments can both be on the phone, as long as
their comment servers use different ports.

## What enable does to stay safe

- It reads `tailscale serve status --json` first. If the port already serves something else, or
  Funnel is on for it, enable stops and changes nothing.
- If the port already points at the comment server, enable records that it did not add the entry,
  and undo leaves it on.
- After adding the entry it reads the status again and checks the entry points at
  `http://127.0.0.1:<port>`.
- Undo turns the entry off only if enable added it and it still points at the comment server. It
  never runs `tailscale serve reset`, which clears every entry.
- No command it runs can contain "funnel"; the helper refuses such an argument, and enable refuses
  any `--…funnel…` flag.

## Checked when building

On Tailscale 1.102.4 (2026-10-12), against the real Mac:
- `tailscale status --json` gives the name as `Self.DNSName` with a trailing dot, the login under
  `User[<Self.UserID>].LoginName`, and the names that can get certificates in `CertDomains`.
  Enable stops with a plain message when HTTPS certificates are off.
- `tailscale serve --https=<port> off` removes just that port's entry. The existing 443 entry was
  the same before and after enable, and after `--phone --undo`.
- Vite's live-reload socket connects through the tailnet address (`wss://…:8766/`), and an edit
  reloads the page on the phone side.
