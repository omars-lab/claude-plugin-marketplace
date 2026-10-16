// The dev-only Vite plugin (design section 3, phase 5), the small loader enable
// writes into the repo, and enable's --vite. Vite itself is not a dependency, so
// a stand-in plays its dev server: a real HTTP server running the middleware the
// plugin adds. All data here is invented.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { createServer, request } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { test } from "node:test";
import pageComments from "../vite.mjs";
import { readAll } from "../lib/store.mjs";
import { ENABLE, PLUGIN, SAMPLE, tempRepo } from "./helpers.mjs";

const TEMPLATE = join(PLUGIN, "skills", "enable-page-comments", "scripts", "vite.template");
const TYPES = join(PLUGIN, "skills", "enable-page-comments", "scripts", "vite-types.template");

function call(port, { method = "GET", path = "/", headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const req = request({ host: "127.0.0.1", port, method, path, headers: { host: `127.0.0.1:${port}`, ...headers }, setHost: false }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        const text = Buffer.concat(chunks).toString("utf8");
        let json = null;
        try {
          json = JSON.parse(text);
        } catch {
          json = null;
        }
        resolve({ status: res.statusCode, text, json });
      });
    });
    req.on("error", reject);
    if (body !== undefined) req.write(JSON.stringify(body));
    req.end();
  });
}

/** A stand-in for Vite's dev server: connect-style middleware, then Vite's own answer. */
async function fakeVite(plugin, root) {
  const stack = [];
  const warnings = [];
  const server = { config: { root, logger: { warn: (m) => warnings.push(m) } }, middlewares: { use: (fn) => stack.push(fn) } };
  if (plugin.configResolved) plugin.configResolved(server.config);
  plugin.configureServer(server);
  const http = createServer((req, res) => {
    let i = 0;
    const next = (err) => {
      if (err) {
        res.writeHead(500);
        return res.end("middleware error");
      }
      const fn = stack[i++];
      if (fn) return fn(req, res, next);
      res.writeHead(200, { "content-type": "text/plain" });
      res.end("vite answered");
    };
    next();
  });
  await new Promise((r) => http.listen(0, "127.0.0.1", r));
  return { port: http.address().port, warnings, close: () => new Promise((r) => http.close(r)) };
}

test("the plugin is dev-only and names itself", () => {
  const p = pageComments({ repo: tmpdir() });
  assert.equal(p.apply, "serve", "never in vite build or preview");
  assert.equal(p.name, "development-manager:page-comments");
  assert.equal(p.transformIndexHtml("<body>x</body>"), "<body>x</body>", "no tag before the server is set up");
});

test("in Vite's server: the tag goes into HTML, and /__page-comments/ gets the same checks", async () => {
  const { repo, store, cleanup } = tempRepo();
  writeFileSync(join(store.dir, "config.json"), JSON.stringify({ author: "sam" }));
  mkdirSync(join(repo, "app"));
  const plugin = pageComments(); // no repo: found from Vite's root
  const v = await fakeVite(plugin, join(repo, "app"));
  try {
    assert.deepEqual(v.warnings, []);
    const html = plugin.transformIndexHtml("<!doctype html><body><h1>Hi</h1></body>");
    assert.match(html, /<h1>Hi<\/h1><script [^>]*src="\/__page-comments\/client\.js"/);
    const token = /data-token="([0-9a-f]+)"/.exec(html)[1];

    assert.equal((await call(v.port, { path: "/src/main.js" })).text, "vite answered", "everything else is Vite's");
    assert.deepEqual((await call(v.port, { path: "/__page-comments/health" })).json, { ok: true, mode: "vite" });
    assert.equal((await call(v.port, { path: "/__page-comments/client.js" })).status, 200);
    assert.equal((await call(v.port, { path: "/__page-comments/health", headers: { host: "evil.example" } })).status, 403, "the Host must be Vite's own port");

    const own = `http://127.0.0.1:${v.port}`;
    const post = (headers) => call(v.port, { method: "POST", path: "/__page-comments/threads", headers: { "content-type": "application/json", ...headers }, body: { page: SAMPLE.page, viewport: SAMPLE.viewport, anchor: SAMPLE.anchor, bodyHash: "a41c09e2b7d3", body: "From Vite." } });
    assert.equal((await post({ origin: own, "x-page-comments-token": "0".repeat(32) })).status, 403, "wrong token");
    assert.equal((await post({ origin: "http://127.0.0.1:9999", "x-page-comments-token": token })).status, 403, "another origin");
    const made = await post({ origin: own, "x-page-comments-token": token });
    assert.equal(made.status, 201);
    assert.equal(readAll(store)[0].messages[0].author, "sam");
    assert.match(readFileSync(join(store.dir, ".state", "server.log"), "utf8"), /ev=start .*mode=vite/);
  } finally {
    await v.close();
    cleanup();
  }
});

