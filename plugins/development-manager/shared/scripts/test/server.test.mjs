import { test } from "node:test";
import assert from "node:assert/strict";
import { createServer, request } from "node:http";
import { connect } from "node:net";
import { existsSync, mkdirSync, readFileSync, symlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { injectTag, phoneSetting, startServer, whoIsAsking } from "../lib/server.mjs";
import { readAll } from "../lib/store.mjs";
import { SAMPLE, tempRepo } from "./helpers.mjs";

/** One raw HTTP call, so Host and Origin can be set to anything. */
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

const tokenOf = (html) => /data-token="([0-9a-f]+)"/.exec(html)[1];

function writeHeaders(port, token, extra = {}) {
  return { origin: `http://127.0.0.1:${port}`, "content-type": "application/json", "x-page-comments-token": token, ...extra };
}

/** A stand-in for a site's own dev server: HTML, JSON, a PUT API and a socket. */
function fakeTarget() {
  const seen = [];
  const srv = createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      seen.push({ method: req.method, url: req.url, headers: req.headers, body: Buffer.concat(chunks).toString("utf8") });
      if (req.url.startsWith("/api/marks/")) {
        res.writeHead(200, { "content-type": "application/json" });
        return res.end(JSON.stringify({ saved: true, got: JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}") }));
      }
      if (req.url === "/nobody") {
        res.writeHead(200, { "content-type": "text/html", etag: '"abc"' });
        return res.end("<p>no closing body tag</p>");
      }
      if (req.url === "/chunked") {
        res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
        res.write("<html><body><h1>Part one</h1>");
        return setTimeout(() => res.end("<p>part two</p></body></html>"), 20);
      }
      res.writeHead(200, { "content-type": "text/html; charset=utf-8", "content-length": 52 });
      res.end("<html><body><h1>Sample trip</h1><p>x</p></body></html>".slice(0, 52));
    });
  });
  srv.on("upgrade", (req, socket) => {
    seen.push({ upgrade: true, url: req.url, headers: req.headers });
    socket.write("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n");
    socket.on("data", (d) => socket.write(Buffer.concat([Buffer.from("echo:"), d])));
  });
  return new Promise((r) => srv.listen(0, "127.0.0.1", () => r({ srv, port: srv.address().port, seen })));
}

test("the tag goes before the last </body>, or at the end", () => {
  assert.equal(injectTag("<body>a</body></html>", "t1"), '<body>a<script src="/__page-comments/client.js" data-token="t1" defer></script></body></html>');
  assert.match(injectTag("<p>no body", "t1"), /<p>no body<script /);
  assert.match(injectTag("<BODY>x</BODY>", "t1"), /x<script .*><\/BODY>$/);
});

test("a page that already has a tag (Vite's, behind --target) ends up with one: this server's", () => {
  const fromVite = injectTag("<html><body><div id=root></div></body></html>", "aaaa");
  const both = injectTag(fromVite, "bbbb");
  assert.equal((both.match(/data-token=/g) || []).length, 1);
  assert.equal(tokenOf(both), "bbbb");
  assert.equal(both, '<html><body><div id=root></div><script src="/__page-comments/client.js" data-token="bbbb" defer></script></body></html>');
});

