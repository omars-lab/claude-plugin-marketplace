# Page comments: how `--vite` edits the Vite config, and how it was proven

**Status:** decided in development-manager 1.4.0
**Affects:** `plugins/development-manager/shared/scripts/vite.mjs`,
`skills/enable-page-comments/scripts/vite.template`,
`skills/enable-page-comments/scripts/enable.mjs` (`--vite`, `--vite --undo`, `--undo`)

## What the design said

Section 3: a dev-only Vite plugin that "only adds the tag and forwards `/__page-comments/` to the
same request handler", at the cost of editing `vite.config`.

## What was built, and where it departs

1. **A loader in the repo, the plugin in the plugin.** `vite.config` imports
   `./.page-comments/vite.mjs`, a small loader committed with the repo. It finds the installed
   plugin the way `.page-comments/run` does (`.state/plugin-root`, then Claude Code's
   `installed_plugins.json`) and hands back `shared/scripts/vite.mjs`'s plugin as a promise, which
   Vite waits for. On a machine without the plugin it warns once in `vite dev` and does nothing, so
   a teammate's clone and every build still work. Neither file imports Vite.
2. **Dev only.** The plugin has `apply: "serve"`; a `vite build` output has no trace of it (checked:
   zero matches for `__page-comments`).
3. **The edit is two marked lines, or a new file.** enable adds one import line ending in
   `// page-comments` and inserts `pageComments(), ` right after `plugins: [`. With no config it
   makes `vite.config.mjs`. It refuses, and prints what to add by hand, when the config is
   CommonJS (`.cjs`, `.cts`, or `require` with no `import`) or has no `plugins: [` or more than
   one. A tool that rewrote the config's syntax tree would need a parser, which this plugin does
   not ship. `--vite --undo` takes out exactly those two lines, byte for byte, or deletes the file
   it made if it is unchanged.
4. **TypeScript configs.** `vite.config.ts` and `.mts` are edited the same way. The loader is plain
   JavaScript with no type file, and Vite loads it without complaint. A project that type-checks
   its config strictly may want a one-line `declare module` for it; enable does not add one.
5. **The import path is relative to the config.** With `--vite-config web/vite.config.mjs` the line
   reads `../.page-comments/vite.mjs`.

## How it was proven, and why on a copy

Omar's live trial runs a Vite server on port 5173 from a scratch folder. To leave it untouched,
the proof copied that folder, linked its `node_modules`, enabled comments with `--vite`, and ran
real Vite 6.3.5 on port 5180.

Vite listens on `localhost`, which on macOS is `[::1]`, not `127.0.0.1`, so the checks use
`http://localhost:5180`. The comment API accepts either name.

| Check | Result |
|---|---|
| Page has the tag | `<script src="/__page-comments/client.js" data-token="…" defer>` |
| `health` | `{"ok":true,"mode":"vite"}` |
| `client.js` / Vite's own `main.js` | 200 / 200 |
| Comment POST from the page's origin | 201 |
| From another origin, with a bad token, or with a bad `Host` | 403 each |
| Thread file on disk, start line in the server log with `mode=vite` | 1 / 1 |
