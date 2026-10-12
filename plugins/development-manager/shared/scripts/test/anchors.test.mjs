// Phase 4: finding comments again after the page changed. The text matcher,
// the page's found/not found reports, the watcher's `ev=anchor_lost`, the
// post-commit hook that notes which commit landed a comment's work, and the
// session-start notice. All data here is invented.

import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { request } from "node:http";
import { join } from "node:path";
import { runInNewContext } from "node:vm";
import { appendEvent, createThread, readEvents, readThread, setAnchorState, addLanded, publicThread } from "../lib/store.mjs";
import { diffSnapshots, replayEvents, takeSnapshot } from "../lib/watch.mjs";
import { startServer } from "../lib/server.mjs";
import { restamp } from "../lib/restamp.mjs";
import { ENABLE, PLUGIN, SAMPLE, SCRIPTS, cli, tempRepo } from "./helpers.mjs";

// ---- The text matcher ------------------------------------------------------------------

function matcher() {
  const ctx = {};
  runInNewContext(readFileSync(join(SCRIPTS, "client", "text-match.js"), "utf8"), { globalThis: ctx });
  const m = ctx.__pageCommentsMatch;
  return { ...m, findQuote: (text, q) => JSON.parse(JSON.stringify(m.findQuote(text, q))) };
}

const PAGE =
  "Day 1. Fly into the valley and check in at the lodge by four. " +
  "Day 2. Walk the long trail to the falls, then picnic by the river before the shuttle back. " +
  "Day 3. Drive the coast road south and stop at the lighthouse for sunset.";
const QUOTE = { exact: "Walk the long trail to the falls", prefix: "check in at the lodge by four. Day 2. ", suffix: ", then picnic by the river" };

test("the matcher finds the exact words, with their place in the page's own text", () => {
  const { findQuote } = matcher();
  const r = findQuote(PAGE, QUOTE);
  assert.equal(r.rival, null);
  assert.equal(r.match.sim, 1);
  assert.equal(PAGE.slice(r.match.start, r.match.end), QUOTE.exact);
  // Line breaks and runs of spaces in the page count as one space.
  const spaced = PAGE.replace("the long trail", "the  long\n   trail");
  const s = findQuote(spaced, QUOTE);
  assert.equal(s.match.sim, 1);
  assert.equal(spaced.slice(s.match.start, s.match.end), "Walk the  long\n   trail to the falls");
});

test("the matcher finds lightly edited words at 80% or more, and nothing below", () => {
  const { findQuote, similarity, THRESHOLD } = matcher();
  assert.equal(THRESHOLD, 0.8);
  const light = PAGE.replace("Walk the long trail to the falls", "Walk the long trail to the big falls");
  const r = findQuote(light, QUOTE);
  assert.ok(r && r.match.sim >= 0.8 && r.match.sim < 1, JSON.stringify(r));
  assert.match(light.slice(r.match.start, r.match.end), /long trail to the big falls/);
  const heavy = PAGE.replace("Walk the long trail to the falls", "Hike a short loop near the falls");
  assert.equal(findQuote(heavy, QUOTE), null, "too different: not found, never a guess");
  const gone = PAGE.replace("Walk the long trail to the falls, then picnic by the river before the shuttle back. ", "");
  assert.equal(findQuote(gone, QUOTE), null, "deleted: not found");
  assert.equal(similarity("Day 2: museum and park", "Day 2: museum and park"), 1);
  assert.ok(similarity("Day 2: museum and park", "Day 2: museum and the park") >= 0.8);
  assert.ok(similarity("Day 2: museum and park", "Day 3: coast road") < 0.8);
});

