// Which page a comment belongs to, for apps that switch screens by the hash
// (`/#/topic/a`): each route is its own page, a plain `#section` is not, and
// comments saved before routes counted (path "/") are read as on their route,
// from the url they kept, without rewriting their files. Also: the page's
// found / not found lines are signed "page". All data here is invented.

import { test } from "node:test";
import assert from "node:assert/strict";
import { request } from "node:http";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import { agentsSetting, cleanPage, createThread, pagePathOf, readAll, readEvents, readThread, routeOf, threadFile } from "../lib/store.mjs";
import { diffSnapshots, takeSnapshot } from "../lib/watch.mjs";
import { startServer } from "../lib/server.mjs";
import { SAMPLE, SCRIPTS, cli, tempRepo } from "./helpers.mjs";

/** The client's own copy of the rule, taken out of comments.js and run alone. */
function clientRouteOf() {
  const src = readFileSync(join(SCRIPTS, "client", "comments.js"), "utf8");
  const fn = /function routeOf\(hash\) \{[\s\S]*?\n {2}\}/.exec(src);
  assert.ok(fn, "comments.js has a routeOf function");
  const ctx = {};
  runInNewContext(`${fn[0]}; this.routeOf = routeOf;`, ctx);
  return ctx.routeOf;
}

const RULE = [
  ["#/topic/a", "#/topic/a"],
  ["#!/inbox", "#!/inbox"],
  ["#/topic/a?tab=2", "#/topic/a?tab=2"],
  ["#/", ""], // the app's first screen: the same page as no hash
  ["#!/", ""],
  ["#section-2", ""], // a jump target on one page, not a screen
  ["#", ""],
  ["", ""],
  [undefined, ""],
];

test("the hash is a screen only when it starts with #/ or #!/; the server and the page agree", () => {
  const client = clientRouteOf();
  for (const [hash, want] of RULE) {
    assert.equal(routeOf(hash), want, `server: ${hash}`);
    assert.equal(client(hash), want, `page: ${hash}`);
  }
});

const HUB = "http://127.0.0.1:8766";
const page = (url, path, title = "Sample app") => ({ url, path, title });

test("a comment's page: the route is kept; older comments get theirs from the url they saved", () => {
  // New comments: the page sends the route in the path.
  assert.equal(pagePathOf(page(`${HUB}/#/topic/a`, "/#/topic/a")), "/#/topic/a");
  // Saved before routes counted: path "/", the route only in the url.
  assert.equal(pagePathOf(page(`${HUB}/#/topic/a`, "/")), "/#/topic/a");
  assert.equal(pagePathOf(page(`${HUB}/app/#!/inbox`, "/app/")), "/app/#!/inbox");
  // Not a route: the page alone.
  assert.equal(pagePathOf(page(`${HUB}/trips/#day-2`, "/trips/")), "/trips/");
  assert.equal(pagePathOf(page(`${HUB}/#/`, "/")), "/");
  assert.equal(pagePathOf(page(`${HUB}/trips/?day=2`, "/trips/")), "/trips/");
  // A url that does not parse, or none at all, leaves the path as it was.
  assert.equal(pagePathOf(page("not a url #/x", "/x/")), "/x/");
  assert.equal(pagePathOf({ path: "/x/" }), "/x/");
  assert.equal(pagePathOf(null), "/");
  // What the server stores: a page that sends only its path still lands on its route.
  assert.deepEqual(cleanPage(page(`${HUB}/#/topic/a`, "/")), page(`${HUB}/#/topic/a`, "/#/topic/a"));
});

/** Three screens of one hash-routed app, one ordinary page with #anchors, and an old comment. */
function seed(store) {
  const at = (url, path, body) => createThread(store, { ...SAMPLE, page: page(url, path), body });
  return {
    a: at(`${HUB}/#/topic/a`, "/#/topic/a", "On screen a."),
    b: at(`${HUB}/#/topic/b`, "/#/topic/b", "On screen b."),
    home: at(`${HUB}/`, "/", "On the first screen."),
    homeHash: at(`${HUB}/#/`, "/", "Also on the first screen."),
    trips: at(`${HUB}/trips/#day-2`, "/trips/", "On the trips page, scrolled to day 2."),
    // Saved by an older page script: every screen filed under "/".
    oldA: at(`${HUB}/#/topic/a`, "/", "On screen a, from before routes counted."),
  };
}

test("an old comment's file is never rewritten; it is read as on its route", () => {
  const { store, cleanup } = tempRepo();
  try {
    const ids = seed(store);
    const before = readFileSync(threadFile(store, ids.oldA), "utf8");
    assert.equal(JSON.parse(before).page.path, "/", "the file says /");
    assert.equal(readThread(store, ids.oldA).page.path, "/#/topic/a");
    assert.equal(readThread(store, ids.oldA).page.url, `${HUB}/#/topic/a`, "the url is as saved");
    assert.equal(readFileSync(threadFile(store, ids.oldA), "utf8"), before, "reading changed nothing");
  } finally {
    cleanup();
  }
});