test("proxy mode: HTML gets the tag with a fixed length; everything else passes through", async () => {
  const { store, cleanup } = tempRepo();
  const t = await fakeTarget();
  const s = await startServer(store, { target: `http://127.0.0.1:${t.port}`, port: 0 });
  try {
    const page = await call(s.port, { path: "/trips/sample/", headers: { "accept-encoding": "gzip", "if-none-match": '"old"' } });
    assert.equal(page.status, 200);
    assert.match(page.text, /<p>x<\/p><script src="\/__page-comments\/client.js" data-token="[0-9a-f]{32}" defer><\/script><\/body>/);
    assert.equal(Number(page.headers["content-length"]), Buffer.byteLength(page.text));
    assert.equal(page.headers["cache-control"], "no-store");
    const upstream = t.seen.find((x) => x.url === "/trips/sample/");
    assert.equal(upstream.headers["accept-encoding"], "identity", "asks the target for plain HTML");
    assert.equal(upstream.headers["if-none-match"], undefined, "never a 'not modified' page with an old token");
    assert.equal(upstream.headers.host, `127.0.0.1:${t.port}`);

    const chunked = await call(s.port, { path: "/chunked" });
    assert.match(chunked.text, /part two<\/p><script /);
    assert.equal(chunked.headers["transfer-encoding"], undefined);
    const nobody = await call(s.port, { path: "/nobody" });
    assert.match(nobody.text, /<\/p><script .*<\/script>$/);
    assert.equal(nobody.headers.etag, undefined);

    // The site's own API, as the trip planner's PUT /api/marks/<slug> uses it:
    // only the Host is checked, no token or Origin from the comment server.
    const put = await call(s.port, { method: "PUT", path: "/api/marks/sample", headers: { "content-type": "application/json", origin: `http://127.0.0.1:${s.port}` }, body: { items: { a: 1 } } });
    assert.equal(put.status, 200);
    assert.deepEqual(put.json, { saved: true, got: { items: { a: 1 } } });
    assert.ok(!put.text.includes("data-token"));
  } finally {
    await s.close();
    t.srv.close();
    cleanup();
  }
});

test("proxy mode: socket upgrades (live reload) are piped through", async () => {
  const { store, cleanup } = tempRepo();
  const t = await fakeTarget();
  const s = await startServer(store, { target: `http://127.0.0.1:${t.port}`, port: 0 });
  try {
    const got = await new Promise((resolve, reject) => {
      const sock = connect(s.port, "127.0.0.1", () => {
        sock.write(`GET /live HTTP/1.1\r\nHost: 127.0.0.1:${s.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n`);
      });
      let buf = "";
      sock.on("data", (d) => {
        buf += d;
        if (buf.includes("\r\n\r\n") && !buf.includes("echo:")) sock.write("ping");
        if (buf.includes("echo:ping")) {
          sock.end();
          resolve(buf);
        }
      });
      sock.on("error", reject);
    });
    assert.match(got, /^HTTP\/1.1 101/);
    assert.equal(t.seen.find((x) => x.upgrade).headers.host, `127.0.0.1:${t.port}`);
  } finally {
    await s.close();
    t.srv.close();
    cleanup();
  }
});

test("folder mode: serves files, adds the tag to HTML, refuses paths outside", async () => {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site", "trips"), { recursive: true });
  writeFileSync(join(repo, "site", "index.html"), "<!doctype html><body><h1>Home</h1></body>");
  writeFileSync(join(repo, "site", "trips", "index.html"), "<body>Trips</body>");
  writeFileSync(join(repo, "site", "app.css"), "h1{color:red}");
  writeFileSync(join(repo, "secret.txt"), "not served");
  symlinkSync(join(repo, "secret.txt"), join(repo, "site", "link.txt"));
  const s = await startServer(store, { root: "site", port: 0 });
  try {
    const home = await call(s.port, { path: "/" });
    assert.match(home.text, /<h1>Home<\/h1><script /);
    assert.equal(Number(home.headers["content-length"]), Buffer.byteLength(home.text));
    const css = await call(s.port, { path: "/app.css" });
    assert.equal(css.text, "h1{color:red}");
    assert.match(css.headers["content-type"], /text\/css/);
    assert.equal((await call(s.port, { path: "/trips" })).status, 301);
    assert.match((await call(s.port, { path: "/trips/" })).text, /Trips<script /);
    for (const path of ["/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt", "/%2e%2e%2fsecret.txt"]) {
      const r = await call(s.port, { path });
      assert.notEqual(r.status, 200, path);
      assert.ok(!r.text.includes("not served"), path);
    }
    assert.equal((await call(s.port, { path: "/link.txt" })).status, 403);
    assert.equal((await call(s.port, { path: "/missing.html" })).status, 404);
    const js = await call(s.port, { path: "/__page-comments/client.js" });
    assert.equal(js.status, 200, "the page script needs no token");
    assert.match(js.headers["content-type"], /javascript/);
  } finally {
    await s.close();
    cleanup();
  }
});

