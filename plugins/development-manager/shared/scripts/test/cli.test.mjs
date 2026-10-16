import { test } from "node:test";
import assert from "node:assert/strict";
import { chmodSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createThread, readThread, threadFile } from "../lib/store.mjs";
import { SAMPLE, cli, tempRepo } from "./helpers.mjs";

test("bad usage exits 2", () => {
  const { repo, cleanup } = tempRepo();
  try {
    assert.equal(cli(["frobnicate", "--repo", repo]).code, 2);
    assert.equal(cli(["list", "--nope", "--repo", repo]).code, 2);
    assert.equal(cli(["show", "not-an-id", "--repo", repo]).code, 2);
    assert.equal(cli(["reply", "--repo", repo]).code, 2);
    assert.equal(cli([]).code, 2);
    assert.equal(cli(["help"]).code, 0);
  } finally {
    cleanup();
  }
});

test("a missing thread or a repo without comments exits 3", () => {
  const { repo, cleanup } = tempRepo();
  const bare = tempRepo({ comments: false });
  try {
    const r = cli(["show", "t_abcdef", "--repo", repo]);
    assert.equal(r.code, 3);
    assert.match(r.stderr, /no thread t_abcdef/);
    const off = cli(["list", "--repo", bare.repo]);
    assert.equal(off.code, 3);
    assert.match(off.stderr, /not turned on/);
  } finally {
    cleanup();
    bare.cleanup();
  }
});

test("reply, resolve, reopen and dismiss from the command line", () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    assert.equal(cli(["reply", id, "--commit", "9c41d0e", "Added the walk time.", "--repo", repo]).code, 0);
    let t = readThread(store, id);
    assert.equal(t.messages[1].author, "claude");
    assert.equal(t.messages[1].commit, "9c41d0e");
    assert.equal(cli(["resolve", id, "fixed in 9c41d0e", "--repo", repo]).code, 0);
    assert.equal(readThread(store, id).status, "resolved");
    assert.equal(cli(["resolve", id, "--reopen", "--author", "sam", "--repo", repo]).code, 0);
    assert.equal(readThread(store, id).status, "open");
    assert.equal(cli(["dismiss", id, "--repo", repo]).code, 0);
    assert.equal(readThread(store, id).status, "dismissed");
  } finally {
    cleanup();
  }
});

test("a reply that cannot be written exits 4", { skip: process.getuid && process.getuid() === 0 }, () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    chmodSync(threadFile(store, id), 0o444);
    const r = cli(["reply", id, "text", "--repo", repo]);
    assert.equal(r.code, 4);
    assert.match(r.stderr, /did not land/);
    chmodSync(threadFile(store, id), 0o644);
  } finally {
    cleanup();
  }
});

test("list --json gives review-md's two shapes", () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    createThread(store, SAMPLE);
    createThread(store, { ...SAMPLE, page: { url: "http://127.0.0.1:8766/", path: "/", title: "Home" } });
    const all = JSON.parse(cli(["list", "--json", "--repo", repo]).stdout);
    assert.equal(all.root, repo);
    assert.deepEqual(all.files.map((f) => f.file), ["/", "/trips/sample/"]);
    assert.deepEqual(Object.keys(all.files[0]).sort(), ["file", "threads", "uid", "vaultPath"]);
    const one = JSON.parse(cli(["list", "--json", "--page", "/trips/sample/", "--repo", repo]).stdout);
    assert.equal(one.file, "/trips/sample/");
    assert.equal(one.vaultPath, repo);
    assert.equal(one.threads.length, 1);
  } finally {
    cleanup();
  }
});

test("list filters, show and stats", () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    const a = createThread(store, SAMPLE);
    const b = createThread(store, SAMPLE);
    cli(["reply", b, "Done.", "--repo", repo]);
    const waiting = JSON.parse(cli(["list", "--open", "--waiting", "claude", "--json", "--repo", repo]).stdout);
    assert.deepEqual(waiting.files[0].threads.map((t) => t.id), [a]);
    const shown = JSON.parse(cli(["show", a, "--json", "--repo", repo]).stdout);
    assert.equal(shown.id, a);
    const text = cli(["show", a, "--repo", repo]).stdout;
    assert.match(text, /Day 2: museum and park/);
    const stats = JSON.parse(cli(["stats", "--json", "--repo", repo]).stdout);
    assert.deepEqual(stats.total, { open: 2, waiting: 1, resolved: 0, dismissed: 0 });
  } finally {
    cleanup();
  }
});

test("--repo is optional: the repo is found from the working folder", () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    createThread(store, SAMPLE);
    const r = cli(["list", "--json"], { cwd: join(repo, ".page-comments") });
    assert.equal(r.code, 0);
    assert.equal(JSON.parse(r.stdout).files.length, 1);
  } finally {
    cleanup();
  }
});

test("reply --ask tags a person; list --asking finds the thread; show prints it", () => {
  const { repo, store, cleanup } = tempRepo();
  try {
    writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ author: "sam", agents: { "page-owner": "answers" } }));
    const a = createThread(store, SAMPLE);
    const b = createThread(store, SAMPLE);
    const r = cli(["reply", a, "--author", "page-owner", "--ask", "sam", "Should it say minutes or miles?", "--repo", repo]);
    assert.equal(r.code, 0, r.stderr);
    assert.match(r.stdout, /asking sam/);
    const t = readThread(store, a);
    assert.equal(t.asking, "sam");
    assert.equal(t.waiting, "human", "page-owner answers, so the thread waits on a person");
    const tagged = JSON.parse(cli(["list", "--open", "--asking", "sam", "--json", "--repo", repo]).stdout);
    assert.deepEqual(tagged.files[0].threads.map((x) => x.id), [a]);
    assert.equal(tagged.files[0].threads[0].asking, "sam");
    assert.match(cli(["list", "--asking", "sam", "--repo", repo]).stdout, new RegExp(`${a} .*asking sam`));
    assert.doesNotMatch(cli(["list", "--asking", "sam", "--repo", repo]).stdout, new RegExp(b));
    assert.match(cli(["show", a, "--repo", repo]).stdout, /^Asking: +sam$/m);
    assert.equal(JSON.parse(cli(["show", a, "--json", "--repo", repo]).stdout).asking, "sam");
    assert.equal(JSON.parse(cli(["show", b, "--json", "--repo", repo]).stdout).asking, null);

    assert.equal(cli(["reply", a, "--author", "sam", "Minutes.", "--repo", repo]).code, 0);
    assert.equal(readThread(store, a).asking, null, "cleared once sam answers");
    assert.match(cli(["list", "--asking", "sam", "--repo", repo]).stdout, /No threads match/);

    assert.equal(cli(["reply", a, "--ask", "two words", "x", "--repo", repo]).code, 2);
    assert.equal(cli(["reply", a, "--ask", "claude", "x", "--repo", repo]).code, 2);
  } finally {
    cleanup();
  }
});