test("with no .page-comments/ it warns once and stays out of the way", async () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const plugin = pageComments();
  const v = await fakeVite(plugin, repo);
  try {
    assert.equal(v.warnings.length, 1);
    assert.match(v.warnings[0], /no \.page-comments\/ folder/);
    assert.equal((await call(v.port, { path: "/__page-comments/health" })).text, "vite answered");
    assert.equal(plugin.transformIndexHtml("<body></body>"), "<body></body>");
  } finally {
    await v.close();
    cleanup();
  }
});

test("the loader in the repo finds the plugin, or stands down with a warning where it is not installed", async () => {
  const { store, cleanup } = tempRepo();
  const saved = process.env.CLAUDE_CONFIG_DIR;
  try {
    copyFileSync(TEMPLATE, join(store.dir, "vite.mjs"));
    mkdirSync(join(store.dir, ".state"), { recursive: true });
    writeFileSync(join(store.dir, ".state", "plugin-root"), PLUGIN + "\n");
    const loader = (await import(pathToFileURL(join(store.dir, "vite.mjs")).href + "?a")).default;
    const plugin = await loader();
    assert.equal(plugin.name, "development-manager:page-comments");
    assert.equal(plugin.apply, "serve");

    // A fresh clone on another machine: no .state/, and no plugin installed.
    writeFileSync(join(store.dir, ".state", "plugin-root"), "/nowhere\n");
    process.env.CLAUDE_CONFIG_DIR = mkdtempSync(join(tmpdir(), "pc-noclaude-"));
    const stub = await loader();
    assert.match(stub.name, /not installed/);
    assert.equal(stub.apply, "serve");
    const warnings = [];
    stub.configureServer({ config: { logger: { warn: (m) => warnings.push(m) } } });
    assert.equal(warnings.length, 1);
  } finally {
    if (saved === undefined) delete process.env.CLAUDE_CONFIG_DIR;
    else process.env.CLAUDE_CONFIG_DIR = saved;
    cleanup();
  }
});

function enable(args, repo) {
  const r = spawnSync(process.execPath, [ENABLE, ...args, "--repo", repo], { encoding: "utf8", timeout: 60000, env: { ...process.env, PAGE_COMMENTS_SKIP_CLAUDE: "1" } });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr };
}

function enabledRepo() {
  const t = tempRepo({ comments: false });
  mkdirSync(join(t.repo, "site"));
  writeFileSync(join(t.repo, "site", "index.html"), "<body>x</body>");
  const r = enable(["--root", "site"], t.repo);
  assert.equal(r.code, 0, r.stderr);
  return t;
}

const CONFIG = `import { defineConfig } from "vite";\nimport react from "@vitejs/plugin-react";\n\nexport default defineConfig({\n  plugins: [react()],\n  server: { port: 5173 },\n});\n`;

