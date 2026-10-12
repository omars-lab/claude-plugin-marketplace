import { test } from "node:test";
import assert from "node:assert/strict";
import { appendFileSync, readFileSync, writeFileSync } from "node:fs";
import { addReply, createThread, foldThread, publicThread, readAll, readThread, setStatus, threadFile, cleanAnchor, cleanBody } from "../lib/store.mjs";
import { findStore } from "../lib/repo.mjs";
import { SAMPLE, tempRepo } from "./helpers.mjs";

test("a new thread is one line, read back in the shared shape", () => {
  const { store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    assert.match(id, /^t_[0-9a-f]{6}$/);
    const lines = readFileSync(threadFile(store, id), "utf8").trim().split("\n");
    assert.equal(lines.length, 1);
    const first = JSON.parse(lines[0]);
    assert.equal(first.v, 1);
    assert.equal(first.ev, "thread");
    const t = publicThread(readThread(store, id));
    assert.deepEqual(Object.keys(t).sort(), ["anchor", "id", "messages", "page", "resolved", "rev", "status", "viewport", "waiting"]);
    assert.equal(t.status, "open");
    assert.equal(t.resolved, false);
    assert.equal(t.waiting, "claude");
    assert.equal(t.anchor.type, "element");
    assert.equal(t.rev.bodyHash, "a41c09e2b7d3");
    assert.deepEqual(t.messages.map((m) => m.author), ["sam"]);
  } finally {
    cleanup();
  }
});

test("replies and status changes fold in order", () => {
  const { store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    addReply(store, id, { author: "claude", body: "Added the walk time.", commit: "9c41d0e" });
    let t = readThread(store, id);
    assert.equal(t.waiting, "human");
    assert.equal(t.messages[1].commit, "9c41d0e");
    setStatus(store, id, { author: "claude", status: "resolved", note: "fixed" });
    t = readThread(store, id);
    assert.equal(t.status, "resolved");
    assert.equal(t.resolved, true);
    assert.equal(t.waiting, null);
    assert.equal(t.history[0].note, "fixed");
    setStatus(store, id, { author: "sam", status: "open" });
    t = readThread(store, id);
    assert.equal(t.status, "open");
    assert.equal(t.waiting, "human", "reopening alone does not make it Claude's turn: the last message is still Claude's");
    addReply(store, id, { author: "sam", body: "Still missing on day 3." });
    assert.equal(readThread(store, id).waiting, "claude");
  } finally {
    cleanup();
  }
});

test("a half-written last line is skipped, then read once it is whole", () => {
  const { store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    const whole = JSON.stringify({ v: 1, ev: "reply", ts: "2099-01-01T00:00:00Z", author: "claude", body: "done" });
    appendFileSync(threadFile(store, id), whole.slice(0, 20));
    assert.equal(readThread(store, id).messages.length, 1);
    appendFileSync(threadFile(store, id), whole.slice(20) + "\n");
    assert.equal(readThread(store, id).messages.length, 2);
  } finally {
    cleanup();
  }
});

test("lines merged from two branches in either order fold the same", () => {
  const open = { v: 1, ev: "thread", id: "t_aaaaaa", ts: "2026-01-01T00:00:00Z", ...SAMPLE };
  const a = { v: 1, ev: "reply", ts: "2026-01-01T00:01:00Z", author: "claude", body: "first" };
  const b = { v: 1, ev: "reply", ts: "2026-01-01T00:02:00Z", author: "sam", body: "second" };
  const c = { v: 1, ev: "status", ts: "2026-01-01T00:03:00Z", author: "sam", status: "resolved" };
  const x = foldThread("t_aaaaaa", [open, a, b, c]);
  const y = foldThread("t_aaaaaa", [open, c, b, a]);
  const z = foldThread("t_aaaaaa", [b, c, open, a]);
  assert.deepEqual(x, y);
  assert.deepEqual(x, z);
  assert.deepEqual(x.messages.map((m) => m.body), [SAMPLE.body, "first", "second"]);
});

test("a file with no opening line is not a thread", () => {
  const { store, cleanup } = tempRepo();
  try {
    writeFileSync(threadFile(store, "t_bbbbbb"), JSON.stringify({ v: 1, ev: "reply", author: "x", body: "y" }) + "\n");
    assert.equal(readThread(store, "t_bbbbbb"), null);
    assert.equal(readAll(store).length, 0);
  } finally {
    cleanup();
  }
});

test("thread ids are checked, so a path cannot be smuggled in", () => {
  const { store, cleanup } = tempRepo();
  try {
    assert.throws(() => threadFile(store, "../../etc/passwd"));
    assert.equal(readThread(store, "t_../x"), null);
  } finally {
    cleanup();
  }
});

test("input from the page is trimmed to the named fields", () => {
  const a = cleanAnchor({ type: "script", css: "x", tag: "div", label: "y".repeat(500), evil: 1, quote: { exact: "q" } });
  assert.equal(a.type, "element");
  assert.equal(a.label.length, 80);
  assert.equal(a.evil, undefined);
  assert.deepEqual(a.quote, { exact: "q", prefix: "", suffix: "" });
  assert.equal(cleanBody("   "), null);
  assert.equal(cleanBody("x".repeat(10001)), null);
  assert.equal(cleanBody("ok\r\nline"), "ok\nline");
});

test("the store is found from a subfolder, but not above the git root", () => {
  const { repo, cleanup } = tempRepo();
  const outer = tempRepo({ comments: true, git: false });
  try {
    const found = findStore(`${repo}/.page-comments/threads`);
    assert.equal(found.repo, repo);
    const bare = tempRepo({ comments: false });
    try {
      assert.equal(findStore(bare.repo), null);
    } finally {
      bare.cleanup();
    }
  } finally {
    cleanup();
    outer.cleanup();
  }
});