test("two places too close to call come back as a rival; the stored context settles it", () => {
  const { findQuote } = matcher();
  const twice = "Cards: Book the table early for dinner. More cards: Book the table early for dinner. End.";
  const bare = findQuote(twice, { exact: "Book the table early for lunch" });
  assert.ok(bare.match && bare.rival, "no context: a tie, which the page treats as not found");
  const withContext = findQuote(twice, { exact: "Book the table early for lunch", prefix: "More cards: ", suffix: ". End." });
  assert.equal(withContext.rival, null);
  assert.ok(withContext.match.start > twice.indexOf("More cards"));
});

test("the matcher is quick on a long page", () => {
  const { findQuote } = matcher();
  const long = (PAGE + " ").repeat(600) + "A one-off line about the ferry timetable near the end.";
  const t0 = Date.now();
  const r = findQuote(long, { exact: "A one-off line about the ferry timetables near the end" });
  assert.ok(r && r.match.sim >= 0.8);
  assert.ok(Date.now() - t0 < 1000, `took ${Date.now() - t0} ms on ${long.length} characters`);
});

// ---- The thread file: found/not found reports, and the landed commit ---------------------

test("anchor reports and the landed commit fold into the thread shape", () => {
  const { store, cleanup } = tempRepo();
  try {
    const id = createThread(store, { ...SAMPLE, rev: { ...SAMPLE.rev, git: { commit: "abc1234", dirty: true } } });
    assert.equal(publicThread(readThread(store, id)).lost, undefined, "found is the default and is left out");
    setAnchorState(store, id, { author: "sam", state: "lost" });
    assert.equal(publicThread(readThread(store, id)).lost, true);
    setAnchorState(store, id, { author: "sam", state: "found" });
    assert.equal(publicThread(readThread(store, id)).lost, undefined);
    assert.throws(() => setAnchorState(store, id, { author: "sam", state: "maybe" }));
    appendEvent(store, id, { ev: "anchor", author: "sam", state: "maybe" });
    assert.equal(readThread(store, id).lost, false, "an unknown state is ignored");

    addLanded(store, id, { commit: "def5678", from: "abc1234" });
    addLanded(store, id, { commit: "0000000", from: "abc1234" });
    const t = publicThread(readThread(store, id));
    assert.equal(t.rev.landed.commit, "def5678", "the first landed commit wins");
    assert.deepEqual(t.rev.git, { commit: "abc1234", dirty: true }, "where the comment was made is kept");
    assert.equal("events" in t, false, "the event count is not part of the shared shape");
  } finally {
    cleanup();
  }
});

// ---- The server: POST threads/<id>/anchor ---------------------------------------------------

function call(port, { method = "GET", path = "/", headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const req = request({ host: "127.0.0.1", port, method, path, headers: { host: `127.0.0.1:${port}`, ...headers }, setHost: false }, (res) => {
      let text = "";
      res.on("data", (c) => (text += c));
      res.on("end", () => {
        let json = null;
        try {
          json = JSON.parse(text);
        } catch {}
        resolve({ status: res.statusCode, text, json });
      });
    });
    req.on("error", reject);
    if (body !== undefined) req.write(JSON.stringify(body));
    req.end();
  });
}

test("the server records a found/not found report only when it changes something", async () => {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
  const s = await startServer(store, { root: "site", port: 0 });
  try {
    const id = createThread(store, SAMPLE);
    const token = /data-token="([0-9a-f]+)"/.exec((await call(s.port, { path: "/" })).text)[1];
    const headers = { origin: `http://127.0.0.1:${s.port}`, "content-type": "application/json", "x-page-comments-token": token };
    const list = () => call(s.port, { path: "/__page-comments/threads", headers: { "x-page-comments-token": token } });
    const v0 = (await list()).json.version;
    const post = (state) => call(s.port, { method: "POST", path: `/__page-comments/threads/${id}/anchor`, headers, body: { state } });

    const client = await call(s.port, { path: "/__page-comments/client.js" });
    assert.equal(client.status, 200);
    assert.ok(client.text.indexOf("__pageCommentsMatch = {") < client.text.indexOf("var MATCH = window.__pageCommentsMatch"), "the matcher is served ahead of the comment bar");

    assert.equal((await post("gone")).status, 400);
    const first = await post("lost");
    assert.equal(first.status, 200);
    assert.equal(first.json.thread.lost, true);
    for (let i = 0; i < 4; i++) assert.equal((await post("lost")).json.changed, false, "a repeat (another tab, a reload) adds nothing");
    assert.equal(readEvents(store, id).events.filter((e) => e.ev === "anchor").length, 1, "exactly one line in the thread file");
    const v1 = (await list()).json.version;
    assert.notEqual(v1, v0, "the page's next poll sees the change");
    await post("found");
    assert.equal(readThread(store, id).lost, false);
    const noToken = await call(s.port, { method: "POST", path: `/__page-comments/threads/${id}/anchor`, headers: { ...headers, "x-page-comments-token": "0".repeat(32) }, body: { state: "lost" } });
    assert.equal(noToken.status, 403);
  } finally {
    await s.close();
    cleanup();
  }
});