test("enable --vite edits a vite.config in two marked places, and undo puts it back byte for byte", () => {
  const { repo, cleanup } = enabledRepo();
  try {
    writeFileSync(join(repo, "vite.config.ts"), CONFIG);
    const r = enable(["--vite"], repo);
    assert.equal(r.code, 0, r.stderr);
    const edited = readFileSync(join(repo, "vite.config.ts"), "utf8");
    assert.ok(edited.startsWith('import pageComments from "./.page-comments/vite.mjs"; // page-comments\n'));
    assert.match(edited, /plugins: \[pageComments\(\), react\(\)\]/);
    assert.equal(readFileSync(join(repo, ".page-comments", "vite.mjs"), "utf8"), readFileSync(TEMPLATE, "utf8"));
    assert.equal(readFileSync(join(repo, ".page-comments", "vite.d.mts"), "utf8"), readFileSync(TYPES, "utf8"), "a vite.config.ts that type-checks needs the loader's types");
    assert.equal(enable(["--vite"], repo).code, 0);
    assert.equal(readFileSync(join(repo, "vite.config.ts"), "utf8"), edited, "a second run changes nothing");

    const off = enable(["--vite", "--undo"], repo);
    assert.equal(off.code, 0, off.stderr);
    assert.equal(readFileSync(join(repo, "vite.config.ts"), "utf8"), CONFIG);
    assert.equal(existsSync(join(repo, ".page-comments", "vite.mjs")), false);
    assert.equal(existsSync(join(repo, ".page-comments", "vite.d.mts")), false);
    assert.ok(existsSync(join(repo, ".page-comments", "install.json")), "the rest stays on");

    assert.equal(enable(["--vite"], repo).code, 0);
    assert.equal(enable(["--undo"], repo).code, 0);
    assert.equal(readFileSync(join(repo, "vite.config.ts"), "utf8"), CONFIG, "the full undo takes it out too");
  } finally {
    cleanup();
  }
});

test("enable --vite makes a vite.config when there is none, and undo removes only an untouched one", () => {
  const { repo, cleanup } = enabledRepo();
  try {
    assert.equal(enable(["--vite"], repo).code, 0);
    const made = readFileSync(join(repo, "vite.config.mjs"), "utf8");
    assert.match(made, /plugins: \[pageComments\(\), \]/);
    assert.equal(enable(["--vite", "--undo"], repo).code, 0);
    assert.equal(existsSync(join(repo, "vite.config.mjs")), false);

    assert.equal(enable(["--vite"], repo).code, 0);
    writeFileSync(join(repo, "vite.config.mjs"), readFileSync(join(repo, "vite.config.mjs"), "utf8") + "// mine\n");
    assert.equal(enable(["--vite", "--undo"], repo).code, 0);
    const kept = readFileSync(join(repo, "vite.config.mjs"), "utf8");
    assert.ok(!kept.includes("pageComments"), "the plugin is out");
    assert.ok(kept.includes("// mine"), "a config someone changed is kept");
  } finally {
    cleanup();
  }
});

test("enable --vite leaves a config it cannot edit safely alone, and says what to add", () => {
  const { repo, cleanup } = enabledRepo();
  try {
    const two = "export default {\n  plugins: [a()],\n  worker: { plugins: [b()] },\n};\n";
    writeFileSync(join(repo, "vite.config.js"), two);
    const r = enable(["--vite"], repo);
    assert.equal(r.code, 0, r.stderr);
    assert.match(r.stdout, /more than one/);
    assert.match(r.stdout, /pageComments\(\),/);
    assert.equal(readFileSync(join(repo, "vite.config.js"), "utf8"), two);

    const cjs = "module.exports = { plugins: [a()] };\n";
    writeFileSync(join(repo, "vite.config.cjs"), cjs);
    const c = enable(["--vite", "--vite-config", "vite.config.cjs"], repo);
    assert.match(c.stdout, /CommonJS/);
    assert.equal(readFileSync(join(repo, "vite.config.cjs"), "utf8"), cjs);
    assert.equal(enable(["--vite", "--vite-config", "nope.js"], repo).code, 3);
  } finally {
    cleanup();
  }
});

test("enable --vite --vite-config points the import at the right folder", () => {
  const { repo, cleanup } = enabledRepo();
  try {
    mkdirSync(join(repo, "web"));
    writeFileSync(join(repo, "web", "vite.config.js"), "export default {\n  plugins: [],\n};\n");
    const r = enable(["--vite", "--vite-config", "web/vite.config.js"], repo);
    assert.equal(r.code, 0, r.stderr);
    const edited = readFileSync(join(repo, "web", "vite.config.js"), "utf8");
    assert.ok(edited.startsWith('import pageComments from "../.page-comments/vite.mjs"; // page-comments\n'));
    assert.match(edited, /plugins: \[pageComments\(\), \]/);
  } finally {
    cleanup();
  }
});

test("enable --vite needs comments turned on first", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    assert.equal(enable(["--vite"], repo).code, 3);
    assert.equal(existsSync(join(repo, "vite.config.mjs")), false);
  } finally {
    cleanup();
  }
});
