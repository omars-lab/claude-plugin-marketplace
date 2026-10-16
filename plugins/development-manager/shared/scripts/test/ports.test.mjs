// Ports shared by several repos on one Mac: detect reads `PORT ?= n`, notices
// when the port is another repo's server and finds this repo's own; enable and
// check say when a port is taken; serve on a busy port says so in plain words.
// Every server here is a throwaway child on a free port; all data is invented.

import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { makePort } from "../../../skills/enable-page-comments/scripts/enable.mjs";
import { firstFreePort, portFree } from "../lib/ports.mjs";
import { CLI, ENABLE, tempRepo, until } from "./helpers.mjs";

const HAS_LSOF = !spawnSync("lsof", ["-v"], { stdio: "ignore" }).error;
const needLsof = HAS_LSOF ? {} : { skip: "lsof is not installed" };

const SERVER = `
const port = Number(process.argv[2]);
require("node:http").createServer((q, s) => { s.setHeader("content-type", "text/html"); s.end("<!doctype html><html><head></head><body>" + process.cwd().split("/").pop() + "</body></html>"); }).listen(port, "127.0.0.1", () => console.log("up " + port));
`;

/** A small page server run from `cwd` as `node <file> <port>`; resolves once it listens. */
async function serverIn(cwd, file, port) {
  writeFileSync(join(cwd, file), SERVER);
  const child = spawn(process.execPath, [file, String(port)], { cwd, stdio: ["ignore", "pipe", "pipe"] });
  let out = "";
  child.stdout.on("data", (d) => (out += d));
  await until(() => out.includes("up "));
  return () =>
    new Promise((done) => {
      if (child.exitCode !== null) return done();
      child.once("exit", () => done());
      child.kill("SIGTERM");
    });
}

function run(script, args, repo) {
  const r = spawnSync(process.execPath, [script, ...args, "--repo", repo], {
    encoding: "utf8",
    timeout: 60000,
    env: { ...process.env, PAGE_COMMENTS_SKIP_CLAUDE: "1" },
  });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr };
}

function seed(repo, makefile) {
  mkdirSync(join(repo, ".claude"), { recursive: true });
  writeFileSync(join(repo, "Makefile"), makefile);
  writeFileSync(join(repo, "CLAUDE.md"), "# Sample project\n");
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<!doctype html><html><head><title>Sample</title></head><body><h1>Hello</h1></body></html>");
}

test("makePort reads a number, $(or $(PORT),n), and $(PORT) with PORT ?= n", () => {
  assert.equal(makePort("", "\tpython3 -m http.server --port $(or $(PORT),8765)\n"), "8765");
  assert.equal(makePort("PORT            ?= 8770\n", "\tpython3 -m http.server $(PORT) --bind 127.0.0.1\n"), "8770");
  assert.equal(makePort("SITE_PORT := 4100\n", "\tnode serve.mjs --port $(SITE_PORT)\n"), "4100");
  assert.equal(makePort("", "\tnode serve.mjs --port 3001\n"), "3001");
  assert.equal(makePort("", "\tnode serve.mjs\n"), null);
});