test("the Host must be this server's own, on every request", async () => {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
  const s = await startServer(store, { root: "site", port: 0 });
  try {
    assert.equal((await call(s.port, { path: "/", headers: { host: "evil.example:80" } })).status, 403);
    assert.equal((await call(s.port, { path: "/", headers: { host: `evil.example:${s.port}` } })).status, 403);
    assert.equal((await call(s.port, { path: "/__page-comments/client.js", headers: { host: "rebound.example" } })).status, 403);
    assert.equal((await call(s.port, { path: "/", headers: { host: `localhost:${s.port}` } })).status, 200);
    assert.equal((await call(s.port, { path: "/", headers: { host: `[::1]:${s.port}` } })).status, 200);
  } finally {
    await s.close();
    cleanup();
  }
});

test("API writes need the token, this server's Origin and JSON", async () => {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
  writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ author: "sam" }));
  const s = await startServer(store, { root: "site", port: 0 });
  try {
    const token = tokenOf((await call(s.port, { path: "/" })).text);
    assert.equal(token, s.token);
    const comment = { page: SAMPLE.page, viewport: SAMPLE.viewport, anchor: SAMPLE.anchor, bodyHash: "a41c09e2b7d3", body: "Say how long the walk is." };
    const post = (headers, body = comment) => call(s.port, { method: "POST", path: "/__page-comments/threads", headers, body });

    assert.equal((await post(writeHeaders(s.port, "0".repeat(32)))).status, 403, "wrong token");
    assert.equal((await post({ origin: `http://127.0.0.1:${s.port}`, "content-type": "application/json" })).status, 403, "no token");
    assert.equal((await post(writeHeaders(s.port, token, { origin: "http://evil.example" }))).status, 403, "another site");
    assert.equal((await post(writeHeaders(s.port, token, { origin: "http://127.0.0.1:9999" }))).status, 403, "another local tab");
    const noOrigin = writeHeaders(s.port, token);
    delete noOrigin.origin;
    assert.equal((await post(noOrigin)).status, 403, "no origin");
    assert.equal((await post(writeHeaders(s.port, token, { "content-type": "text/plain" }))).status, 415);
    assert.equal((await post(writeHeaders(s.port, token), { ...comment, body: "  " })).status, 400);
    assert.equal((await post(writeHeaders(s.port, token), "x".repeat(70 * 1024))).status, 413);
    assert.equal((await call(s.port, { path: "/__page-comments/threads" })).status, 403, "reads need the token too");
    assert.equal(readAll(store).length, 0, "nothing was written by the refused calls");

    const made = await post(writeHeaders(s.port, token));
    assert.equal(made.status, 201);
    const t = made.json.thread;
    assert.equal(t.messages[0].author, "sam", "the author comes from the repo's config, not the page");
    assert.equal(t.rev.bodyHash, "a41c09e2b7d3");
    assert.match(t.rev.git.commit, /^[0-9a-f]{7,}$/);
    assert.equal(typeof t.rev.git.dirty, "boolean");

    const reply = await call(s.port, { method: "POST", path: `/__page-comments/threads/${t.id}/replies`, headers: writeHeaders(s.port, token), body: { body: "And on day 3." } });
    assert.equal(reply.json.thread.messages.length, 2);
    const resolved = await call(s.port, { method: "POST", path: `/__page-comments/threads/${t.id}/status`, headers: writeHeaders(s.port, token), body: { status: "resolved" } });
    assert.equal(resolved.json.thread.status, "resolved");
    const bad = await call(s.port, { method: "POST", path: `/__page-comments/threads/${t.id}/status`, headers: writeHeaders(s.port, token), body: { status: "deleted" } });
    assert.equal(bad.status, 400);
    assert.equal((await call(s.port, { method: "POST", path: "/__page-comments/threads/t_ffffff/replies", headers: writeHeaders(s.port, token), body: { body: "x" } })).status, 404);

    const list = await call(s.port, { path: "/__page-comments/threads?page=%2Ftrips%2Fsample%2F", headers: { "x-page-comments-token": token } });
    assert.equal(list.json.threads.length, 1);
    const again = await call(s.port, { path: `/__page-comments/threads?since=${list.json.version}`, headers: { "x-page-comments-token": token } });
    assert.equal(again.json.changed, false);
    assert.equal(list.headers["access-control-allow-origin"], undefined, "no cross-origin answers");

    const log = readFileSync(join(repo, ".page-comments", ".state", "server.log"), "utf8");
    assert.ok(!log.includes(token), "the token never reaches the log");
    assert.ok(existsSync(join(repo, ".page-comments", ".state", "server.json")));
  } finally {
    await s.close();
    cleanup();
  }
  assert.equal(existsSync(join(repo, ".page-comments", ".state", "server.json")), false);
});

