# Page comments: the MCP server's tools, and how `.mcp.json` starts it

**Status:** decided in development-manager 1.4.0
**Affects:** `plugins/development-manager/shared/scripts/mcp.mjs`,
`plugins/development-manager/.mcp.json`, the repo-root `.gitignore`

## What the design said

Section 10: an MCP wrapper over the command line, modelled on review-md's `reviews-mcp.mjs`.
Section 11: started from `.mcp.json` as `node ${CLAUDE_PLUGIN_ROOT}/shared/scripts/mcp.mjs`. The
stage 5 brief asked for that path quoted, because the plugin validator now requires quoted plugin
paths in commands.

## What was built, and where it departs

1. **`args` array, not a quoted command string.** `.mcp.json` says
   `{"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/shared/scripts/mcp.mjs"]}`. That is the form
   review-md uses, and the path is one argument, so a space in it cannot split it: the same
   protection quoting gives in a shell command. Nothing is run through a shell here, so there are no
   quotes to add. The validator checks hooks and monitors, not `.mcp.json`. A test pins the shape.
2. **Seven tools, not review-md's eight.** `list`, `show`, `stats`, `reply`, `resolve` (with
   `reopen`), `dismiss` and `shot`, each running the command line with `--json` where it has one.
   - No `find` or `diff`: the command line has neither; a page has no text diff to show.
   - No `comment`: new threads start on the page, pinned to an element. Claude answers threads; it
     does not open them.
   - Added `dismiss` and `shot`, which page comments have and review-md does not.
3. **A message that starts with `--` stays the message.** Every tool puts its flags first, then
   `--`, then the thread id and text.
4. **Only its own tools.** A tool name is looked up with `hasOwnProperty`, so names like `toString`
   are refused.
5. **The repo-root `.gitignore` ignored every `.mcp.json`.** The line was meant for the
   marketplace's own local MCP config, which may hold keys. It is now `/.mcp.json`, so it still
   covers that file but no longer hides a plugin's `.mcp.json`, which must ship with the plugin.

## Proof (2026-10-12)

A real stdio round trip under Node 18, in a throwaway repo with one open thread: `initialize`
answered with `serverInfo` `page-comments` and the plugin's version; `tools/list` listed the seven
tools; `tools/call list` and `stats` returned the thread and the counts. The tests also run
`ping`, every tool, and the error cases (no comments in the folder, an unknown thread, a path in
place of an id, a missing argument, an unknown tool or method, and bad JSON).
