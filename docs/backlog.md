# Backlog — plugin marketplace

Parked work and open decisions. One item per bullet; move it into `docs/issues/` or a plan when
it is picked up.

## Parked

- **Employer names in the public wiki plugin** (parked 2026-10-14). The `wiki-manager` plugin
  names a current and a former employer as example "spaces". They are in `plugin.json`,
  `README.md`, `references/hub.md`, `references/spaces.md` and `skills/introduce/SKILL.md`, and
  they are already on the public GitHub copy. Two ways out, Omar's call:
  1. Swap the names for invented ones in the current files, and add them to the pre-commit
     "text that must stay private" list so they can't come back. Older commits on GitHub still
     have them.
  2. Do (1) and also rewrite the GitHub history to remove them. This is a force-push to a public
     repo, can't be undone, and breaks every existing clone.
- **Try the Tampermonkey way of adding page comments in a real browser** (parked 2026-10-14).
  `development-manager`'s `enable-page-comments --userscript --origin <url>` writes a
  Tampermonkey script that puts the Comment button on pages whose own server can't be changed or
  put behind the comment server. It is covered by tests but has never been imported into
  Tampermonkey and used on a real page. No repo needs it yet: adventures gets the button through
  `make serve`. Pick it up when a repo first needs it. Steps then: run enable with `--userscript`,
  start the comment server with `serve --api-only`, import the script into Tampermonkey, leave a
  comment on the page, and check that it lands in `.page-comments/threads/`. The script holds the
  repo's token, so it is never pasted into chat or committed.