// ---- The watcher: ev=anchor_lost ----------------------------------------------------------

test("the watcher prints anchor_lost once, for open threads only", () => {
  const { store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    const s0 = takeSnapshot(store);
    setAnchorState(store, id, { author: "sam", state: "lost" });
    const s1 = takeSnapshot(store);
    assert.deepEqual(diffSnapshots(s0, s1).map((e) => [e.ev, e.thread, e.author]), [["anchor_lost", id, "sam"]]);
    assert.deepEqual(diffSnapshots(s1, takeSnapshot(store)), [], "nothing new, nothing printed");
    // A thread that arrives already lost (merged in from a branch).
    const late = createThread(store, SAMPLE);
    setAnchorState(store, late, { author: "sam", state: "lost" });
    assert.deepEqual(diffSnapshots(s1, takeSnapshot(store)).map((e) => e.ev), ["thread_new", "anchor_lost"]);
    assert.ok(replayEvents(takeSnapshot(store), { exclude: ["claude"] }).some((e) => e.ev === "anchor_lost" && e.thread === id));
    const st = join(store.dir, ".state", "w.json");
    cli(["watch", "--once", "--state", st, "--repo", store.repo]);
    setAnchorState(store, id, { author: "sam", state: "found" });
    setAnchorState(store, id, { author: "sam", state: "lost" });
    const again = cli(["watch", "--once", "--state", st, "--repo", store.repo]);
    assert.doesNotMatch(again.stdout, /anchor_lost/, "found then lost again between two looks: still lost, nothing new");
  } finally {
    cleanup();
  }
});

// ---- The post-commit hook: restamp ----------------------------------------------------------

