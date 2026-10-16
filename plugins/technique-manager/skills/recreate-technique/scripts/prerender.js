#!/usr/bin/env node
/*
 * Render pages to static HTML with the same claude-ui components the browser uses, so a page
 * shows its content where JavaScript doesn't run: macOS Quick Look and Finder previews,
 * iCloud previews, feed readers, a blog that strips scripts. In a browser, React hydrates
 * that markup instead of drawing the page again.
 *
 * Needs only Node (no npm packages): it loads the vendored React UMD builds.
 *
 * Usage:  node prerender.js < jobs.json
 *   jobs.json: [{"component": "Page" | "Gallery" | "Catalog", "props": {...}}, ...]
 * Output: JSON array of HTML strings, one per job, in order. Exit 1 on any render error.
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const components = path.join(__dirname, "..", "components");
const files = [
  "vendor/react.production.min.js",
  "vendor/react-dom-server.production.min.js",
  "vendor/htm.umd.js",
  "claude-ui.js",
];

// A bare window: the UMD builds and claude-ui.js only need window/self to attach globals.
const sandbox = { console };
sandbox.window = sandbox;
sandbox.self = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
for (const f of files) {
  vm.runInContext(fs.readFileSync(path.join(components, f), "utf8"), sandbox, { filename: f });
}
const { React, ReactDOMServer, ClaudeUI } = sandbox;

const jobs = JSON.parse(fs.readFileSync(0, "utf8"));
const out = jobs.map((job, i) => {
  const Component = ClaudeUI[job.component];
  if (!Component) throw new Error(`job ${i}: no component ${job.component}`);
  return ReactDOMServer.renderToString(React.createElement(Component, job.props || {}));
});
process.stdout.write(JSON.stringify(out));
