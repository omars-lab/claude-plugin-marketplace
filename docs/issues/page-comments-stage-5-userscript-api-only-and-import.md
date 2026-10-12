# Page comments: the userscript runs against an API-only server, and is imported, not served

**Status:** decided in development-manager 1.4.0
**Affects:** `plugins/development-manager/shared/scripts/lib/userscript.mjs`, `lib/server.mjs`
(`createHandler`), `page-comments.mjs serve`, `client/comments.js`,
`skills/enable-page-comments/scripts/enable.mjs` (`--userscript`)

## What the design said

Section 3: a userscript "matched to `http://localhost/*` and `http://127.0.0.1/*`", built with
`script-manager:tampermonkey-create`. Section 9: a per-repo token in `.page-comments/.state/token`,
written into the userscript; cross-origin calls only from the exact origins in `config.json` and
only with that token; `serve --rotate-token` makes a new one and setup writes the userscript again.

## What was built, and where it departs

1. **It matches only the listed origins, not every local page.** Each `@match` is one origin from
   `config.userscript.origins` (for example `http://127.0.0.1:8765/*`), and the script checks
   `location.origin` again at run time, because script managers read ports in `@match`
   differently. A script on every localhost page would put the repo token into pages the server
   refuses anyway (section 9), so matching wider buys nothing and spreads the token.
2. **A new server mode, `serve --api-only`.** With the userscript, the page comes from its own
   server, so the comment server has nothing to proxy or serve. `--api-only` answers only
   `/__page-comments/`; any other path gets 404 saying so, and `health` reports `mode: "api"`.
   `serve` still needs exactly one of `--target`, `--root` or `--api-only`.
3. **The page script takes its server address from the tag.** `client/comments.js` reads
   `data-base` (default `/__page-comments/`), so the same file works same-origin and from the
   userscript, which points it at `http://127.0.0.1:<port>/__page-comments/`.
4. **Two tokens, never mixed.** A request from a listed origin must carry the repo token; a request
   from the server's own origin must carry the per-run token. A listed origin's answer gets
   `Access-Control-Allow-Origin` with that exact origin and `Vary: Origin`; a preflight from any
   other origin gets 403. Changes to the origins or the token are read again when their files
   change, with no restart.
5. **The userscript is a file Omar imports, never served over HTTP.** It is written to
   `.page-comments/.state/page-comments.user.js` (ignored by git, mode 600), and the report gives
   the Tampermonkey steps (Dashboard, Utilities, Import from file). A URL that served it would let
   any page that can reach the server read the token out of it.
6. **`tampermonkey-create`'s conventions were used where they fit,** not its whole scaffold: the
   header layout, `@grant none`, `@noframes`, `@run-at document-idle`, a guard against running
   twice. Its logging and debug-panel scaffold was left out. The script only adds one `<script>`
   tag; the page script already logs to the server with `ev=` lines.
7. **Serve makes the token when it is missing.** If origins are listed but `.state/token` is gone
   (a fresh clone, or someone deleted it), `serve` makes a new one and writes the userscript again,
   and says Omar must re-import it.

## Proof (2026-10-12)

An API-only server on a spare port with one listed origin, checked with curl:

| Request | Result |
|---|---|
| GET and POST from the listed origin with the repo token | 200 / 201, with that origin allowed |
| Listed origin with a wrong token | 403 |
| Unlisted origin with the repo token | 403, no allow-origin header |
| No token | 403 |
| No origin, repo token | 403 |
| Preflight from the listed origin / an unlisted one | 204 / 403 |
| `/` on an API-only server | 404 |

The token never appeared in the server log. After a restart with `--rotate-token`, the old token
got 403, the new one 200, and the userscript held only the new one. `git status --ignored` showed
`.state/` as ignored.

**Not yet done:** a run in a real browser with Tampermonkey installed.
