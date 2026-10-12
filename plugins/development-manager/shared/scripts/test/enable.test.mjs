// enable-page-comments: turning comments on, the check, and undo putting every
// file back the way it was. All data here is invented.

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { ENABLE, tempRepo } from "./helpers.mjs";

const ID = "development-manager@oeid-claude-plugins";

function enable(args, repo, env = {}) {
  const r = spawnSync(process.execPath, [ENABLE, ...args, "--repo", repo], {
    encoding: "utf8",
    timeout: 60000,
    env: { ...process.env, PAGE_COMMENTS_SKIP_CLAUDE: "1", ...env },
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

// ---- --phone, against a stand-in for Tailscale's command line -----------------------------
// Invented names throughout. The existing entry on 443 stands for something else the
// person already serves on their tailnet name; it must come through every test untouched.

const FAKE_TS = join(dirname(fileURLToPath(import.meta.url)), "fake-tailscale.mjs");
const TS_HOST = "sample-mac.tailnet-example.ts.net";
const TS_LOGIN = "person@example.com";
const OTHER_ENTRY = { TCP: { 443: { HTTPS: true } }, Web: { [`${TS_HOST}:443`]: { Handlers: { "/": { Proxy: "http://127.0.0.1:4000" } } } } };

/** A fake Tailscale: its state file, its call log, and the env that points enable at it. */
function fakeTailscale({ serve = OTHER_ENTRY, status = {} } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "pc-ts-"));
  const statePath = join(dir, "state.json");
  const logPath = join(dir, "calls.log");
  const bin = join(dir, "tailscale");
  writeFileSync(bin, `#!/bin/sh\nexec "${process.execPath}" "${FAKE_TS}" "$@"\n`);
  chmodSync(bin, 0o755);
  writeFileSync(
    statePath,
    JSON.stringify({
      status: { BackendState: "Running", Self: { DNSName: `${TS_HOST}.`, UserID: 1234 }, User: { 1234: { LoginName: TS_LOGIN } }, CertDomains: [TS_HOST], ...status },
      serve: structuredClone(serve),
    }),
  );
  writeFileSync(logPath, "");
  return {
    env: { PAGE_COMMENTS_TAILSCALE: bin, FAKE_TAILSCALE_STATE: statePath, FAKE_TAILSCALE_LOG: logPath },
    serve: () => JSON.parse(readFileSync(statePath, "utf8")).serve,
    calls: () => readFileSync(logPath, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l).join(" ")),
    clearCalls: () => writeFileSync(logPath, ""),
    cleanup: () => rmSync(dir, { recursive: true, force: true }),
  };
}

const json = (repo, f) => JSON.parse(readFileSync(join(repo, ".page-comments", f), "utf8"));
const changes = (repo) => json(repo, "install.json").changes.filter((c) => c.kind === "tailscale-serve");

test("--phone serves the comment port on the tailnet, writes the setting, and records what it added", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const ts = fakeTailscale();
  try {
    seed(repo);
    const r = enable(["--target", "http://127.0.0.1:8765", "--phone"], repo, ts.env);
    assert.equal(r.code, 0, r.stderr);
    assert.match(r.stdout, new RegExp(`On the phone: https://${TS_HOST.replace(/\./g, "\\.")}:8766/`));
    assert.match(r.stdout, /tailscale serve --https=8766 off/);
    assert.match(r.stdout, /committed with the repo/);

    assert.deepEqual(json(repo, "config.json").phone, { host: TS_HOST, port: 8766, logins: [TS_LOGIN] });
    assert.deepEqual(changes(repo), [
      { kind: "tailscale-serve", host: TS_HOST, port: 8766, target: "http://127.0.0.1:8766", added: true, on: ["serve", "--bg", "--https=8766", "http://127.0.0.1:8766"], off: ["serve", "--https=8766", "off"] },
    ]);
    assert.deepEqual(ts.calls(), ["status --json", "serve status --json", "serve --bg --https=8766 http://127.0.0.1:8766", "serve status --json"]);
    const serve = ts.serve();
    assert.deepEqual(serve.Web[`${TS_HOST}:8766`], { Handlers: { "/": { Proxy: "http://127.0.0.1:8766" } } });
    assert.deepEqual(serve.Web[`${TS_HOST}:443`], OTHER_ENTRY.Web[`${TS_HOST}:443`], "the 443 entry is untouched");

    // Again: nothing new is served, and it still counts as added by enable.
    ts.clearCalls();
    const again = enable(["--phone"], repo, ts.env);
    assert.equal(again.code, 0, again.stderr);
    assert.ok(!ts.calls().some((c) => c.startsWith("serve --bg")), ts.calls().join("; "));
    assert.equal(changes(repo)[0].added, true);
    assert.ok(ts.calls().every((c) => !/funnel/i.test(c)));
  } finally {
    ts.cleanup();
    cleanup();
  }
});

