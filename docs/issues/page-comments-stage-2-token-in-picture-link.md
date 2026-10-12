# Page comments: a picture's link carries the token in the address

**Status:** decided in development-manager 1.1.0
**Affects:** `plugins/development-manager/shared/scripts/lib/server.mjs` (`getShot`),
`client/comments.js` (`shotView`)

## What changed

Every other call to the comment server carries the per-run token in a request header. The page
shows a picture with a plain `<img>`, and an `<img>` cannot send a header. So a picture's address
carries the token instead: `/__page-comments/shots/<thread>/<name>?token=…`.

## Why this is safe enough

- The server listens on `127.0.0.1` only, and checks the `Host` header, so no other machine and
  no rebound outside name can ask.
- The token changes at each start of the server and is never written to a log.
- The server serves only a file that one of that thread's own `shot` events names, and only from
  inside the pictures folder. A name with a slash or `..` is refused, and so is any event that
  points outside the folder.
- A GET only reads; no write takes the token from the address.

The other way, fetching each picture with the header and showing it as a blob, adds code to the
page and breaks "open image in new tab". Not worth it for a server that only this Mac can reach.
