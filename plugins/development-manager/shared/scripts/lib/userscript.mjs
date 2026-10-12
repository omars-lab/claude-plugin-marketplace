// The userscript way in (design section 9, "Closing the bookmarklet's token gap").
//
// A Tampermonkey script puts the comment bar on pages a repo's own server
// serves, on a port the comment server is not in front of. The page and the
// comment API are then on different origins, so the per-run token in an
// injected tag cannot reach it. Instead:
//   - a per-repo token lives in `.page-comments/.state/token`, which git ignores;
//   - the generated userscript, `.page-comments/.state/page-comments.user.js`,
//     carries that token, so it is ignored by git too;
//   - the server answers cross-origin calls only from the exact origins listed
//     in config.json's `userscript.origins`, and only with that token;
//   - `page-comments serve --rotate-token` makes a new token and writes the
//     userscript again.

import { randomBytes } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { paths, readConfig } from "./repo.mjs";

const PLUGIN_JSON = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", ".claude-plugin", "plugin.json");

/** `http://127.0.0.1:8765` from a URL-ish string, or null. Only http(s), no path. */
export function cleanOrigin(value) {
  if (typeof value !== "string") return null;
  const v = value.trim().replace(/\/+$/, "");
  if (!/^https?:\/\/[^/?#]+$/i.test(v)) return null;
  try {
    const u = new URL(v);
    return u.origin === "null" ? null : u.origin;
  } catch {
    return null;
  }
}

/** The origins config.json lists for the userscript, cleaned, without repeats. */
export function userscriptOrigins(config) {
  const u = config && config.userscript;
  const list = u && Array.isArray(u.origins) ? u.origins : [];
  return [...new Set(list.map(cleanOrigin).filter(Boolean))];
}

export function tokenPath(store) {
  return join(paths(store).state, "token");
}

export function userscriptPath(store) {
  return join(paths(store).state, "page-comments.user.js");
}

/** The repo's token, or null when there is none (or it was mangled). */
export function readRepoToken(store) {
  try {
    const t = readFileSync(tokenPath(store), "utf8").trim();
    return /^[0-9a-f]{32,128}$/.test(t) ? t : null;
  } catch {
    return null;
  }
}

/** Make a new repo token, readable only by this user. */
export function makeRepoToken(store) {
  const t = randomBytes(24).toString("hex");
  mkdirSync(paths(store).state, { recursive: true });
  writeFileSync(tokenPath(store), t + "\n", { mode: 0o600 });
  return t;
}

/** The comment server's own address, as the userscript should call it. */
export function serverOrigin(config) {
  const port = Number(config && config.serve && config.serve.port) || 8766;
  return `http://127.0.0.1:${port}`;
}

function pluginVersion() {
  try {
    return JSON.parse(readFileSync(PLUGIN_JSON, "utf8")).version || "0.0.0";
  } catch {
    return "0.0.0";
  }
}

/** The userscript's text. Every value goes in through JSON.stringify. */
export function userscriptText({ name, origins, server, token, version = pluginVersion() }) {
  const matches = origins.map((o) => `// @match        ${o}/*`).join("\n");
  return `// ==UserScript==
// @name         Page comments: ${name.replace(/[\r\n]/g, " ")}
// @namespace    development-manager/page-comments
// @version      ${version}
// @description  The page-comments bar on this repo's local pages. Written by development-manager's page-comments; it holds the repo's comment token, so keep it to yourself.
${matches}
// @run-at       document-idle
// @grant        none
// @noframes
// ==/UserScript==
//
// Written by \`enable.mjs --userscript\` or \`page-comments serve --rotate-token\`.
// Don't edit it: the next run writes it again. Install it in Tampermonkey again
// after each token change.

(function () {
  "use strict";

  // ---- Configuration ----
  var VERSION = ${JSON.stringify(version)}; // the same as @version
  var SERVER = ${JSON.stringify(server)}; // the comment server
  var ORIGINS = ${JSON.stringify(origins)}; // the pages it may run on
  var TOKEN = ${JSON.stringify(token)};

  // Script managers read @match ports differently, so the exact origin is checked here too.
  if (ORIGINS.indexOf(location.origin) < 0) return;
  // A page served through the comment server already has the bar.
  if (window.__pageComments || document.querySelector('script[src*="/__page-comments/client.js"]')) return;

  var s = document.createElement("script");
  s.src = SERVER + "/__page-comments/client.js";
  s.dataset.token = TOKEN;
  s.dataset.base = SERVER + "/__page-comments/";
  s.defer = true;
  s.onerror = function () {
    console.warn("[page-comments " + VERSION + "] no comment server at " + SERVER + ". Start it with: .page-comments/run serve --api-only");
  };
  (document.body || document.documentElement).appendChild(s);
})();
`;
}

/**
 * Write the userscript from config.json and the repo token, making the token
 * first if there is none. Returns { path, origins, server, madeToken } or null
 * when config.json lists no origins.
 */
export function writeUserscript(store, { version } = {}) {
  const config = readConfig(store);
  const origins = userscriptOrigins(config);
  if (!origins.length) return null;
  let token = readRepoToken(store);
  const madeToken = !token;
  if (!token) token = makeRepoToken(store);
  const server = serverOrigin(config);
  const path = userscriptPath(store);
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, userscriptText({ name: basename(store.repo), origins, server, token, version }), { mode: 0o600 });
  return { path, origins, server, madeToken };
}

/** A new token, and the userscript written again with it. */
export function rotateToken(store) {
  makeRepoToken(store);
  return writeUserscript(store);
}
