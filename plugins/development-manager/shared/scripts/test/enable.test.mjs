// enable-page-comments: turning comments on, the check, and undo putting every
// file back the way it was. All data here is invented.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { ENABLE, tempRepo } from "./helpers.mjs";

const ID = "development-manager@oeid-claude-plugins";

function enable(args, repo) {
  const r = spawnSync(process.execPath, [ENABLE, ...args, "--repo", repo], {
    encoding: "utf8",
    timeout: 60000,
    env: { ...process.env, PAGE_COMMENTS_SKIP_CLAUDE: "1" },
  });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr };
}

const SETTINGS = JSON.stringify({ hooks: { Stop: [] }, enabledPlugins: { "other-plugin@somewhere": true }, model: "x" }, null, 2) + "\n";
const MAKEFILE = ".PHONY: serve\nserve:\n\t@python3 -m http.server --port $(or $(PORT),8765)\n";
const CLAUDE_MD = "# Sample project\n\nSome rules.\n";

function seed(repo) {
  mkdirSync(join(repo, ".claude"), { recursive: true });
  writeFileSync(join(repo, ".claude", "settings.json"), SETTINGS);
  writeFileSync(join(repo, "Makefile"), MAKEFILE);
  writeFileSync(join(repo, "CLAUDE.md"), CLAUDE_MD);
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<!doctype html><html><head><title>Sample</title></head><body><h1>Hello</h1></body></html>");
}

test("detect finds the make target and its port", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    seed(repo);
    const r = enable(["--detect", "--json"], repo);
    assert.equal(r.code, 0, r.stderr);
    const d = JSON.parse(r.stdout);
    assert.equal(d.mode, "target");
    assert.equal(d.target, "http://127.0.0.1:8765");
  } finally {
    cleanup();
  }
});

test("enable sets up comments and answering, merges settings, and runs twice the same", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    seed(repo);
    const r = enable(["--target", "http://127.0.0.1:8765"], repo);
    assert.equal(r.code, 0, r.stderr);

    const dir = join(repo, ".page-comments");
    for (const f of ["threads/.gitkeep", "config.json", ".gitattributes", ".gitignore", "run", "install.json", ".state/plugin-root"]) assert.ok(existsSync(join(dir, f)), f);
    assert.ok(statSync(join(dir, "run")).mode & 0o100, "run is executable");
    assert.match(readFileSync(join(dir, ".gitattributes"), "utf8"), /threads\/\*\.jsonl merge=union/);
    const config = JSON.parse(readFileSync(join(dir, "config.json"), "utf8"));
    assert.equal(config.author, "test");
    assert.deepEqual(config.serve, { target: "http://127.0.0.1:8765", port: 8766 });

    const settings = JSON.parse(readFileSync(join(repo, ".claude", "settings.json"), "utf8"));
    assert.equal(settings.enabledPlugins[ID], true);
    assert.equal(settings.enabledPlugins["other-plugin@somewhere"], true);
    assert.deepEqual(settings.hooks, { Stop: [] });
    assert.equal(settings.model, "x");

    const md = readFileSync(join(repo, "CLAUDE.md"), "utf8");
    assert.ok(md.startsWith(CLAUDE_MD));
    assert.match(md, /development-manager:answer-page-comments/);

    const make = readFileSync(join(repo, "Makefile"), "utf8");
    assert.match(make, /\ncomments:.*\n\t@\.page-comments\/run serve --target http:\/\/127\.0\.0\.1:8765 --port 8766\n/);
    const dry = spawnSync("make", ["-C", repo, "-n", "comments"], { encoding: "utf8" });
    assert.equal(dry.status, 0, dry.stderr);

    // A second run changes nothing.
    const before = ["Makefile", "CLAUDE.md", ".claude/settings.json"].map((f) => readFileSync(join(repo, f), "utf8"));
    assert.equal(enable(["--target", "http://127.0.0.1:8765"], repo).code, 0);
    const after = ["Makefile", "CLAUDE.md", ".claude/settings.json"].map((f) => readFileSync(join(repo, f), "utf8"));
    assert.deepEqual(after, before);
  } finally {
    cleanup();
  }
});