test("each start makes a new token", async () => {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
  try {
    const a = await startServer(store, { root: "site", port: 0 });
    await a.close();
    const b = await startServer(store, { root: "site", port: 0 });
    await b.close();
    assert.notEqual(a.token, b.token);
  } finally {
    cleanup();
  }
});

// ---- The phone, through tailscale serve (design section 13) --------------------------------
// Invented tailnet name and logins. Tailscale passes the phone's Host on as
// `<name>:<port>` and sets Tailscale-User-Login itself (checked 2026-10-12).

const PHONE_HOST = "sample-mac.tailnet-example.ts.net";
const PHONE_LOGIN = "person@example.com";

async function phoneServer({ phone } = {}) {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
  const s = await startServer(store, { root: "site", port: 0 });
  const p = { host: PHONE_HOST, port: s.port, logins: [PHONE_LOGIN], ...phone };
  writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ author: "sam", phone: p }));
  return { repo, store, s, cleanup: async () => (await s.close(), cleanup()) };
}

const viaTailscale = (port, extra = {}) => ({ host: `${PHONE_HOST}:${port}`, "tailscale-user-login": PHONE_LOGIN, ...extra });

test("phoneSetting reads the phone block, and turns away a bad one", () => {
  assert.equal(phoneSetting({}), null);
  assert.equal(phoneSetting({ phone: { host: "x", port: 8766 } }), null, "not a dotted name");
  assert.equal(phoneSetting({ phone: { host: PHONE_HOST, port: "nope" } }), null);
  const p = phoneSetting({ phone: { host: `${PHONE_HOST.toUpperCase()}.`, port: 8766, logins: [" Person@Example.com ", 7], authors: { "person@example.com": "sam" } } });
  assert.deepEqual(p, { host: PHONE_HOST, port: 8766, hosts: [`${PHONE_HOST}:8766`], logins: [PHONE_LOGIN], authors: { [PHONE_LOGIN]: "sam" } });
  assert.deepEqual(phoneSetting({ phone: { host: PHONE_HOST, port: 443 } }).hosts, [`${PHONE_HOST}:443`, PHONE_HOST], "port 443 also comes without the port");
});

test("whoIsAsking: local requests unchanged; Tailscale ones need a login on the list", () => {
  const localHosts = new Set(["127.0.0.1:8766", "localhost:8766", "[::1]:8766"]);
  const phone = phoneSetting({ phone: { host: PHONE_HOST, port: 8766, logins: [PHONE_LOGIN], authors: { [PHONE_LOGIN]: "omar" } } });
  const ask = (headers, p = phone) => whoIsAsking(headers, { localHosts, phone: p, author: "sam" });
  assert.deepEqual(ask({ host: "127.0.0.1:8766" }), { ok: true, via: "local", origin: "http://127.0.0.1:8766", author: "sam" });
  assert.equal(ask({ host: "evil.example:8766" }).reason, "host");
  // A local router passes <name>.localhost through, on its own port or none.
  assert.deepEqual(ask({ host: "instagram.localhost:7100" }), { ok: true, via: "local", origin: "http://instagram.localhost:7100", author: "sam" });
  assert.equal(ask({ host: "instagram.localhost" }).origin, "http://instagram.localhost");
  for (const host of ["localhost.evil.example", "evil.localhost.example", "x.localhost:7100/", ".localhost", "-x.localhost"]) {
    assert.equal(ask({ host }).reason, "host", host);
  }
  assert.equal(ask({ host: `${PHONE_HOST}:8766` }, null).reason, "host", "no phone block: the tailnet name is just another host");
  assert.equal(ask({ host: `${PHONE_HOST}:9999`, "tailscale-user-login": PHONE_LOGIN }).reason, "host", "another port on the tailnet name");
  assert.equal(ask({ host: `${PHONE_HOST}:8766` }).reason, "no_login", "a tagged device, or a forged Host with no login");
  assert.equal(ask({ host: `${PHONE_HOST}:8766`, "tailscale-user-login": "" }).reason, "no_login");
  assert.equal(ask({ host: `${PHONE_HOST}:8766`, "tailscale-user-login": "someone-else@example.com" }).reason, "login_not_allowed");
  assert.deepEqual(ask({ host: `${PHONE_HOST}:8766`, "tailscale-user-login": "PERSON@example.com" }), {
    ok: true,
    via: "tailscale",
    origin: `https://${PHONE_HOST}:8766`,
    author: "omar",
    login: PHONE_LOGIN,
  });
  // A login header on the local Host did not come through Tailscale. It is held to
  // the same list: an unknown one is refused, a known one changes nothing that matters.
  assert.equal(ask({ host: "127.0.0.1:8766", "tailscale-user-login": "someone-else@example.com" }).reason, "login_not_allowed");
  assert.equal(ask({ host: "127.0.0.1:8766", "tailscale-user-login": "someone-else@example.com" }, null).reason, "login_not_allowed");
  assert.equal(ask({ host: "127.0.0.1:8766", "tailscale-user-login": PHONE_LOGIN }).origin, "http://127.0.0.1:8766");
});