test("--phone --undo turns off only its own port and keeps the rest on", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const ts = fakeTailscale();
  try {
    seed(repo);
    assert.equal(enable(["--target", "http://127.0.0.1:8765"], repo).code, 0);
    assert.equal(enable(["--phone"], repo, ts.env).code, 0);
    ts.clearCalls();
    const r = enable(["--phone", "--undo"], repo, ts.env);
    assert.equal(r.code, 0, r.stderr);
    assert.deepEqual(ts.calls(), ["serve status --json", "serve --https=8766 off"]);
    assert.deepEqual(ts.serve(), OTHER_ENTRY, "back to exactly what was there");
    assert.equal(json(repo, "config.json").phone, undefined);
    assert.deepEqual(changes(repo), []);
    assert.ok(existsSync(join(repo, ".page-comments", "run")), "the rest of page comments stays on");
    assert.equal(JSON.parse(readFileSync(join(repo, ".claude", "settings.json"), "utf8")).enabledPlugins[ID], true);
    const twice = enable(["--phone", "--undo"], repo, ts.env);
    assert.match(twice.stdout, /nothing to undo/);
  } finally {
    ts.cleanup();
    cleanup();
  }
});

test("--undo takes the phone off too", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const ts = fakeTailscale();
  try {
    seed(repo);
    assert.equal(enable(["--target", "http://127.0.0.1:8765", "--phone"], repo, ts.env).code, 0);
    ts.clearCalls();
    const r = enable(["--undo"], repo, ts.env);
    assert.equal(r.code, 0, r.stderr);
    assert.deepEqual(ts.calls(), ["serve status --json", "serve --https=8766 off"]);
    assert.deepEqual(ts.serve(), OTHER_ENTRY);
    assert.equal(readFileSync(join(repo, "Makefile"), "utf8"), MAKEFILE);
  } finally {
    ts.cleanup();
    cleanup();
  }
});

test("--phone stops when the port already serves something else, and changes nothing", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const taken = { TCP: { ...OTHER_ENTRY.TCP, 8766: { HTTPS: true } }, Web: { ...OTHER_ENTRY.Web, [`${TS_HOST}:8766`]: { Handlers: { "/": { Proxy: "http://127.0.0.1:9000" } } } } };
  const ts = fakeTailscale({ serve: taken });
  try {
    seed(repo);
    assert.equal(enable(["--target", "http://127.0.0.1:8765"], repo).code, 0);
    const before = readFileSync(join(repo, ".page-comments", "config.json"), "utf8");
    const r = enable(["--phone"], repo, ts.env);
    assert.equal(r.code, 1);
    assert.match(r.stderr, /already serves something else on https port 8766 \(\/ -> http:\/\/127\.0\.0\.1:9000\)/);
    assert.deepEqual(ts.calls(), ["status --json", "serve status --json"]);
    assert.deepEqual(ts.serve(), taken);
    assert.equal(readFileSync(join(repo, ".page-comments", "config.json"), "utf8"), before);
    assert.deepEqual(changes(repo), []);
  } finally {
    ts.cleanup();
    cleanup();
  }
});

test("--phone leaves on an entry that was there before it, on undo", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const mine = { TCP: { 8766: { HTTPS: true } }, Web: { [`${TS_HOST}:8766`]: { Handlers: { "/": { Proxy: "http://127.0.0.1:8766" } } } } };
  const ts = fakeTailscale({ serve: mine });
  try {
    seed(repo);
    assert.equal(enable(["--target", "http://127.0.0.1:8765", "--phone"], repo, ts.env).code, 0);
    assert.equal(changes(repo)[0].added, false);
    ts.clearCalls();
    const r = enable(["--phone", "--undo"], repo, ts.env);
    assert.equal(r.code, 0, r.stderr);
    assert.deepEqual(ts.calls(), []);
    assert.match(r.stdout, /there before enable/);
    assert.deepEqual(ts.serve(), mine);
  } finally {
    ts.cleanup();
    cleanup();
  }
});

test("--phone refuses Funnel, and stops when Tailscale is missing, off, or has no certificates", () => {
  const { repo, cleanup } = tempRepo({ comments: false });
  const off = fakeTailscale({ status: { BackendState: "Stopped" } });
  const noCerts = fakeTailscale({ status: { CertDomains: undefined } });
  try {
    seed(repo);
    assert.equal(enable(["--phone"], repo, noCerts.env).code, 3, "not enabled yet");
    assert.equal(enable(["--target", "http://127.0.0.1:8765"], repo).code, 0);
    for (const flag of ["--funnel", "--phone-funnel", "--Funnel=on"]) {
      const r = enable(["--phone", flag], repo, noCerts.env);
      assert.equal(r.code, 2, flag);
      assert.match(r.stderr, /never use/);
    }
    // helpers.mjs points PAGE_COMMENTS_TAILSCALE at a file that is not there.
    const missing = enable(["--phone"], repo);
    assert.equal(missing.code, 3, missing.stderr);
    assert.match(missing.stderr, /command line was not found/);
    const stopped = enable(["--phone"], repo, off.env);
    assert.equal(stopped.code, 1);
    assert.match(stopped.stderr, /not connected/);
    const certs = enable(["--phone"], repo, noCerts.env);
    assert.equal(certs.code, 1);
    assert.match(certs.stderr, /HTTPS Certificates/);
    for (const ts of [off, noCerts]) assert.ok(!ts.calls().some((c) => c.startsWith("serve --bg")));
    assert.equal(json(repo, "config.json").phone, undefined);
  } finally {
    off.cleanup();
    noCerts.cleanup();
    cleanup();
  }
});
