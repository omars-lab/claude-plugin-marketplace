// The userscript way in (design section 9): the per-repo token, the CORS rules
// for the listed origins, the script's text, and enable's --userscript. All data
// here is invented.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { request } from "node:http";
import { join } from "node:path";
import { test } from "node:test";
import { Script } from "node:vm";
import { startServer } from "../lib/server.mjs";
import { readAll } from "../lib/store.mjs";
import { cleanOrigin, readRepoToken, rotateToken, tokenPath, userscriptPath, userscriptText, writeUserscript } from "../lib/userscript.mjs";
import { CLI, ENABLE, SAMPLE, startChild, tempRepo, until } from "./helpers.mjs";

const PAGE = "http://127.0.0.1:8765"; // the repo's own page server, in these tests
const OTHER = "http://127.0.0.1:9999";

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
        resolve({ status: res.statusCode, headers: res.headers, text, json });
      });
    });
    req.on("error", reject);
    if (body !== undefined) req.write(typeof body === "string" ? body : JSON.stringify(body));
    req.end();
  });
}

function withConfig(store, config) {
  writeFileSync(join(store.dir, "config.json"), JSON.stringify(config));
}

const COMMENT = { page: SAMPLE.page, viewport: SAMPLE.viewport, anchor: SAMPLE.anchor, bodyHash: "a41c09e2b7d3", body: "Say how long the walk is." };

test("cleanOrigin keeps only http(s) scheme, host and port", () => {
  assert.equal(cleanOrigin("http://127.0.0.1:8765"), "http://127.0.0.1:8765");
  assert.equal(cleanOrigin("http://127.0.0.1:8765/"), "http://127.0.0.1:8765");
  assert.equal(cleanOrigin("HTTP://LOCALHOST:5173"), "http://localhost:5173");
  assert.equal(cleanOrigin("https://example.test:443"), "https://example.test");
  for (const bad of ["127.0.0.1:8765", "http://127.0.0.1:8765/trips/", "file:///tmp/x", "javascript:alert(1)", "http://x?y", "", null, 42]) assert.equal(cleanOrigin(bad), null, String(bad));
});

test("the userscript's text: one exact @match per origin, values escaped, and it parses", () => {
  const text = userscriptText({ name: "sample\nrepo", origins: [PAGE, "http://localhost:3000"], server: "http://127.0.0.1:8766", token: "ab".repeat(24), version: "9.9.9" });
  assert.match(text, /^\/\/ ==UserScript==\n/);
  assert.match(text, /\/\/ @name {9}Page comments: sample repo\n/, "a newline in the name cannot add a header line");
  assert.match(text, /\/\/ @match {8}http:\/\/127\.0\.0\.1:8765\/\*\n\/\/ @match {8}http:\/\/localhost:3000\/\*\n/);
  assert.match(text, /\/\/ @version {6}9\.9\.9\n/);
  assert.match(text, /\/\/ @grant {8}none\n/);
  assert.match(text, /\/\/ @noframes\n/);
  assert.match(text, /ORIGINS\.indexOf\(location\.origin\) < 0\) return;/, "the exact origin is checked at run time too");
  assert.match(text, /window\.__pageComments \|\|/, "it does not add a second bar");
  assert.match(text, /var TOKEN = "(ab){24}";/);
  new Script(text, { filename: "page-comments.user.js" }); // throws on a syntax error
  const odd = userscriptText({ name: "x", origins: [PAGE], server: 'http://127.0.0.1:8766"; alert(1); "', token: "cd".repeat(24), version: "1" });
  assert.ok(odd.includes('var SERVER = "http://127.0.0.1:8766\\"; alert(1); \\"";'), "values go in through JSON.stringify");
  new Script(odd);
});

test("writeUserscript makes the token once, readable by this user only; rotate makes a new one", () => {
  const { store, cleanup } = tempRepo();
  try {
    withConfig(store, { author: "sam", serve: { port: 8777 } });
    assert.equal(writeUserscript(store), null, "no origins listed: no script and no token");
    assert.equal(existsSync(tokenPath(store)), false);

    withConfig(store, { author: "sam", serve: { port: 8777 }, userscript: { origins: [PAGE, PAGE + "/", "not an origin"] } });
    const a = writeUserscript(store);
    assert.equal(a.madeToken, true);
    assert.deepEqual(a.origins, [PAGE], "cleaned and without repeats");
    assert.equal(a.server, "http://127.0.0.1:8777");
    const token = readRepoToken(store);
    assert.match(token, /^[0-9a-f]{48}$/);
    assert.equal(statSync(tokenPath(store)).mode & 0o077, 0, "the token file is private");
    assert.equal(statSync(userscriptPath(store)).mode & 0o077, 0, "the script file is private");
    assert.ok(readFileSync(userscriptPath(store), "utf8").includes(token));

    assert.equal(writeUserscript(store).madeToken, false, "a second write keeps the token");
    assert.equal(readRepoToken(store), token);

    rotateToken(store);
    const next = readRepoToken(store);
    assert.notEqual(next, token);
    const script = readFileSync(userscriptPath(store), "utf8");
    assert.ok(script.includes(next) && !script.includes(token), "the script carries the new token only");

    writeFileSync(tokenPath(store), "not-hex\n");
    assert.equal(readRepoToken(store), null, "a mangled token is no token");
  } finally {
    cleanup();
  }
});