test("phone: the tailnet name loads the page and comments as the login's author", async () => {
  const { store, s, repo, cleanup } = await phoneServer({ phone: { authors: { [PHONE_LOGIN]: "omar" } } });
  try {
    const page = await call(s.port, { path: "/", headers: viaTailscale(s.port) });
    assert.equal(page.status, 200);
    const token = tokenOf(page.text);
    const comment = { page: SAMPLE.page, viewport: SAMPLE.viewport, anchor: SAMPLE.anchor, body: "From the phone." };
    const post = (headers) => call(s.port, { method: "POST", path: "/__page-comments/threads", headers: { "content-type": "application/json", "x-page-comments-token": token, ...headers }, body: comment });

    assert.equal((await post(viaTailscale(s.port, { origin: `http://${PHONE_HOST}:${s.port}` }))).status, 403, "the phone's page is https");
    assert.equal((await post(viaTailscale(s.port, { origin: `http://127.0.0.1:${s.port}` }))).status, 403, "a local Origin on the phone Host");
    const made = await post(viaTailscale(s.port, { origin: `https://${PHONE_HOST}:${s.port}` }));
    assert.equal(made.status, 201, made.text);
    assert.equal(made.json.thread.messages[0].author, "omar", "the login's author, not the repo's");
    const list = await call(s.port, { path: "/__page-comments/threads", headers: viaTailscale(s.port, { "x-page-comments-token": token }) });
    assert.equal(list.json.author, "omar");

    // The same server still answers the Mac as before, as the repo's author.
    const local = await post({ origin: `http://127.0.0.1:${s.port}` });
    assert.equal(local.status, 201);
    assert.equal(local.json.thread.messages[0].author, "sam");
    assert.match(readFileSync(join(repo, ".page-comments", ".state", "server.log"), "utf8"), /ev=thread_new .*via=tailscale/);
    assert.equal(readAll(store).length, 2);
  } finally {
    await cleanup();
  }
});

test("phone: no login, a login not on the list, or a forged Host is refused, page loads included", async () => {
  const { store, s, repo, cleanup } = await phoneServer();
  try {
    const page = await call(s.port, { path: "/" });
    const token = tokenOf(page.text);
    const headers = (extra) => ({ origin: `https://${PHONE_HOST}:${s.port}`, "content-type": "application/json", "x-page-comments-token": token, ...extra });
    const post = (extra) => call(s.port, { method: "POST", path: "/__page-comments/threads", headers: headers(extra), body: { anchor: SAMPLE.anchor, page: SAMPLE.page, body: "x" } });

    assert.equal((await call(s.port, { path: "/", headers: { host: `${PHONE_HOST}:${s.port}` } })).status, 403, "page load with no login");
    assert.equal((await call(s.port, { path: "/", headers: viaTailscale(s.port, { "tailscale-user-login": "someone-else@example.com" }) })).status, 403);
    const noLogin = await post({ host: `${PHONE_HOST}:${s.port}` });
    assert.equal(noLogin.status, 403);
    assert.match(noLogin.json.error, /no Tailscale login/);
    assert.equal((await post(viaTailscale(s.port, { "tailscale-user-login": "someone-else@example.com" }))).status, 403);
    assert.equal((await post({ host: `other-mac.tailnet-example.ts.net:${s.port}`, "tailscale-user-login": PHONE_LOGIN })).status, 403, "another tailnet name");
    assert.equal(readAll(store).length, 0);
    const log = readFileSync(join(repo, ".page-comments", ".state", "server.log"), "utf8");
    assert.match(log, /ev=reject reason=no_login/);
    assert.match(log, /ev=reject reason=login_not_allowed .*login=someone-else@example.com/);
  } finally {
    await cleanup();
  }
});