function git(repo, ...args) {
  return execFileSync("git", ["-C", repo, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
}

/** A repo whose commits run its own .git/hooks, without this machine's template hooks. */
function commitRepo() {
  const r = tempRepo();
  rmSync(join(r.repo, ".git", "hooks"), { recursive: true, force: true });
  mkdirSync(join(r.repo, ".git", "hooks"));
  writeFileSync(join(r.repo, "page.html"), "<h1>Day 2</h1>\n");
  git(r.repo, "add", "page.html");
  git(r.repo, "commit", "-q", "-m", "page");
  return r;
}

test("restamp notes the commit that landed a comment's uncommitted work, once", () => {
  const { repo, store, cleanup } = commitRepo();
  try {
    const base = git(repo, "rev-parse", "--short", "HEAD");
    const dirty = createThread(store, { ...SAMPLE, rev: { ...SAMPLE.rev, git: { commit: base, dirty: true } } });
    const clean = createThread(store, { ...SAMPLE, rev: { ...SAMPLE.rev, git: { commit: base, dirty: false } } });
    const older = createThread(store, { ...SAMPLE, rev: { ...SAMPLE.rev, git: { commit: "abc1234", dirty: true } } });

    // A commit of only the comments themselves lands no work.
    git(repo, "add", ".page-comments");
    git(repo, "commit", "-q", "-m", "comments");
    assert.match(restamp(store).skipped, /only changes \.page-comments/);
    git(repo, "reset", "-q", "--soft", "HEAD~1");

    writeFileSync(join(repo, "page.html"), "<h1>Day 2: the falls</h1>\n");
    git(repo, "add", "page.html");
    git(repo, "commit", "-q", "-m", "work");
    const head = git(repo, "rev-parse", "--short", "HEAD");
    const r = restamp(store);
    assert.deepEqual(r.landed.map((x) => x.id), [dirty]);
    assert.equal(readThread(store, dirty).rev.landed.commit, head);
    assert.equal(readThread(store, dirty).rev.git.commit, base, "never rewritten");
    assert.equal(readThread(store, clean).rev.landed, undefined, "made on committed work: nothing to land");
    assert.equal(readThread(store, older).rev.landed, undefined, "made on another commit: not this one's work");
    assert.deepEqual(restamp(store).landed, [], "a second run adds nothing");
    assert.equal(git(repo, "rev-parse", "--short", "HEAD"), head, "the commit is not amended");

    const cmd = cli(["restamp", "--repo", repo]);
    assert.equal(cmd.code, 0);
    assert.equal(cmd.stdout, "", "silent when there is nothing to do");
    assert.equal(cli(["restamp"], { cwd: tempRepo({ comments: false }).repo }).stdout, "", "silent in a repo without comments");
  } finally {
    cleanup();
  }
});

test("restamp skips merge commits and a rebase in progress", () => {
  const { repo, store, cleanup } = commitRepo();
  try {
    const base = git(repo, "rev-parse", "--short", "HEAD");
    const id = createThread(store, { ...SAMPLE, rev: { ...SAMPLE.rev, git: { commit: base, dirty: true } } });
    // A real merge commit.
    git(repo, "switch", "-q", "-c", "side");
    writeFileSync(join(repo, "side.html"), "<p>side</p>\n");
    git(repo, "add", "side.html");
    git(repo, "commit", "-q", "-m", "side");
    git(repo, "switch", "-q", "-");
    writeFileSync(join(repo, "page.html"), "<h1>Day 2 on main</h1>\n");
    git(repo, "add", "page.html");
    git(repo, "commit", "-q", "-m", "main");
    git(repo, "merge", "-q", "--no-ff", "--no-edit", "side");
    assert.equal(restamp(store).skipped, "a merge commit");
    // In the middle of a merge or a rebase.
    writeFileSync(join(repo, ".git", "MERGE_HEAD"), git(repo, "rev-parse", "HEAD") + "\n");
    assert.match(restamp(store).skipped, /merge is in progress/);
    rmSync(join(repo, ".git", "MERGE_HEAD"));
    mkdirSync(join(repo, ".git", "rebase-merge"));
    assert.match(restamp(store).skipped, /rebase-merge is in progress/);
    rmSync(join(repo, ".git", "rebase-merge"), { recursive: true });
    assert.equal(readThread(store, id).rev.landed, undefined);
  } finally {
    cleanup();
  }
});

// ---- enable: installing the hook, chaining, core.hooksPath, undo ----------------------------

function enable(args, repo) {
  const r = spawnSync(process.execPath, [ENABLE, ...args, "--repo", repo], { encoding: "utf8", timeout: 60000, env: { ...process.env, PAGE_COMMENTS_SKIP_CLAUDE: "1" } });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr };
}

const OLD_HOOK = '#!/bin/sh\n# an earlier post-commit hook\necho "earlier hook ran with $# args" >> "$(git rev-parse --show-toplevel)/.git/earlier.log"\n';

test("enable chains the post-commit hook already there, and a real commit runs both", () => {
  const { repo, cleanup } = commitRepo();
  try {
    mkdirSync(join(repo, "site"));
    writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
    const hook = join(repo, ".git", "hooks", "post-commit");
    writeFileSync(hook, OLD_HOOK);
    chmodSync(hook, 0o750);
    const r = enable(["--root", "site"], repo);
    assert.equal(r.code, 0, r.stderr);
    assert.match(r.stdout, /post-commit hook already there still runs first/);
    assert.match(readFileSync(hook, "utf8"), /page-comments:post-commit/);
    assert.equal(readFileSync(join(repo, ".git", "hooks", "post-commit.page-comments-prev"), "utf8"), OLD_HOOK);
    const install = JSON.parse(readFileSync(join(repo, ".page-comments", "install.json"), "utf8"));
    const c = install.changes.find((x) => x.kind === "post-commit-hook");
    assert.deepEqual({ ...c }, { kind: "post-commit-hook", file: ".git/hooks/post-commit", prev: ".git/hooks/post-commit.page-comments-prev", hadPrevious: true, prevMode: 0o750 });
    assert.doesNotMatch(JSON.stringify(install), /\/Users\/|\/home\//, "no machine paths in install.json");

    // Run twice: still one hook, the earlier one still kept.
    assert.equal(enable(["--root", "site"], repo).code, 0);
    assert.equal(readFileSync(join(repo, ".git", "hooks", "post-commit.page-comments-prev"), "utf8"), OLD_HOOK);

    // A comment made on uncommitted work, then a real commit.
    const store = { repo, dir: join(repo, ".page-comments") };
    writeFileSync(join(repo, "page.html"), "<h1>Day 2, edited</h1>\n");
    const base = git(repo, "rev-parse", "--short", "HEAD");
    const id = createThread(store, { ...SAMPLE, rev: { ...SAMPLE.rev, git: { commit: base, dirty: true } } });
    git(repo, "add", "page.html");
    // git sends a hook's output to stderr.
    const done = spawnSync("git", ["-C", repo, "commit", "-m", "edit the page"], { encoding: "utf8" });
    assert.equal(done.status, 0, done.stderr);
    assert.match(done.stderr, /page-comments: 1 comment made on uncommitted work now points at commit [0-9a-f]{7,}\./);
    assert.equal(readThread(store, id).rev.landed.commit, git(repo, "rev-parse", "--short", "HEAD"));
    assert.equal(readFileSync(join(repo, ".git", "earlier.log"), "utf8"), "earlier hook ran with 0 args\n");

    const u = enable(["--undo"], repo);
    assert.equal(u.code, 0, u.stderr);
    assert.match(u.stdout, /put back the post-commit hook that was there before/);
    assert.equal(readFileSync(hook, "utf8"), OLD_HOOK, "byte for byte");
    assert.equal(statSync(hook).mode & 0o7777, 0o750, "and its mode");
    assert.equal(existsSync(join(repo, ".git", "hooks", "post-commit.page-comments-prev")), false);
  } finally {
    cleanup();
  }
});

test("enable follows core.hooksPath, skips hooks it must not touch, and undo leaves no hook", () => {
  const { repo, cleanup } = commitRepo();
  try {
    mkdirSync(join(repo, "site"));
    writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");

    // An ignored hooks folder in the work tree: the hook goes there, not in .git/hooks.
    writeFileSync(join(repo, ".gitignore"), "local-hooks/\n");
    mkdirSync(join(repo, "local-hooks"));
    git(repo, "config", "core.hooksPath", "local-hooks");
    assert.equal(enable(["--root", "site"], repo).code, 0);
    assert.ok(existsSync(join(repo, "local-hooks", "post-commit")));
    assert.equal(existsSync(join(repo, ".git", "hooks", "post-commit")), false);
    assert.equal(enable(["--undo"], repo).code, 0);
    assert.equal(existsSync(join(repo, "local-hooks", "post-commit")), false, "no hook was there before, so none after");

    // A committed hooks folder: adding a file there would show up in git, so skip it.
    mkdirSync(join(repo, ".githooks"));
    writeFileSync(join(repo, ".githooks", "pre-commit"), "#!/bin/sh\nexit 0\n");
    git(repo, "add", ".githooks/pre-commit", ".gitignore");
    git(repo, "commit", "-q", "-m", "team hooks");
    git(repo, "config", "core.hooksPath", ".githooks");
    const r = enable(["--root", "site"], repo);
    assert.equal(r.code, 0, r.stderr);
    assert.match(r.stdout, /no post-commit hook: core\.hooksPath points at \.githooks\//);
    assert.equal(existsSync(join(repo, ".githooks", "post-commit")), false);
    assert.equal(git(repo, "status", "--porcelain", "--", ".githooks"), "");
    assert.equal(enable(["--undo"], repo).code, 0);

    // Hooks turned off.
    git(repo, "config", "core.hooksPath", "/dev/null");
    assert.match(enable(["--root", "site"], repo).stdout, /git hooks are turned off here/);
    assert.equal(enable(["--undo"], repo).code, 0);
  } finally {
    cleanup();
  }
});

test("undo without install.json still finds the hook by its marker", () => {
  const { repo, cleanup } = commitRepo();
  try {
    mkdirSync(join(repo, "site"));
    writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
    const hook = join(repo, ".git", "hooks", "post-commit");
    writeFileSync(hook, OLD_HOOK);
    chmodSync(hook, 0o755);
    assert.equal(enable(["--root", "site"], repo).code, 0);
    rmSync(join(repo, ".page-comments", "install.json"));
    const u = enable(["--undo"], repo);
    assert.equal(u.code, 0, u.stderr);
    assert.equal(readFileSync(hook, "utf8"), OLD_HOOK);
  } finally {
    cleanup();
  }
});

// ---- The session-start notice ------------------------------------------------------------

const SESSION = join(PLUGIN, "hooks", "session-start.sh");

function session(cwd) {
  const t0 = process.hrtime.bigint();
  const r = spawnSync("sh", [SESSION], { cwd, encoding: "utf8", timeout: 10000, env: { ...process.env, CLAUDE_PROJECT_DIR: "" } });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr, ms: Number(process.hrtime.bigint() - t0) / 1e6 };
}

test("the session-start notice counts threads waiting on Claude, and is silent elsewhere", () => {
  const hooks = JSON.parse(readFileSync(join(PLUGIN, "hooks", "hooks.json"), "utf8"));
  const start = hooks.hooks.SessionStart[0];
  assert.equal(start.matcher, "startup|resume");
  assert.match(start.hooks[0].command, /session-start\.sh/);

  const none = tempRepo({ comments: false });
  const empty = tempRepo();
  const busy = tempRepo();
  try {
    const plain = session(none.repo);
    assert.deepEqual([plain.code, plain.stdout, plain.stderr], [0, "", ""]);
    assert.ok(plain.ms < 500, `${plain.ms} ms in a repo without comments`);
    assert.equal(session(empty.repo).stdout, "", "comments on, nothing waiting");

    createThread(busy.store, SAMPLE);
    const lost = createThread(busy.store, SAMPLE);
    setAnchorState(busy.store, lost, { author: "sam", state: "lost" });
    const answered = createThread(busy.store, SAMPLE);
    appendEvent(busy.store, answered, { ev: "reply", author: "claude", body: "Done." });
    mkdirSync(join(busy.repo, "src", "deep"), { recursive: true });
    const r = session(join(busy.repo, "src", "deep"));
    assert.equal(r.code, 0, r.stderr);
    assert.equal(
      r.stdout,
      "Page comments: 2 comment threads are waiting on Claude in this repo (1 not found on its page). List them with: .page-comments/run list --open --waiting claude\n",
    );
    assert.equal(cli(["notice", "--repo", none.repo]).stdout, "");
  } finally {
    none.cleanup();
    empty.cleanup();
    busy.cleanup();
  }
});
