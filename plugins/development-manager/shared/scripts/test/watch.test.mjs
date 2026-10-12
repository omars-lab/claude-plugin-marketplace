import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, rmSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { addReply, appendEvent, createThread, setStatus } from "../lib/store.mjs";
import { diffSnapshots, replayEvents, takeSnapshot } from "../lib/watch.mjs";
import { CLI, SAMPLE, cli, startChild, tempRepo, until } from "./helpers.mjs";

const LINE = /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ pid=\d+ ev=\w+ /;

test("the snapshot diff names each kind of change", () => {
  const { store, cleanup } = tempRepo();
  try {
    const before = takeSnapshot(store);
    const id = createThread(store, SAMPLE);
    const s1 = takeSnapshot(store);
    assert.deepEqual(diffSnapshots(before, s1).map((e) => e.ev), ["thread_new"]);
    addReply(store, id, { author: "claude", body: "Done." });
    setStatus(store, id, { author: "claude", status: "resolved" });
    const s2 = takeSnapshot(store);
    assert.deepEqual(diffSnapshots(s1, s2).map((e) => e.ev), ["message_new", "thread_resolved"]);
    assert.deepEqual(diffSnapshots(s1, s2, { exclude: ["claude"] }), []);
    setStatus(store, id, { author: "sam", status: "open" });
    const s3 = takeSnapshot(store);
    assert.deepEqual(diffSnapshots(s2, s3).map((e) => e.ev), ["thread_reopened"]);
    appendEvent(store, id, { ev: "edit", index: 0, author: "sam", body: "Say how long the walk is, in minutes." });
    assert.deepEqual(diffSnapshots(s3, takeSnapshot(store)).map((e) => e.ev), ["message_edited"]);
  } finally {
    cleanup();
  }
});

test("replay lists only open threads waiting on Claude", () => {
  const { store, cleanup } = tempRepo();
  try {
    const waiting = createThread(store, SAMPLE);
    const answered = createThread(store, SAMPLE);
    addReply(store, answered, { author: "claude", body: "Answered." });
    const closed = createThread(store, SAMPLE);
    setStatus(store, closed, { author: "sam", status: "dismissed" });
    const ev = replayEvents(takeSnapshot(store), { exclude: ["claude"] });
    assert.deepEqual(ev.map((e) => [e.ev, e.thread]), [["thread_open", waiting]]);
  } finally {
    cleanup();
  }
});

test("watch --once --state reports only what changed since the last pass", () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    const state = join(repo, ".page-comments", ".state", "once.json");
    createThread(store, SAMPLE);
    const first = cli(["watch", "--once", "--state", state, "--replay", "--exclude-author", "claude", "--repo", repo]);
    assert.equal(first.code, 0);
    assert.match(first.stdout, /ev=thread_open /);
    assert.equal(cli(["watch", "--once", "--state", state, "--repo", repo]).stdout, "");
    const id = createThread(store, { ...SAMPLE, body: 'Say "45 min" here.\nThanks' });
    const next = cli(["watch", "--once", "--state", state, "--repo", repo]).stdout.trim().split("\n");
    assert.equal(next.length, 1);
    assert.match(next[0], LINE);
    assert.match(next[0], new RegExp(`ev=thread_new page=/trips/sample/ thread=${id} author=sam msg="Say \\\\"45 min\\\\" here. Thanks"$`), "newlines fold to one space, as in review-md");
  } finally {
    cleanup();
  }
});

test("watch keeps running and prints one line per change, never heartbeats", async () => {
  const { repo, store, cleanup } = tempRepo();
  const w = startChild(CLI, ["watch", "--exclude-author", "claude", "--repo", repo, "--interval", "0.2", "--heartbeat", "0.2"]);
  try {
    await until(() => existsSync(join(repo, ".page-comments", ".state", "watch.log")));
    const id = createThread(store, SAMPLE);
    await until(() => w.out().includes("ev=thread_new"));
    addReply(store, id, { author: "claude", body: "On it." });
    addReply(store, id, { author: "sam", body: "Thanks." });
    await until(() => w.out().includes("ev=message_new"));
    await new Promise((r) => setTimeout(r, 500));
    const lines = w.out().trim().split("\n");
    assert.deepEqual(lines.map((l) => l.match(/ev=(\w+)/)[1]), ["thread_new", "message_new"]);
    assert.ok(lines.every((l) => LINE.test(l)));
    const log = readFileSync(join(repo, ".page-comments", ".state", "watch.log"), "utf8");
    assert.match(log, /ev=start /);
    assert.match(log, /ev=heartbeat /);
  } finally {
    await w.stop();
    cleanup();
  }
});

test("watch leaves quietly when the comments folder is removed", async () => {
  const { repo, cleanup } = tempRepo();
  const w = startChild(CLI, ["watch", "--repo", repo, "--interval", "0.2"]);
  try {
    await until(() => existsSync(join(repo, ".page-comments", ".state", "watch.log")));
    rmSync(join(repo, ".page-comments"), { recursive: true, force: true });
    const code = await until(() => w.child.exitCode !== null && { code: w.child.exitCode });
    assert.equal(code.code, 0);
    assert.equal(w.out(), "");
  } finally {
    await w.stop();
    cleanup();
  }
});

test("the monitor's command is silent and writes nothing in a repo without comments", () => {
  const bare = tempRepo({ comments: false });
  const plain = tempRepo({ comments: false, git: false });
  try {
    for (const dir of [bare.repo, plain.repo]) {
      const before = readdirSync(dir).sort();
      // The exact command the plugin monitor runs, from the session's working folder.
      const r = cli(["watch", "--exclude-author", "claude", "--replay"], { cwd: dir });
      assert.equal(r.code, 0);
      assert.equal(r.stdout, "");
      assert.equal(r.stderr, "");
      assert.deepEqual(readdirSync(dir).sort(), before);
    }
  } finally {
    bare.cleanup();
    plain.cleanup();
  }
});

test("wait reports what is already waiting first, then blocks for the next change", async () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    const first = cli(["wait", "--repo", repo]);
    assert.match(first.stdout, new RegExp(`ev=thread_open .*thread=${id}`));
    const w = startChild(CLI, ["wait", "--repo", repo, "--interval", "0.2"]);
    try {
      await new Promise((r) => setTimeout(r, 400));
      assert.equal(w.child.exitCode, null, "nothing new yet, so wait keeps waiting");
      addReply(store, id, { author: "claude", body: "Mine, so it does not count." });
      await new Promise((r) => setTimeout(r, 600));
      assert.equal(w.child.exitCode, null);
      addReply(store, id, { author: "sam", body: "One more thing." });
      await until(() => w.child.exitCode !== null);
      assert.match(w.out(), /ev=message_new .*author=sam/);
    } finally {
      await w.stop();
    }
    const quiet = cli(["wait", "--repo", repo, "--timeout", "0.3"]);
    assert.equal(quiet.code, 0);
    assert.equal(quiet.stdout, "");
  } finally {
    cleanup();
  }
});