test("phone: the setting is picked up without a restart, and socket upgrades are checked too", async () => {
  const { repo, store, cleanup } = tempRepo();
  const t = await new Promise((r) => {
    const srv = createServer((req, res) => res.end("<body>x</body>"));
    srv.on("upgrade", (req, socket) => socket.end("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n"));
    srv.listen(0, "127.0.0.1", () => r({ srv, port: srv.address().port }));
  });
  const s = await startServer(store, { target: `http://127.0.0.1:${t.port}`, port: 0 });
  const upgrade = (headers) =>
    new Promise((resolve, reject) => {
      const sock = connect(s.port, "127.0.0.1", () => {
        const lines = Object.entries(headers).map(([k, v]) => `${k}: ${v}`);
        sock.write(`GET /live HTTP/1.1\r\n${lines.join("\r\n")}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n\r\n`);
      });
      let buf = "";
      sock.on("data", (d) => (buf += d));
      sock.on("close", () => resolve(buf.split("\r\n")[0]));
      sock.on("error", reject);
      setTimeout(() => sock.end(), 300);
    });
  try {
    assert.equal((await call(s.port, { path: "/", headers: viaTailscale(s.port) })).status, 403, "no phone block yet");
    writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ author: "sam", phone: { host: PHONE_HOST, port: s.port, logins: [PHONE_LOGIN] } }));
    assert.equal((await call(s.port, { path: "/", headers: viaTailscale(s.port) })).status, 200, "picked up while running");
    assert.match(await upgrade(viaTailscale(s.port)), /^HTTP\/1.1 101/);
    assert.match(await upgrade({ host: `${PHONE_HOST}:${s.port}` }), /^HTTP\/1.1 403/);
  } finally {
    await s.close();
    t.srv.close();
    cleanup();
  }
});

// ---- Agents sign with their own names (hub review contract, section 1) -----------------
// Invented names: "sam" is the repo's author, "page-checker" asks, "page-owner" answers.

const AGENTS = { "page-checker": "asks", "page-owner": "answers" };

test("agents: a listed agent signs every write on a local request; no header is the repo's author", async () => {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
  writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ author: "sam", agents: AGENTS }));
  const s = await startServer(store, { root: "site", port: 0 });
  try {
    const token = tokenOf((await call(s.port, { path: "/" })).text);
    const as = (name) => writeHeaders(s.port, token, name ? { "x-page-comments-author": name } : {});
    const post = (path, body, name) => call(s.port, { method: "POST", path: `/__page-comments/${path}`, headers: as(name), body });
    const comment = { page: SAMPLE.page, viewport: SAMPLE.viewport, anchor: SAMPLE.anchor, body: "The walk time is missing." };

    const made = await post("threads", comment, "page-checker");
    assert.equal(made.status, 201, made.text);
    const id = made.json.thread.id;
    assert.equal(made.json.thread.messages[0].author, "page-checker");
    assert.equal(made.json.thread.waiting, "claude", "an asks agent's comment waits on Claude");

    const shot = await post(`threads/${id}/shot`, { error: "the capture failed in a test" }, "page-checker");
    assert.equal(shot.status, 200, shot.text);
    assert.equal(shot.json.thread.shots[0].author, "page-checker");

    const answered = await post(`threads/${id}/replies`, { body: "Should it say minutes?", ask: "sam" }, "page-owner");
    assert.equal(answered.json.thread.messages[1].author, "page-owner");
    assert.equal(answered.json.thread.waiting, "human", "an answers agent's word waits on a person");
    assert.equal(answered.json.thread.asking, "sam");
    assert.equal((await post(`threads/${id}/replies`, { body: "x", ask: "not a name!" }, "page-owner")).status, 400);

    const lost = await post(`threads/${id}/anchor`, { state: "lost" }, "page-checker");
    assert.equal(lost.json.thread.lost, true);
    const closed = await post(`threads/${id}/status`, { status: "resolved" }, "page-owner");
    assert.equal(closed.json.thread.status, "resolved");
    assert.equal(closed.json.thread.asking, null, "a closed thread asks no one");
    const t = readAll(store)[0];
    assert.equal(t.history[0].author, "page-owner");
    assert.equal(t.lostBy, "page", "a found/not found line is the page's, whoever's tab sent it");

    const listed = await call(s.port, { path: "/__page-comments/threads", headers: { "x-page-comments-token": token, "x-page-comments-author": "page-checker" } });
    assert.equal(listed.json.author, "page-checker", "the page shows 'you' for the agent");

    // No header: exactly as before, the repo's author.
    const plain = await post(`threads/${id}/replies`, { body: "Minutes, please." });
    assert.equal(plain.json.thread.messages.at(-1).author, "sam");
    const plainList = await call(s.port, { path: "/__page-comments/threads", headers: { "x-page-comments-token": token } });
    assert.equal(plainList.json.author, "sam");
  } finally {
    await s.close();
    cleanup();
  }
});