test("CORS: a listed origin with the repo token is answered; every other mix is refused", async () => {
  const { store, cleanup } = tempRepo();
  withConfig(store, { author: "sam", userscript: { origins: [PAGE] } });
  writeUserscript(store);
  const repoToken = readRepoToken(store);
  const s = await startServer(store, { port: 0 });
  try {
    const t = (token, origin, extra = {}) => ({ ...(origin ? { origin } : {}), ...(token ? { "x-page-comments-token": token } : {}), ...extra });
    const get = (headers) => call(s.port, { path: "/__page-comments/threads", headers });
    const post = (headers) => call(s.port, { method: "POST", path: "/__page-comments/threads", headers: { "content-type": "application/json", ...headers }, body: COMMENT });

    const ok = await get(t(repoToken, PAGE));
    assert.equal(ok.status, 200);
    assert.equal(ok.headers["access-control-allow-origin"], PAGE);
    assert.match(ok.headers.vary || "", /Origin/);

    assert.equal((await get(t(s.token, PAGE))).status, 403, "listed origin with the per-run token");
    assert.equal((await get(t("0".repeat(48), PAGE))).status, 403, "listed origin with a wrong token");
    assert.equal((await get(t(null, PAGE))).status, 403, "listed origin with no token");
    const other = await get(t(repoToken, OTHER));
    assert.equal(other.status, 403, "an origin not on the list, with the repo token");
    assert.equal(other.headers["access-control-allow-origin"], undefined);
    assert.equal((await get(t(repoToken, null))).status, 403, "the repo token with no origin");
    assert.equal((await get(t(s.token, null))).status, 200, "the server's own page still uses its per-run token");

    assert.equal((await post(t(repoToken, OTHER))).status, 403);
    assert.equal((await post(t(s.token, PAGE))).status, 403);
    assert.equal((await post(t(repoToken, PAGE, { "content-type": "text/plain" }))).status, 415, "writes still need JSON");
    assert.equal(readAll(store).length, 0, "nothing was written by the refused calls");
    const made = await post(t(repoToken, PAGE));
    assert.equal(made.status, 201);
    assert.equal(made.json.thread.messages[0].author, "sam");

    const pre = await call(s.port, { method: "OPTIONS", path: "/__page-comments/threads", headers: { origin: PAGE, "access-control-request-method": "POST", "access-control-request-headers": "x-page-comments-token, content-type" } });
    assert.equal(pre.status, 204);
    assert.equal(pre.headers["access-control-allow-origin"], PAGE);
    assert.match(pre.headers["access-control-allow-headers"], /X-Page-Comments-Token/);
    assert.match(pre.headers["access-control-allow-methods"], /POST/);
    const preOther = await call(s.port, { method: "OPTIONS", path: "/__page-comments/threads", headers: { origin: OTHER, "access-control-request-method": "POST" } });
    assert.equal(preOther.status, 403);
    assert.equal(preOther.headers["access-control-allow-origin"], undefined);

    assert.equal((await call(s.port, { path: "/" })).status, 404, "an API-only server serves no pages");
    assert.deepEqual((await call(s.port, { path: "/__page-comments/health" })).json, { ok: true, mode: "api" });
    assert.equal((await call(s.port, { path: "/__page-comments/threads", headers: { host: "evil.example", origin: PAGE, "x-page-comments-token": repoToken } })).status, 403, "the Host check still comes first");

    const log = readFileSync(join(store.dir, ".state", "server.log"), "utf8");
    assert.ok(!log.includes(repoToken) && !log.includes(s.token), "no token reaches the log");
  } finally {
    await s.close();
    cleanup();
  }
});

test("CORS: a new origin, a removed one and a rotated token count without a restart", async () => {
  const { store, cleanup } = tempRepo();
  withConfig(store, { author: "sam" });
  const s = await startServer(store, { port: 0 });
  try {
    const get = (token, origin) => call(s.port, { path: "/__page-comments/threads", headers: { origin, "x-page-comments-token": token } });
    assert.equal((await get("ab".repeat(24), PAGE)).status, 403, "no list, no token: nothing cross-origin");

    withConfig(store, { author: "sam", userscript: { origins: [PAGE] } });
    writeUserscript(store);
    const first = readRepoToken(store);
    await until(async () => (await get(first, PAGE)).status === 200);

    rotateToken(store);
    const second = readRepoToken(store);
    await until(async () => (await get(second, PAGE)).status === 200);
    assert.equal((await get(first, PAGE)).status, 403, "the old token stops working");

    withConfig(store, { author: "sam" });
    await until(async () => (await get(second, PAGE)).status === 403);
  } finally {
    await s.close();
    cleanup();
  }
});

