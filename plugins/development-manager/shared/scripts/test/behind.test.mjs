// serve --behind: the comment server starts the repo's own page server on a
// spare port, serves its pages with the comment button, and stops it on exit.
// Every server here is a throwaway child on a free port; all data is invented.

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { freePort } from "../lib/behind.mjs";
import { CLI, cli, startChild, tempRepo, until } from "./helpers.mjs";

// A tiny page server: `node site.js <port>` serves one page and a JSON answer,
// and writes its pid to site.pid so a test can check it was stopped.
const SITE = `
const http = require("http");
const fs = require("fs");
const port = Number(process.argv[2] || process.env.PORT);
fs.writeFileSync("site.pid", String(process.pid));
http.createServer((req, res) => {
  if (req.url === "/api") { res.writeHead(200, { "content-type": "application/json" }); return res.end('{"ok":true}'); }
  res.writeHead(200, { "content-type": "text/html" });
  res.end("<html><body><h1>Sample page</h1></body></html>");
}).listen(port, "127.0.0.1");
`;

function alive(pid) {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

const require_ = (file) => readFileSync(file, "utf8").trim();

function seed(repo) {
  writeFileSync(join(repo, "site.js"), SITE);
}

test("serve --behind starts the page server behind and adds the comment button", async () => {
  const { repo, cleanup } = tempRepo();
  seed(repo);
  const port = await freePort();
  const s = startChild(CLI, ["serve", "--behind", `${JSON.stringify(process.execPath)} site.js {port}`, "--port", String(port), "--repo", repo, "--throwaway"]);
  try {
    await until(() => /Comment server on/.test(s.out()), 15000);
    assert.match(s.out(), /in front of the page server on port \d+/);
    const page = await (await fetch(`http://127.0.0.1:${port}/`)).text();
    assert.match(page, /Sample page/);
    assert.match(page, /page-comments/i, "the page gets the comment button");
    const api = await (await fetch(`http://127.0.0.1:${port}/api`)).json();
    assert.deepEqual(api, { ok: true }, "other answers pass through unchanged");
    const pid = Number(await until(() => {
      try {
        return require_(join(repo, "site.pid"));
      } catch {
        return null;
      }
    }));
    assert.ok(alive(pid));
    assert.equal(await s.stop(), 0);
    await until(() => !alive(pid), 8000);
  } finally {
    await s.stop();
    cleanup();
  }
});

test("the PORT variable carries the port too", async () => {
  const { repo, cleanup } = tempRepo();
  seed(repo);
  const port = await freePort();
  const s = startChild(CLI, ["serve", "--behind", `${JSON.stringify(process.execPath)} site.js`, "--port", String(port), "--repo", repo, "--throwaway"]);
  try {
    await until(() => /Comment server on/.test(s.out()), 15000);
    assert.match(await (await fetch(`http://127.0.0.1:${port}/`)).text(), /Sample page/);
  } finally {
    await s.stop();
    cleanup();
  }
});

test("a page server that stops before it is ready fails with its exit code", () => {
  const { repo, cleanup } = tempRepo();
  try {
    const r = cli(["serve", "--behind", "exit 7", "--port", "0", "--repo", repo, "--throwaway"]);
    assert.equal(r.code, 7);
    assert.match(r.stderr, /stopped before it was ready \(exit 7\)/);
  } finally {
    cleanup();
  }
});

test("when the page server stops, the comment server stops with its code", async () => {
  const { repo, cleanup } = tempRepo();
  seed(repo);
  const port = await freePort();
  const s = startChild(CLI, ["serve", "--behind", `${JSON.stringify(process.execPath)} site.js {port}`, "--port", String(port), "--repo", repo, "--throwaway"]);
  try {
    await until(() => /Comment server on/.test(s.out()), 15000);
    const pid = Number(require_(join(repo, "site.pid")));
    process.kill(pid, "SIGKILL");
    const code = await new Promise((res) => (s.child.exitCode !== null ? res(s.child.exitCode) : s.child.once("exit", res)));
    assert.notEqual(code, 0);
    assert.match(s.err(), /the page server stopped/);
  } finally {
    await s.stop();
    cleanup();
  }
});

test("a stop while the page server is still starting stops the page server too", async () => {
  const { repo, cleanup } = tempRepo();
  // Writes its pid, then waits before it opens a port, so the stop lands mid-start.
  writeFileSync(join(repo, "slow.js"), `require("fs").writeFileSync("slow.pid", String(process.pid)); setTimeout(() => require("http").createServer(() => {}).listen(+process.env.PORT, "127.0.0.1"), 20000);`);
  const port = await freePort();
  const s = startChild(CLI, ["serve", "--behind", `${JSON.stringify(process.execPath)} slow.js`, "--port", String(port), "--repo", repo, "--throwaway"]);
  try {
    const pid = Number(await until(() => {
      try {
        return require_(join(repo, "slow.pid"));
      } catch {
        return null;
      }
    }, 15000));
    assert.ok(alive(pid));
    s.child.kill("SIGTERM");
    await until(() => !alive(pid), 8000);
    assert.ok(!/Comment server on/.test(s.out()), "it never got as far as serving");
  } finally {
    await s.stop();
    cleanup();
  }
});

test("a busy port fails before the page server starts", async () => {
  const { repo, cleanup } = tempRepo();
  seed(repo);
  const port = await freePort();
  const holder = startChild(CLI, ["serve", "--api-only", "--port", String(port), "--repo", repo, "--throwaway"]);
  try {
    await until(() => /Comment server on/.test(holder.out()), 15000);
    const r = cli(["serve", "--behind", "touch started; sleep 30", "--port", String(port), "--repo", repo, "--throwaway"]);
    assert.equal(r.code, 1);
    assert.match(r.stderr, /already in use/);
    assert.throws(() => require_(join(repo, "started")), "the page server never ran");
  } finally {
    await holder.stop();
    cleanup();
  }
});

test("serve with no mode uses the one in config.json, and two modes is bad usage", async () => {
  const { repo, cleanup } = tempRepo();
  seed(repo);
  const port = await freePort();
  writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ v: 1, serve: { behind: `${JSON.stringify(process.execPath)} site.js {port}`, port } }));
  const s = startChild(CLI, ["serve", "--repo", repo, "--throwaway"]);
  try {
    await until(() => /Comment server on/.test(s.out()), 15000);
    assert.match(s.out(), new RegExp(`127\\.0\\.0\\.1:${port}/`));
    assert.match(await (await fetch(`http://127.0.0.1:${port}/`)).text(), /Sample page/);
  } finally {
    await s.stop();
  }
  try {
    assert.equal(cli(["serve", "--root", ".", "--behind", "true", "--repo", repo]).code, 2);
    writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ v: 1 }));
    const r = cli(["serve", "--repo", repo]);
    assert.equal(r.code, 2);
    assert.match(r.stderr, /config\.json names none/);
  } finally {
    cleanup();
  }
});