test("agents: an unlisted name, the repo's author or claude in the header is refused, never signed as the author", async () => {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
  writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ author: "sam", agents: { ...AGENTS, sam: "asks", claude: "answers" } }));
  const s = await startServer(store, { root: "site", port: 0 });
  try {
    const token = tokenOf((await call(s.port, { path: "/" })).text);
    const comment = { page: SAMPLE.page, anchor: SAMPLE.anchor, body: "x" };
    for (const name of ["page-chekcer", "sam", "Sam", "claude", "", "two words"]) {
      const r = await call(s.port, { method: "POST", path: "/__page-comments/threads", headers: writeHeaders(s.port, token, { "x-page-comments-author": name }), body: comment });
      assert.equal(r.status, 403, `"${name}"`);
      assert.match(r.json.error, /X-Page-Comments-Author|agents|not an agent/, `"${name}"`);
      const get = await call(s.port, { path: "/__page-comments/threads", headers: { "x-page-comments-token": token, "x-page-comments-author": name } });
      assert.equal(get.status, 403, `GET as "${name}"`);
    }
    assert.equal(readAll(store).length, 0, "nothing was written");
    assert.match(readFileSync(join(repo, ".page-comments", ".state", "server.log"), "utf8"), /ev=reject reason=agent_reserved author=sam/);
  } finally {
    await s.close();
    cleanup();
  }
});

test("agents: the header is refused on the phone path, even for a listed agent", async () => {
  const { store, s, repo, cleanup } = await phoneServer();
  try {
    writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ author: "sam", agents: AGENTS, phone: { host: PHONE_HOST, port: s.port, logins: [PHONE_LOGIN] } }));
    const token = tokenOf((await call(s.port, { path: "/", headers: viaTailscale(s.port) })).text);
    const headers = viaTailscale(s.port, { origin: `https://${PHONE_HOST}:${s.port}`, "content-type": "application/json", "x-page-comments-token": token });
    const comment = { page: SAMPLE.page, anchor: SAMPLE.anchor, body: "From the phone." };
    const r = await call(s.port, { method: "POST", path: "/__page-comments/threads", headers: { ...headers, "x-page-comments-author": "page-checker" }, body: comment });
    assert.equal(r.status, 403);
    assert.match(r.json.error, /only from a page on this Mac/);
    // A local Host with a Tailscale login header is not a plain local request either.
    const local = await call(s.port, {
      method: "POST",
      path: "/__page-comments/threads",
      headers: writeHeaders(s.port, token, { "tailscale-user-login": PHONE_LOGIN, "x-page-comments-author": "page-checker" }),
      body: comment,
    });
    assert.equal(local.status, 403);
    assert.equal(readAll(store).length, 0);
    const ok = await call(s.port, { method: "POST", path: "/__page-comments/threads", headers, body: comment });
    assert.equal(ok.status, 201, "the phone without the header works as before");
  } finally {
    await cleanup();
  }
});