/** One raw HTTP call. */
function call(port, { method = "GET", path = "/", headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const req = request({ host: "127.0.0.1", port, method, path, headers }, (res) => {
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

async function server(config) {
  const r = tempRepo();
  mkdirSync(join(r.repo, "site"));
  writeFileSync(join(r.repo, "site", "index.html"), "<body>x</body>");
  if (config) writeFileSync(join(r.repo, ".page-comments", "config.json"), JSON.stringify(config));
  const s = await startServer(r.store, { root: "site", port: 0 });
  const token = /data-token="([0-9a-f]+)"/.exec((await call(s.port, { path: "/" })).text)[1];
  const get = (p) => call(s.port, { path: `/__page-comments/threads?page=${encodeURIComponent(p)}`, headers: { "x-page-comments-token": token } });
  const post = (path, body, extra = {}) =>
    call(s.port, { method: "POST", path: `/__page-comments/${path}`, headers: { origin: `http://127.0.0.1:${s.port}`, "content-type": "application/json", "x-page-comments-token": token, ...extra }, body });
  return { ...r, s, get, post };
}

test("the page asks for its own screen's comments, and gets only those", async () => {
  const { store, s, get, post, cleanup } = await server();
  try {
    const ids = seed(store);
    const idsOn = async (p) => (await get(p)).json.threads.map((t) => t.id).sort();
    assert.deepEqual(await idsOn("/#/topic/a"), [ids.a, ids.oldA].sort(), "screen a: its own comment, and the old one made there");
    assert.deepEqual(await idsOn("/#/topic/b"), [ids.b]);
    assert.deepEqual(await idsOn("/"), [ids.home, ids.homeHash].sort(), "the first screen: no other screen's comments");
    assert.deepEqual(await idsOn("/trips/"), [ids.trips], "#day-2 did not make a page of its own");
    // A new comment on a screen is filed under that screen.
    const made = await post("threads", { page: page(`${HUB}/#/topic/b`, "/#/topic/b"), anchor: SAMPLE.anchor, body: "Another on b." });
    assert.equal(made.status, 201, made.text);
    assert.equal(made.json.thread.page.path, "/#/topic/b");
    assert.equal(JSON.parse(readFileSync(threadFile(store, made.json.thread.id), "utf8")).page.path, "/#/topic/b", "stored with its route");
    assert.ok((await idsOn("/#/topic/b")).includes(made.json.thread.id));
    assert.ok(!(await idsOn("/")).includes(made.json.thread.id));
    assert.ok(!(await idsOn("/#/topic/a")).includes(made.json.thread.id));
  } finally {
    await s.close();
    cleanup();
  }
});

test("list, stats and the watcher name the same page the page asks for", () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    const ids = seed(store);
    const one = cli(["list", "--json", "--page", "/#/topic/a", "--repo", repo]);
    assert.equal(one.code, 0, one.stderr);
    assert.deepEqual(JSON.parse(one.stdout).threads.map((t) => t.id).sort(), [ids.a, ids.oldA].sort());
    const all = JSON.parse(cli(["list", "--json", "--repo", repo]).stdout);
    assert.deepEqual(all.files.map((f) => f.file), ["/", "/#/topic/a", "/#/topic/b", "/trips/"]);
    const text = cli(["list", "--repo", repo]).stdout;
    assert.match(text, /^\/#\/topic\/a\n {2}t_/m, "the text list groups by screen too");
    const stats = JSON.parse(cli(["stats", "--json", "--repo", repo]).stdout);
    assert.deepEqual(
      stats.pages.map((p) => [p.page, p.open]),
      [
        ["/", 2],
        ["/#/topic/a", 2],
        ["/#/topic/b", 1],
        ["/trips/", 1],
      ],
    );
    const shown = JSON.parse(cli(["show", ids.oldA, "--json", "--repo", repo]).stdout);
    assert.equal(shown.page.path, "/#/topic/a");
    const events = diffSnapshots({}, takeSnapshot(store)).filter((e) => e.ev === "thread_new");
    assert.equal(events.find((e) => e.thread === ids.oldA).page, "/#/topic/a", "the watcher prints page=/#/topic/a");
  } finally {
    cleanup();
  }
});

test("found / not found lines are signed 'page', from the repo's author's tab or an agent's", async () => {
  const { store, s, post, cleanup } = await server({ author: "sam", agents: { "page-checker": "asks", page: "answers" } });
  try {
    const made = await post("threads", { page: page(`${HUB}/#/topic/a`, "/#/topic/a"), anchor: SAMPLE.anchor, body: "From an agent." }, { "x-page-comments-author": "page-checker" });
    assert.equal(made.status, 201, made.text);
    const id = made.json.thread.id;
    assert.equal((await post(`threads/${id}/anchor`, { state: "lost" })).status, 200);
    assert.equal((await post(`threads/${id}/anchor`, { state: "found" }, { "x-page-comments-author": "page-checker" })).status, 200);
    const lines = readEvents(store, id).events.filter((e) => e.ev === "anchor");
    assert.deepEqual(
      lines.map((e) => [e.author, e.state]),
      [
        ["page", "lost"],
        ["page", "found"],
      ],
    );
    // The watcher says the page reported it, not sam or the agent.
    const before = takeSnapshot(store);
    assert.equal((await post(`threads/${id}/anchor`, { state: "lost" })).status, 200);
    const lost = diffSnapshots(before, takeSnapshot(store)).find((e) => e.ev === "anchor_lost");
    assert.equal(lost.author, "page");
    assert.equal(readAll(store)[0].messages[0].author, "page-checker", "the comment itself keeps its agent's name");
    // Nobody may sign as "page": it is not an agent, even when config.json lists it.
    assert.deepEqual(agentsSetting({ author: "sam", agents: { page: "answers", "page-checker": "asks" } }), { "page-checker": "asks" });
    const refused = await post("threads", { page: page(`${HUB}/`, "/"), anchor: SAMPLE.anchor, body: "x" }, { "x-page-comments-author": "page" });
    assert.equal(refused.status, 403);
  } finally {
    await s.close();
    cleanup();
  }
});