test("undo puts every file back byte for byte", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    seed(repo);
    assert.equal(enable(["--target", "http://127.0.0.1:8765"], repo).code, 0);
    const r = enable(["--undo"], repo);
    assert.equal(r.code, 0, r.stderr);
    assert.equal(readFileSync(join(repo, ".claude", "settings.json"), "utf8"), SETTINGS.replace(/\n$/, "") + "\n");
    assert.deepEqual(JSON.parse(readFileSync(join(repo, ".claude", "settings.json"), "utf8")), JSON.parse(SETTINGS));
    assert.equal(readFileSync(join(repo, "Makefile"), "utf8"), MAKEFILE);
    assert.equal(readFileSync(join(repo, "CLAUDE.md"), "utf8"), CLAUDE_MD);
    assert.ok(!existsSync(join(repo, ".page-comments")));
  } finally {
    cleanup();
  }
});

test("undo removes files and folders that enable created, and keeps a key that was there before", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    mkdirSync(join(repo, "site"));
    writeFileSync(join(repo, "site", "index.html"), "<html><body>Hi</body></html>");
    assert.equal(enable(["--root", "site"], repo).code, 0);
    assert.ok(existsSync(join(repo, "CLAUDE.md")));
    assert.ok(existsSync(join(repo, ".claude", "settings.json")));
    assert.ok(!existsSync(join(repo, "Makefile")), "no Makefile is made");
    assert.equal(enable(["--undo"], repo).code, 0);
    assert.ok(!existsSync(join(repo, "CLAUDE.md")));
    assert.ok(!existsSync(join(repo, ".claude")));

    // The plugin was already on before enable: undo leaves it on.
    mkdirSync(join(repo, ".claude"));
    const had = JSON.stringify({ enabledPlugins: { [ID]: true } }, null, 2) + "\n";
    writeFileSync(join(repo, ".claude", "settings.json"), had);
    assert.equal(enable(["--root", "site"], repo).code, 0);
    assert.equal(enable(["--undo"], repo).code, 0);
    assert.equal(readFileSync(join(repo, ".claude", "settings.json"), "utf8"), had);
  } finally {
    cleanup();
  }
});

test("undo keeps comment threads unless asked to purge", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    seed(repo);
    assert.equal(enable(["--root", "site"], repo).code, 0);
    const thread = join(repo, ".page-comments", "threads", "t1.jsonl");
    writeFileSync(thread, "");
    assert.equal(enable(["--undo"], repo).code, 0);
    assert.ok(existsSync(thread));
    assert.ok(!existsSync(join(repo, ".page-comments", "install.json")));
    assert.ok(!existsSync(join(repo, ".page-comments", "run")));
    assert.equal(readFileSync(join(repo, "CLAUDE.md"), "utf8"), CLAUDE_MD);
    assert.equal(enable(["--undo", "--purge"], repo).code, 0);
    assert.ok(!existsSync(join(repo, ".page-comments")));
  } finally {
    cleanup();
  }
});

test("check proves the loop and leaves no test thread behind", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    seed(repo);
    assert.equal(enable(["--root", "site"], repo).code, 0);
    const r = enable(["--check"], repo);
    assert.equal(r.code, 0, r.stdout + r.stderr);
    assert.match(r.stdout, /ok\s+the plugin is on in \.claude\/settings\.json/);
    assert.match(r.stdout, /ok\s+pages get the comment bar/);
    assert.match(r.stdout, /ok\s+the watcher prints it: .*ev=thread_new/);
    assert.match(r.stdout, /The loop works/);
    const left = readFileSync(join(repo, ".page-comments", "threads", ".gitkeep"), "utf8");
    assert.equal(left, "");
    const threads = spawnSync("ls", [join(repo, ".page-comments", "threads")], { encoding: "utf8" }).stdout.trim();
    assert.equal(threads, "", "only the hidden .gitkeep is left");
    assert.ok(!existsSync(join(repo, ".page-comments", ".state", "server.json")), "the check server leaves no server record");
  } finally {
    cleanup();
  }
});

test("check fails when the CLAUDE.md note is gone", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  try {
    seed(repo);
    assert.equal(enable(["--root", "site"], repo).code, 0);
    writeFileSync(join(repo, "CLAUDE.md"), CLAUDE_MD);
    const r = enable(["--check"], repo);
    assert.equal(r.code, 1);
    assert.match(r.stdout, /FAIL\s+CLAUDE\.md points Claude to answer-page-comments/);
  } finally {
    cleanup();
  }
});