test("detect warns when the port is another repo's server", needLsof, async () => {
  const mine = tempRepo({ comments: false });
  const other = tempRepo({ comments: false });
  const port = await firstFreePort(20100);
  const stop = await serverIn(other.repo, "other_site.js", port);
  try {
    seed(mine.repo, `PORT ?= ${port}\nserve:\n\tnode my_site.js $(PORT)\n`);
    const r = run(ENABLE, ["--detect", "--json"], mine.repo);
    assert.equal(r.code, 0, r.stderr);
    const d = JSON.parse(r.stdout);
    assert.equal(d.target, `http://127.0.0.1:${port}`);
    assert.equal(d.running.from, "other");
    assert.match(d.warning, new RegExp(`port ${port} belongs to another repo`));
    assert.match(d.why, /another repo's server/);
  } finally {
    await stop();
    mine.cleanup();
    other.cleanup();
  }
});

test("detect points at this repo's server when it runs on another port", needLsof, async () => {
  const mine = tempRepo({ comments: false });
  const other = tempRepo({ comments: false });
  const taken = await firstFreePort(20200);
  const moved = await firstFreePort(taken + 1);
  const stopOther = await serverIn(other.repo, "other_site.js", taken);
  const stopMine = await serverIn(mine.repo, "my_site.js", moved);
  try {
    seed(mine.repo, `serve:\n\tnode my_site.js --port $(or $(PORT),${taken})\n`);
    const d = JSON.parse(run(ENABLE, ["--detect", "--json"], mine.repo).stdout);
    assert.equal(d.target, `http://127.0.0.1:${moved}`);
    assert.deepEqual(d.running.mine, [moved]);
    assert.equal(d.warning, undefined);
  } finally {
    await stopOther();
    await stopMine();
    mine.cleanup();
    other.cleanup();
  }
});

test("enable takes a free comment port, and says when --port is in use", needLsof, async () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const busy = await firstFreePort(20300);
  const stop = await serverIn(repo, "holder.js", busy);
  try {
    seed(repo, "serve:\n\tnode site.js --port 8000\n");
    let r = run(ENABLE, ["--root", "site"], repo);
    assert.equal(r.code, 0, r.stderr);
    const port = JSON.parse(readFileSync(join(repo, ".page-comments", "config.json"), "utf8")).serve.port;
    assert.ok(port >= 8766, `picked ${port}`);
    assert.ok(await portFree(port), "the port it picked was free");
    assert.doesNotMatch(r.stdout, /careful:/);

    r = run(ENABLE, ["--root", "site", "--port", String(busy)], repo);
    assert.equal(r.code, 0, r.stderr);
    assert.match(r.stdout, new RegExp(`careful: port ${busy}, for the comment server, is in use by node holder\\.js`));
    assert.match(r.stdout, /Run enable again with --port \d+/);
  } finally {
    await stop();
    cleanup();
  }
});

test("check fails when the target is another repo's site, or the comment port is taken", needLsof, async () => {
  const mine = tempRepo({ comments: false });
  const other = tempRepo({ comments: false });
  const site = await firstFreePort(20400);
  const held = await firstFreePort(site + 1);
  const stopSite = await serverIn(other.repo, "other_site.js", site);
  const stopHeld = await serverIn(other.repo, "other_comments.js", held);
  try {
    seed(mine.repo, `serve:\n\tnode my_site.js --port ${site}\n`);
    const e = run(ENABLE, ["--target", `http://127.0.0.1:${site}`, "--port", String(held)], mine.repo);
    assert.equal(e.code, 0, e.stderr);
    assert.match(e.stdout, new RegExp(`careful: the target, port ${site}, is served by another repo right now`));
    const r = run(ENABLE, ["--check"], mine.repo);
    assert.equal(r.code, 1, r.stdout);
    assert.match(r.stdout, new RegExp(`FAIL  port ${held} is free for the comment server: in use by node other_comments\\.js`));
    assert.match(r.stdout, new RegExp(`FAIL  this repo's site is running on port ${site}: port ${site} is another repo's server`));
  } finally {
    await stopSite();
    await stopHeld();
    mine.cleanup();
    other.cleanup();
  }
});

test("check passes the port lines when this repo's site is the one running", needLsof, async () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const site = await firstFreePort(20500);
  const stop = await serverIn(repo, "my_site.js", site);
  try {
    seed(repo, `serve:\n\tnode my_site.js --port ${site}\n`);
    assert.equal(run(ENABLE, ["--target", `http://127.0.0.1:${site}`], repo).code, 0);
    const r = run(ENABLE, ["--check"], repo);
    assert.match(r.stdout, /ok\s+port \d+ is free for the comment server/);
    assert.match(r.stdout, new RegExp(`ok\\s+this repo's site is running on port ${site}: node my_site\\.js`));
    assert.match(r.stdout, /ok\s+pages get the comment bar/);
    assert.equal(r.code, 0, r.stdout);
  } finally {
    await stop();
    cleanup();
  }
});

test("serve on a busy port says who has it and a free one, without a stack trace", needLsof, async () => {
  const { repo, cleanup } = tempRepo();
  const busy = await firstFreePort(20600);
  const stop = await serverIn(repo, "holder.js", busy);
  try {
    mkdirSync(join(repo, "site"));
    writeFileSync(join(repo, "site", "index.html"), "<p>hi</p>");
    const r = run(CLI, ["serve", "--root", "site", "--port", String(busy), "--throwaway"], repo);
    assert.equal(r.code, 1);
    assert.match(r.stderr, new RegExp(`port ${busy} is already in use by another server: node holder\\.js`));
    assert.match(r.stderr, /pass --port \d+ here, or run enable-page-comments again with --port \d+/);
    assert.doesNotMatch(r.stderr, /\n\s+at /, "no stack trace");
  } finally {
    await stop();
    cleanup();
  }
});