test("shot pictures take either token, since an <img> sends none", async () => {
  const { store, cleanup } = tempRepo();
  withConfig(store, { author: "sam", userscript: { origins: [PAGE] } });
  writeUserscript(store);
  const repoToken = readRepoToken(store);
  const s = await startServer(store, { port: 0 });
  try {
    const shot = (token) => call(s.port, { path: `/__page-comments/shots/t_abcdef/x.png?token=${token}` });
    assert.equal((await shot(repoToken)).status, 404, "the repo token gets past the token check");
    assert.equal((await shot(s.token)).status, 404);
    assert.equal((await shot("0".repeat(48))).status, 403);
  } finally {
    await s.close();
    cleanup();
  }
});

test("serve: exactly one of --target, --root or --api-only; --rotate-token writes the script again", async () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    withConfig(store, { author: "sam", serve: { port: 8777 }, userscript: { origins: [PAGE] } });
    for (const args of [["serve"], ["serve", "--api-only", "--root", "."], ["serve", "--target", PAGE, "--api-only"]]) {
      const r = spawnSync(process.execPath, [CLI, ...args, "--repo", repo], { encoding: "utf8", timeout: 20000 });
      assert.equal(r.status, 2, args.join(" "));
    }
    const run = startChild(CLI, ["serve", "--api-only", "--port", "0", "--rotate-token", "--repo", repo]);
    try {
      await until(() => /comment API only/.test(run.out()));
      assert.match(run.out(), /page-comments\.user\.js/);
      assert.match(run.out(), /Tampermonkey/);
      const token = readRepoToken(store);
      assert.ok(token && readFileSync(userscriptPath(store), "utf8").includes(token));
      assert.ok(!run.out().includes(token), "the token is not printed");
    } finally {
      await run.stop();
    }
  } finally {
    cleanup();
  }
});

function enable(args, repo) {
  const r = spawnSync(process.execPath, [ENABLE, ...args, "--repo", repo], { encoding: "utf8", timeout: 60000, env: { ...process.env, PAGE_COMMENTS_SKIP_CLAUDE: "1" } });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr };
}

test("enable --userscript lists the origin, writes the script with the token, and undo takes only that out", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    mkdirSync(join(repo, "site"));
    writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
    assert.equal(enable(["--userscript", "--origin", PAGE], repo).code, 3, "comments must be on first");
    assert.equal(enable(["--root", "site", "--port", "8766"], repo).code, 0);
    const dir = join(repo, ".page-comments");

    assert.equal(enable(["--userscript"], repo).code, 2, "no origin");
    assert.equal(enable(["--userscript", "--origin", "127.0.0.1:8765"], repo).code, 2, "not an origin");
    assert.equal(enable(["--userscript", "--origin", "http://127.0.0.1:8766"], repo).code, 2, "the comment server itself");

    const r = enable(["--userscript", "--origin", PAGE, "--origin", "http://localhost:8765/"], repo);
    assert.equal(r.code, 0, r.stderr);
    assert.match(r.stdout, /Import from file/);
    const config = JSON.parse(readFileSync(join(dir, "config.json"), "utf8"));
    assert.deepEqual(config.userscript.origins, [PAGE, "http://localhost:8765"]);
    assert.equal(config.serve.root, "site", "the rest of the config is kept");
    const token = readFileSync(join(dir, ".state", "token"), "utf8").trim();
    assert.ok(!r.stdout.includes(token), "the token is not printed");
    const script = readFileSync(join(dir, ".state", "page-comments.user.js"), "utf8");
    assert.ok(script.includes(token));
    const ignored = spawnSync("git", ["-C", repo, "check-ignore", ".page-comments/.state/token", ".page-comments/.state/page-comments.user.js"], { encoding: "utf8" });
    assert.equal(ignored.stdout.trim().split("\n").length, 2, "git ignores the token and the script");

    const again = enable(["--userscript", "--origin", PAGE], repo);
    assert.equal(again.code, 0);
    assert.equal(readFileSync(join(dir, ".state", "token"), "utf8").trim(), token, "a second run keeps the token");

    const off = enable(["--userscript", "--undo"], repo);
    assert.equal(off.code, 0, off.stderr);
    assert.equal(JSON.parse(readFileSync(join(dir, "config.json"), "utf8")).userscript, undefined);
    assert.equal(existsSync(join(dir, ".state", "token")), false);
    assert.equal(existsSync(join(dir, ".state", "page-comments.user.js")), false);
    assert.ok(existsSync(join(dir, "install.json")), "the rest stays on");
  } finally {
    cleanup();
  }
});
