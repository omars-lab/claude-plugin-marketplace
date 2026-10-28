# Page comments: every screen of a hash app was filed under "/"

**Status:** resolved in development-manager 1.8.0
**Affects:** `plugins/development-manager/shared/scripts/client/comments.js`,
`plugins/development-manager/shared/scripts/lib/store.mjs`,
`plugins/development-manager/shared/scripts/lib/server.mjs`

## What happened

The page recorded a comment's page as `location.pathname`, which leaves out everything after `#`.
Apps that switch screens by the hash, such as the Naqsh hub (`/#/topic/cup-mark/round/21`), have
one path, `/`, for every screen. So every comment on every screen was filed under `/`.

On any one screen, the page asked for the comments on `/`, got all of them, and could not find the
elements the other screens' comments pointed at. They piled up under "Not found on this page", and
the watcher printed `ev=anchor_lost` for them again and again as Omar moved between screens.

A second, smaller problem showed up in the same lines: the found and not-found lines were signed
with the name of whoever's tab sent them. From Omar's tab that was `omar`, even on a thread an
agent wrote and Omar never touched.

## What we did instead

**The page key keeps the screen route.** A comment's page is the path plus the hash, but only when
the hash starts with `#/` or `#!/` and has something after the slash. `#/` alone is the app's first
screen, the same as no hash. Any other hash (`#section-2`) is a jump to a place on one page and is
dropped, so an ordinary page with links to its own sections is not split into many pages. The rule
is one regular expression, `/^#!?\/./`, written twice: in `store.mjs` (`routeOf`) and in
`comments.js`. A test runs both copies on the same cases so they cannot drift apart.

We picked a fixed rule over a per-repo setting. Every hash router we know of uses `#/` or `#!/`, and
no page uses `#/` as an ordinary jump target. A setting can be added later; it would need a data
attribute on the script tag so the page can read it.

**The page re-checks on a screen change, with no reload.** On `hashchange` or `popstate` the page
forgets its threads and asks for the new screen's. It also clears the store version it last saw.
That version is a fingerprint of the whole store, not of one page, so without clearing it the
server would answer "nothing changed" and the new screen would show the old screen's comments.
Each poll also checks the address, for routers that change it with `pushState` and fire no event.
An answer that comes back after the screen changed is thrown away.

**Old comments are read, not rewritten.** Thread files are append-only, and the hub's existing
threads must keep working. Every comment already stored kept its full address in `page.url`. So
when a stored `page.path` has no `#` and `page.url` has a screen route, the route is added as the
thread is read (`pagePathOf`, called from `foldThread`). The files on disk stay exactly as they
were. The server applies the same rule to what a page sends (`cleanPage`), so a tab still running
the older script files new comments under their screen too. Because the rule runs where threads
are read, the page, `list`, `list --page`, `show`, `stats`, the watcher and the MCP tools all
agree.

**Found and not-found lines are signed `page`.** The line records what the page noticed, not what
a person said. `page` is now reserved: `config.json` cannot list it as an agent, and an API call
signed `page` gets a 403. Lines already signed `omar` stay as they are.

## How it was checked

- `test/hash-routes.test.mjs`: the rule (server and page copies), old files read under their route
  and left byte for byte the same, the server answering one screen's comments only, `list`,
  `stats`, `show` and the watcher agreeing, and the `page` signature.
- A copy of the hub's real threads: `list` grouped Omar's two resolved comments under
  `/#/topic/cup-mark/round/21` and `/#/topic/cup-mark/round/20`; `/` kept only the six made with no
  hash.
- Headless Chromium against a small hash app on a spare port: on `#/a` the bar showed screen a's
  comment and an old one filed under `/`; moving to `#/b` with no reload showed only b's; the back
  button returned to `#/a` with both; `#notes` and `#/` showed the first screen's; a comment typed
  on `#/b` was stored under `/#/b`. No found or not-found lines were written while switching.

There is still no automated browser test for the page script; these checks were by hand.
